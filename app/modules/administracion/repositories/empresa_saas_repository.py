"""Persistencia de empresas, planes y suscripciones sin datos comerciales."""

from datetime import date
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from zoneinfo import ZoneInfo
from fastapi import HTTPException

from psycopg2.extras import Json, RealDictCursor

from app.database.connection import get_connection
from app.core.plan_empresa import (LOCK_PLANES, normalizar_politica, validar_politica,
                                  uso_empresa_cursor, seleccionar_pausas_reportes)


def listar_planes() -> list[dict[str, object]]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM plan ORDER BY id")
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def crear_plan(codigo: str, nombre: str, limites: dict, funciones: dict, actor_id: int, publico: bool = False, **metadatos) -> dict[str, object]:
    datos = _configurar_plan({}, {"codigo": codigo, "nombre": nombre, "limites": limites,
                                 "funciones": funciones, "publico": publico, **metadatos})
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """INSERT INTO plan (codigo,nombre,limites,funciones,publico,descripcion,precio,moneda,condiciones)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (datos['codigo'],datos['nombre'],Json(datos['limites']),Json(datos['funciones']),publico,
                 datos['descripcion'],datos['precio'],datos['moneda'],datos['condiciones']),
            )
            row = dict(cur.fetchone())
            auditar(cur, actor_id, "CREAR_PLAN", recurso_id=str(row["id"]))
            _historial_plan(cur, row['id'], actor_id, None, row, {})
        conn.commit()
        return row
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def listar_empresas() -> list[dict[str, object]]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT e.id, e.codigo, e.nombre, e.estado,
                          s.id AS suscripcion_id, s.estado AS suscripcion_estado,
                          s.fecha_inicio, s.fecha_vencimiento,
                          p.id AS plan_id, p.codigo AS plan_codigo, p.nombre AS plan_nombre,
                          reg.correo_contacto, reg.responsable
                   FROM empresa e
                   LEFT JOIN LATERAL (
                       SELECT * FROM suscripcion WHERE empresa_id=e.id
                       ORDER BY fecha_creacion DESC,id DESC LIMIT 1
                   ) s ON TRUE
                   LEFT JOIN plan p ON p.id=s.plan_id
                   LEFT JOIN solicitud_registro_empresa reg ON reg.empresa_id=e.id
                   ORDER BY e.id"""
            )
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def crear_empresa_con_admin(datos: dict[str, object], password_hash: str, actor_id: int) -> dict[str, object]:
    """Alta atomica: empresa, suscripcion y administrador inicial."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT pg_advisory_xact_lock_shared(%s)", (LOCK_PLANES,))
            cur.execute("SELECT id,limites FROM plan WHERE id=%s AND activo=TRUE FOR SHARE", (datos["plan_id"],))
            plan = cur.fetchone()
            if plan is None:
                raise ValueError("Plan no encontrado o inactivo.")
            if plan["limites"].get("usuarios", 1) < 1:
                raise ValueError("El plan debe permitir al menos la cuenta administradora inicial.")
            cur.execute(
                "INSERT INTO empresa (codigo,nombre) VALUES (%s,%s) RETURNING id,codigo,nombre,estado",
                (datos["codigo"], datos["nombre"]),
            )
            empresa = dict(cur.fetchone())
            cur.execute(
                """INSERT INTO suscripcion (empresa_id,plan_id,estado,fecha_inicio,fecha_vencimiento)
                   VALUES (%s,%s,'ACTIVA',%s,%s) RETURNING id""",
                (empresa["id"], datos["plan_id"], datos["fecha_inicio"], datos["fecha_vencimiento"]),
            )
            suscripcion_id = int(cur.fetchone()["id"])
            cur.execute(
                """INSERT INTO usuario (empresa_id,nombre,apellido,username,correo,password_hash)
                   VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
                (empresa["id"], datos["admin_nombre"], datos["admin_apellido"],
                 datos["admin_username"], datos["admin_correo"], password_hash),
            )
            admin_usuario_id = int(cur.fetchone()["id"])
            cur.execute(
                """INSERT INTO usuario_rol (usuario_id,rol_id)
                   SELECT %s,id FROM rol WHERE nombre='ADMINISTRADOR' AND activo=TRUE
                   RETURNING rol_id""",
                (admin_usuario_id,),
            )
            if cur.fetchone() is None:
                raise ValueError("No existe el rol ADMINISTRADOR.")
            empresa["admin_usuario_id"] = admin_usuario_id
            empresa["suscripcion_id"] = suscripcion_id
            auditar(cur, actor_id, "CREAR_EMPRESA", empresa_id=int(empresa["id"]))
        conn.commit()
        return empresa
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def cambiar_estado_empresa(empresa_id: int, estado: str, actor_id: int) -> dict[str, object] | None:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('SELECT pg_advisory_xact_lock_shared(%s)',(LOCK_PLANES,))
            cur.execute('SELECT estado FROM empresa WHERE id=%s FOR UPDATE', (empresa_id,))
            actual = cur.fetchone()
            if actual and actual['estado'] == 'PENDIENTE' and estado != 'CANCELADA':
                raise ValueError('Activa esta empresa asignando su plan y vigencia desde la suscripción.')
            if actual and actual['estado'] == 'PENDIENTE' and estado == 'CANCELADA':
                cur.execute("UPDATE suscripcion SET estado='CANCELADA' WHERE empresa_id=%s AND estado='PENDIENTE'", (empresa_id,))
            cur.execute(
                """UPDATE empresa SET estado=%s,fecha_actualizacion=CURRENT_TIMESTAMP
                   WHERE id=%s RETURNING id,codigo,nombre,estado""",
                (estado, empresa_id),
            )
            row = cur.fetchone()
            if row:
                auditar(cur, actor_id, "ESTADO_EMPRESA_" + estado, empresa_id=empresa_id)
        conn.commit()
        return dict(row) if row else None
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def asignar_plan_empresa(
    empresa_id: int, plan_id: int, fecha_inicio: date, fecha_vencimiento: date | None, actor_id: int,
) -> dict[str, object] | None:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK_PLANES,))
            cur.execute("SELECT id,estado FROM empresa WHERE id=%s FOR UPDATE", (empresa_id,))
            empresa = cur.fetchone()
            if empresa is None:
                return None
            cur.execute("SELECT * FROM plan WHERE id=%s AND activo=TRUE FOR SHARE", (plan_id,))
            plan = cur.fetchone()
            if plan is None:
                raise ValueError("Plan no encontrado o inactivo.")
            if empresa['estado'] == 'PENDIENTE' and plan['limites'].get('usuarios', 1) < 1:
                raise ValueError('El plan debe permitir la cuenta administradora inicial.')
            cur.execute("SELECT to_jsonb(s) AS datos FROM suscripcion s WHERE empresa_id=%s ORDER BY fecha_creacion DESC,id DESC LIMIT 1", (empresa_id,))
            anterior = cur.fetchone()
            cur.execute(
                "UPDATE suscripcion SET estado='CANCELADA' WHERE empresa_id=%s AND estado IN ('ACTIVA','PENDIENTE')",
                (empresa_id,),
            )
            cur.execute(
                """INSERT INTO suscripcion (empresa_id,plan_id,estado,fecha_inicio,fecha_vencimiento)
                   VALUES (%s,%s,'ACTIVA',%s,%s)
                   RETURNING id,empresa_id,plan_id,estado,fecha_inicio,fecha_vencimiento""",
                (empresa_id, plan_id, fecha_inicio, fecha_vencimiento),
            )
            row = dict(cur.fetchone())
            auditar(cur, actor_id, "ASIGNAR_SUSCRIPCION", empresa_id, str(row["id"]),
                    anterior['datos'] if anterior else None, row)
            _ajustar_programaciones(cur, empresa_id, normalizar_politica(plan))
            if empresa['estado'] == 'PENDIENTE':
                cur.execute("UPDATE empresa SET estado='ACTIVA',fecha_actualizacion=CURRENT_TIMESTAMP WHERE id=%s", (empresa_id,))
                auditar(cur, actor_id, 'APROBAR_REGISTRO_EMPRESA', empresa_id, str(row['id']))
        conn.commit()
        return row
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def obtener_plan_empresa(empresa_id: int) -> dict[str, object] | None:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT e.id AS empresa_id,e.codigo AS empresa_codigo,e.nombre AS empresa_nombre,
                          e.estado AS empresa_estado,s.id AS suscripcion_id,
                          s.estado AS suscripcion_estado,s.fecha_inicio,s.fecha_vencimiento,
                          p.id AS plan_id,p.codigo AS plan_codigo,p.nombre AS plan_nombre,
                          p.limites,p.funciones,p.activo AS plan_activo
                   FROM empresa e
                   LEFT JOIN LATERAL (
                       SELECT * FROM suscripcion WHERE empresa_id=e.id
                       ORDER BY fecha_creacion DESC,id DESC LIMIT 1
                   ) s ON TRUE
                   LEFT JOIN plan p ON p.id=s.plan_id
                   WHERE e.id=%s LIMIT 1""",
                (empresa_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            respuesta = dict(row)
            uso = {}
            for clave, tabla in (("usuarios", "usuario"), ("empleados", "empleado"), ("productos", "producto"), ("sucursales", "sucursal")):
                cur.execute(f"SELECT count(*) AS total FROM {tabla} WHERE empresa_id=%s AND activo=TRUE", (empresa_id,))
                uso[clave] = int(cur.fetchone()["total"])
            respuesta["uso"] = uso
            from datetime import datetime
            from zoneinfo import ZoneInfo
            hoy = datetime.now(ZoneInfo("America/La_Paz")).date()
            respuesta["operaciones_habilitadas"] = bool(
                respuesta["empresa_estado"] == "ACTIVA" and respuesta["suscripcion_estado"] == "ACTIVA"
                and respuesta["plan_activo"] and respuesta["fecha_inicio"] <= hoy
                and (respuesta["fecha_vencimiento"] is None or respuesta["fecha_vencimiento"] >= hoy)
            )
            return respuesta
    finally:
        conn.close()


def auditar(cursor, actor_id: int, accion: str, empresa_id: int | None = None, recurso_id: str | None = None, antes=None, despues=None) -> None:
    cursor.execute(
        "INSERT INTO evento_plataforma (actor_id,empresa_id,accion,recurso_id,antes,despues) VALUES (%s,%s,%s,%s,%s,%s)",
        (actor_id,empresa_id,accion,recurso_id,_json_adaptado(antes),_json_adaptado(despues)),
    )


def editar_plan(plan_id: int, datos: dict, actor_id: int):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK_PLANES,))
            cur.execute("SELECT * FROM plan WHERE id=%s FOR UPDATE", (plan_id,))
            actual = cur.fetchone()
            if actual is None:
                return None
            propuesta = _configurar_plan(dict(actual), datos)
            impacto = _impacto_plan(cur, plan_id, propuesta)
            esperado = _token_impacto(dict(actual), propuesta, impacto)
            if not datos.get('token_previsualizacion') or datos['token_previsualizacion'] != esperado:
                raise HTTPException(409, {"codigo": "PREVISUALIZACION_REQUERIDA", "mensaje": "Previsualiza nuevamente: la configuración o el uso de las empresas cambió."})
            cur.execute(
                """UPDATE plan SET codigo=%s,nombre=%s,limites=%s,funciones=%s,activo=%s,publico=%s,
                    descripcion=%s,precio=%s,moneda=%s,condiciones=%s,revision=revision+1
                    WHERE id=%s RETURNING *""",
                (propuesta['codigo'],propuesta['nombre'],Json(propuesta['limites']),Json(propuesta['funciones']),
                 propuesta['activo'],propuesta['publico'],propuesta['descripcion'],propuesta['precio'],
                 propuesta['moneda'],propuesta['condiciones'],plan_id),
            )
            row = dict(cur.fetchone())
            for empresa in impacto['empresas']:
                _ajustar_programaciones(cur, empresa['id'], normalizar_politica(propuesta))
            _historial_plan(cur, plan_id, actor_id, dict(actual), row, impacto)
            auditar(cur, actor_id, "EDITAR_PLAN", recurso_id=str(plan_id), antes=dict(actual), despues=row)
        conn.commit()
        return row
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def editar_empresa(empresa_id: int, nombre: str, actor_id: int):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("UPDATE empresa SET nombre=%s,fecha_actualizacion=CURRENT_TIMESTAMP WHERE id=%s RETURNING id,codigo,nombre,estado", (nombre,empresa_id))
            row = cur.fetchone()
            if row:
                auditar(cur, actor_id, "EDITAR_EMPRESA", empresa_id)
        conn.commit()
        return dict(row) if row else None
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def listar_eventos_plataforma():
    conn=get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id,actor_id,empresa_id,accion,recurso_id,fecha FROM evento_plataforma ORDER BY id DESC LIMIT 200")
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

def _json_adaptado(valor):
    return Json(json.loads(json.dumps(valor, default=str))) if valor is not None else None


def _configurar_plan(actual, cambios):
    permitidas = {'codigo','nombre','descripcion','precio','moneda','condiciones','activo','publico','limites','funciones','token_previsualizacion'}
    if set(cambios) - permitidas:
        raise ValueError('Campos de plan desconocidos.')
    datos = {'descripcion':'','precio':Decimal('0'),'moneda':'BOB','condiciones':'','activo':True,'publico':False, **actual}
    datos.update({k:v for k,v in cambios.items() if k not in {'limites','funciones','token_previsualizacion'}})
    for k, minimo, maximo in (('codigo',2,50),('nombre',2,120),('descripcion',0,4000),('condiciones',0,10000)):
        if not isinstance(datos.get(k),str) or not minimo <= len(datos[k].strip()) <= maximo:
            raise ValueError(f'Campo inválido: {k}.')
        datos[k] = datos[k].strip()
    datos['codigo'] = datos['codigo'].upper()
    if not re.fullmatch(r'[A-Z0-9_]{2,50}',datos['codigo']):
        raise ValueError('Código de plan inválido.')
    if actual.get('codigo') == 'STYLEAR_LEGADO' and datos['codigo'] != actual['codigo']:
        raise ValueError('El código del plan de transición es estable.')
    if not isinstance(datos['moneda'],str) or not re.fullmatch(r'[A-Z]{3}',datos['moneda']):
        raise ValueError('Moneda inválida; utiliza tres letras mayúsculas.')
    try:
        precio = Decimal(str(datos['precio']))
        if not precio.is_finite() or precio < 0 or precio > Decimal('9999999999.99') or precio != precio.quantize(Decimal('.01')):
            raise ValueError()
        datos['precio'] = precio.quantize(Decimal('.01'))
    except (InvalidOperation, ValueError):
        raise ValueError('Precio inválido; admite como máximo dos decimales.') from None
    for clave in ('activo','publico'):
        if type(datos[clave]) is not bool:
            raise ValueError(f'{clave} requiere un booleano.')
    for clave in ('limites','funciones'):
        valor = cambios.get(clave,{})
        if not isinstance(valor,dict):
            raise ValueError(f'{clave} debe ser un objeto.')
    politica = normalizar_politica(actual)
    # Las claves excluidas se conservan compatibles y no son opciones comerciales.
    datos['limites'] = {**politica['limites'], **cambios.get('limites',{})}
    datos['funciones'] = {**politica['funciones'], **cambios.get('funciones',{})}
    validar_politica(datos['limites'],datos['funciones'])
    if datos['publico'] and datos['codigo']=='STYLEAR_LEGADO':
        raise ValueError('El plan de transición no se publica.')
    return {k:datos[k] for k in permitidas if k in datos and k != 'token_previsualizacion'}


def _historial_plan(cur, plan_id, actor_id, antes, despues, impacto):
    cur.execute("""INSERT INTO plan_historial(plan_id,actor_id,antes,despues,impacto)
        VALUES(%s,%s,%s,%s,%s)""", (plan_id,actor_id,_json_adaptado(antes),_json_adaptado(despues),_json_adaptado(impacto)))


def _programaciones(cur, empresa_id):
    cur.execute('SELECT * FROM reporte_programado WHERE empresa_id=%s ORDER BY id',(empresa_id,))
    return [dict(r) for r in cur.fetchall()]


def _ajustar_programaciones(cur, empresa_id, politica):
    pausar = seleccionar_pausas_reportes(_programaciones(cur,empresa_id),politica)
    if pausar:
        cur.execute("""UPDATE reporte_programado SET activo=FALSE,pausa_motivo='CAMBIO_PLAN'
            WHERE empresa_id=%s AND id=ANY(%s)""",(empresa_id,pausar))
    if not politica['funciones']['horario_respaldo_configurable']:
        cur.execute("""UPDATE respaldo_programacion SET hora_local='02:00',zona_horaria='America/La_Paz',
            actualizada_en=CURRENT_TIMESTAMP WHERE empresa_id=%s""",(empresa_id,))


def _impacto_plan(cur, plan_id, propuesta):
    cur.execute("""SELECT e.id,e.nombre,e.estado,s.id AS suscripcion_id,s.estado AS suscripcion_estado
        FROM empresa e JOIN LATERAL (SELECT * FROM suscripcion WHERE empresa_id=e.id
            ORDER BY fecha_creacion DESC,id DESC LIMIT 1) s ON TRUE
        WHERE s.plan_id=%s ORDER BY e.id""",(plan_id,))
    empresas = []
    politica = normalizar_politica(propuesta)
    for row in cur.fetchall():
        empresa = dict(row)
        uso = uso_empresa_cursor(cur,empresa['id'])
        programaciones = _programaciones(cur,empresa['id'])
        cur.execute('SELECT * FROM respaldo_programacion WHERE empresa_id=%s',(empresa['id'],))
        respaldo = cur.fetchone()
        empresas.append({**empresa,'uso':uso,'excesos':{
            k:{'uso':v,'limite':politica['limites'][k]} for k,v in uso.items()
            if k in politica['limites'] and v > politica['limites'][k]},
            'programaciones':programaciones,
            'reportes_a_pausar':seleccionar_pausas_reportes(programaciones,politica),
            'programacion_respaldo':dict(respaldo) if respaldo else None,
            'restablecer_horario_respaldo':bool(respaldo and not politica['funciones']['horario_respaldo_configurable']
                 and (str(respaldo['hora_local'])!='02:00:00' or respaldo['zona_horaria']!='America/La_Paz')),
            'operaciones_bloqueadas_por_desactivar_plan':not propuesta['activo']})
    return {'total_empresas':len(empresas),'empresas':empresas}


def _token_impacto(actual, propuesta, impacto):
    contenido = json.dumps({'actual':actual,'propuesta':propuesta,'impacto':impacto},default=str,sort_keys=True,separators=(',',':'))
    return hashlib.sha256(contenido.encode()).hexdigest()


def previsualizar_plan(plan_id, cambios):
    conn=get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('SELECT pg_advisory_xact_lock(%s)',(LOCK_PLANES,))
            cur.execute('SELECT * FROM plan WHERE id=%s',(plan_id,))
            actual=cur.fetchone()
            if not actual:
                raise HTTPException(404,'Plan no encontrado.')
            propuesta=_configurar_plan(dict(actual),cambios)
            impacto=_impacto_plan(cur,plan_id,propuesta)
            return {'plan_actual':dict(actual),'propuesta':propuesta,'impacto':impacto,
                    'token_previsualizacion':_token_impacto(dict(actual),propuesta,impacto)}
    finally:
        conn.close()


def historial_plan(plan_id):
    conn=get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('SELECT * FROM plan_historial WHERE plan_id=%s ORDER BY id DESC LIMIT 200',(plan_id,))
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def historial_suscripciones(empresa_id):
    conn=get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""SELECT s.*,p.codigo AS plan_codigo,p.nombre AS plan_nombre FROM suscripcion s
                JOIN plan p ON p.id=s.plan_id WHERE s.empresa_id=%s ORDER BY s.fecha_creacion DESC,s.id DESC""",(empresa_id,))
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def resumen_planes():
    conn=get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""WITH actuales AS (
                SELECT e.id,e.estado,s.plan_id,s.estado AS suscripcion_estado,s.fecha_inicio,s.fecha_vencimiento
                FROM empresa e JOIN LATERAL(SELECT * FROM suscripcion WHERE empresa_id=e.id
                    ORDER BY fecha_creacion DESC,id DESC LIMIT 1) s ON TRUE)
                SELECT p.id,p.codigo,p.nombre,count(a.id) AS empresas,
                    count(a.id) FILTER(WHERE a.estado='ACTIVA' AND a.suscripcion_estado='ACTIVA' AND p.activo
                        AND a.fecha_inicio<=CURRENT_DATE AND (a.fecha_vencimiento IS NULL OR a.fecha_vencimiento>=CURRENT_DATE)) AS vigentes
                FROM plan p LEFT JOIN actuales a ON a.plan_id=p.id GROUP BY p.id ORDER BY p.id""")
            return [{**dict(r),'no_vigentes':int(r['empresas'])-int(r['vigentes'])} for r in cur.fetchall()]
    finally:
        conn.close()


def empresas_por_plan(plan_id=None,estado=None,buscar='',pagina=1,tamano=20):
    conn=get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            where=""" WHERE (%s::bigint IS NULL OR s.plan_id=%s) AND (%s::text IS NULL OR e.estado=%s)
                AND (e.nombre ILIKE %s OR e.codigo ILIKE %s)"""
            params=(plan_id,plan_id,estado,estado,'%'+buscar+'%','%'+buscar+'%')
            fuente=""" FROM empresa e LEFT JOIN LATERAL(SELECT * FROM suscripcion WHERE empresa_id=e.id
                ORDER BY fecha_creacion DESC,id DESC LIMIT 1) s ON TRUE LEFT JOIN plan p ON p.id=s.plan_id"""
            cur.execute('SELECT count(*) AS total'+fuente+where,params)
            total=cur.fetchone()['total']
            cur.execute("""SELECT e.id,e.codigo,e.nombre,e.estado,s.id AS suscripcion_id,s.plan_id,
                s.estado AS suscripcion_estado,s.fecha_inicio,s.fecha_vencimiento,p.codigo AS plan_codigo,p.nombre AS plan_nombre,p.limites,
                coalesce(e.estado='ACTIVA' AND s.estado='ACTIVA' AND p.activo AND s.fecha_inicio<=CURRENT_DATE
                    AND (s.fecha_vencimiento IS NULL OR s.fecha_vencimiento>=CURRENT_DATE),FALSE) AS vigente"""
                +fuente+where+' ORDER BY e.id LIMIT %s OFFSET %s',params+(tamano,(pagina-1)*tamano))
            empresas=[dict(r) for r in cur.fetchall()]
            for empresa in empresas:
                empresa['uso']=uso_empresa_cursor(cur,empresa['id'])
            return {'total':total,'pagina':pagina,'tamano':tamano,'empresas':empresas}
    finally:
        conn.close()
