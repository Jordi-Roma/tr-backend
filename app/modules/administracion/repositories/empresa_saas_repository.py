"""Persistencia de empresas, planes y suscripciones sin datos comerciales."""

from datetime import date

from psycopg2.extras import Json, RealDictCursor

from app.database.connection import get_connection


def listar_planes() -> list[dict[str, object]]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, codigo, nombre, limites, funciones, activo FROM plan ORDER BY id")
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def crear_plan(codigo: str, nombre: str, limites: dict, funciones: dict, actor_id: int) -> dict[str, object]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """INSERT INTO plan (codigo, nombre, limites, funciones)
                   VALUES (%s, %s, %s, %s)
                   RETURNING id, codigo, nombre, limites, funciones, activo""",
                (codigo, nombre, Json(limites), Json(funciones)),
            )
            row = dict(cur.fetchone())
            auditar(cur, actor_id, "CREAR_PLAN", recurso_id=str(row["id"]))
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
                          p.id AS plan_id, p.codigo AS plan_codigo, p.nombre AS plan_nombre
                   FROM empresa e
                   LEFT JOIN LATERAL (
                       SELECT * FROM suscripcion WHERE empresa_id=e.id
                       ORDER BY fecha_creacion DESC,id DESC LIMIT 1
                   ) s ON TRUE
                   LEFT JOIN plan p ON p.id=s.plan_id
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
            cur.execute("SELECT id FROM empresa WHERE id=%s FOR UPDATE", (empresa_id,))
            if cur.fetchone() is None:
                return None
            cur.execute("SELECT id FROM plan WHERE id=%s AND activo=TRUE", (plan_id,))
            if cur.fetchone() is None:
                raise ValueError("Plan no encontrado o inactivo.")
            cur.execute(
                "UPDATE suscripcion SET estado='CANCELADA' WHERE empresa_id=%s AND estado='ACTIVA'",
                (empresa_id,),
            )
            cur.execute(
                """INSERT INTO suscripcion (empresa_id,plan_id,estado,fecha_inicio,fecha_vencimiento)
                   VALUES (%s,%s,'ACTIVA',%s,%s)
                   RETURNING id,empresa_id,plan_id,estado,fecha_inicio,fecha_vencimiento""",
                (empresa_id, plan_id, fecha_inicio, fecha_vencimiento),
            )
            row = dict(cur.fetchone())
            auditar(cur, actor_id, "ASIGNAR_SUSCRIPCION", empresa_id, str(row["id"]))
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


def auditar(cursor, actor_id: int, accion: str, empresa_id: int | None = None, recurso_id: str | None = None) -> None:
    cursor.execute(
        "INSERT INTO evento_plataforma (actor_id,empresa_id,accion,recurso_id) VALUES (%s,%s,%s,%s)",
        (actor_id,empresa_id,accion,recurso_id),
    )


def editar_plan(plan_id: int, datos: dict, actor_id: int):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT codigo FROM plan WHERE id=%s FOR UPDATE", (plan_id,))
            actual = cur.fetchone()
            if actual is None:
                return None
            if actual["codigo"] == "STYLEAR_LEGADO" and datos["codigo"] != "STYLEAR_LEGADO":
                raise ValueError("El código del plan de transición es estable.")
            cur.execute(
                """UPDATE plan SET codigo=%s,nombre=%s,limites=%s,funciones=%s,activo=%s
                   WHERE id=%s RETURNING id,codigo,nombre,limites,funciones,activo""",
                (datos["codigo"], datos["nombre"], Json(datos["limites"]), Json(datos["funciones"]), datos["activo"], plan_id),
            )
            row = dict(cur.fetchone())
            auditar(cur, actor_id, "EDITAR_PLAN", recurso_id=str(plan_id))
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
