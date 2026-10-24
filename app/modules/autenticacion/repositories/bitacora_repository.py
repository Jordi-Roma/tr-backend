from psycopg2.extras import RealDictCursor

from app.database.connection import get_connection


def registrar_bitacora(
    usuario_id: int | None,
    accion: str,
    modulo: str,
    resultado: str,
    descripcion: str | None = None,
    direccion_ip: str | None = None,
    user_agent: str | None = None,
    empresa_id: int | None = None,
) -> None:
    """
    Registra un evento en la bitacora del sistema.
    Esta funcion es 'best-effort': si falla, no interrumpe la operacion principal.
    NUNCA registrar contrasenas, hashes, tokens ni datos sensibles.
    """
    import ipaddress
    ip_val: str | None = None
    if direccion_ip:
        try:
            ipaddress.ip_address(direccion_ip.strip())
            ip_val = direccion_ip.strip()
        except ValueError:
            ip_val = None

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO bitacora (
                usuario_id,
                empresa_id,
                accion,
                modulo,
                descripcion,
                resultado,
                direccion_ip,
                user_agent
            )
            VALUES (%s, COALESCE(%s, (SELECT empresa_id FROM usuario WHERE id = %s)), %s, %s, %s, %s, %s::INET, %s);
            """,
            (
                usuario_id,
                empresa_id,
                usuario_id,
                accion,
                modulo,
                descripcion,
                resultado,
                ip_val,
                user_agent,
            ),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        # No re-lanzar: el registro de bitacora no debe romper operaciones
    finally:
        cursor.close()
        connection.close()



def _filtros(empresa_id,usuario_id=None,accion=None,modulo=None,resultado=None,fecha_desde=None,fecha_hasta=None,**_):
    condiciones=["b.empresa_id IS NOT DISTINCT FROM %s"]
    params=[empresa_id]
    # Legacy events with unknown context and a commercial actor do not become
    # platform data merely because empresa_id was never written.
    if empresa_id is None:
        condiciones.append("(b.usuario_id IS NULL OR u.empresa_id IS NULL)")
    if usuario_id is not None: condiciones.append("b.usuario_id=%s");params.append(usuario_id)
    for campo,valor in [('accion',accion),('modulo',modulo)]:
        if valor: condiciones.append("UPPER(b."+campo+") LIKE UPPER(%s)");params.append('%'+valor+'%')
    if resultado: condiciones.append("b.resultado=%s");params.append(resultado.upper())
    if fecha_desde: condiciones.append("b.fecha>=%s::timestamptz");params.append(fecha_desde)
    if fecha_hasta: condiciones.append("b.fecha<=%s::timestamptz");params.append(fecha_hasta)
    return " WHERE "+" AND ".join(condiciones),params

_CAMPOS="""b.id,b.usuario_id,u.username usuario_username,u.nombre usuario_nombre,u.apellido usuario_apellido,
    u.correo usuario_correo,b.accion,b.modulo,b.descripcion,b.resultado,b.direccion_ip::text direccion_ip,
    b.user_agent,b.fecha,b.empresa_id,b.objetivo_usuario_id,b.empresa_afectada_id"""
_FROM=" FROM bitacora b LEFT JOIN usuario u ON u.id=b.usuario_id "

def consultar_bitacora(empresa_id,pagina=1,por_pagina=50,**filtros):
    from app.modules.autenticacion.repositories.perfil_repository import _transaccion
    where,params=_filtros(empresa_id,**filtros)
    with _transaccion() as cur:
        cur.connection.set_session(isolation_level='REPEATABLE READ',readonly=True)
        cur.execute("SELECT count(*) total"+_FROM+where,params)
        total=cur.fetchone()['total']
        cur.execute("SELECT "+_CAMPOS+_FROM+where+" ORDER BY b.fecha DESC,b.id DESC LIMIT %s OFFSET %s",
            params+[por_pagina,(pagina-1)*por_pagina])
        return [dict(r) for r in cur.fetchall()],total

def listar_bitacora(empresa_id,pagina=1,por_pagina=50,**filtros):
    return consultar_bitacora(empresa_id,pagina,por_pagina,**filtros)[0]

def contar_bitacora(empresa_id,**filtros):
    return consultar_bitacora(empresa_id,por_pagina=1,**filtros)[1]

def obtener_registro_bitacora(registro_id,empresa_id):
    from app.modules.autenticacion.repositories.perfil_repository import _transaccion
    where,params=_filtros(empresa_id)
    with _transaccion() as cur:
        cur.execute("SELECT "+_CAMPOS+_FROM+where+" AND b.id=%s",params+[registro_id])
        fila=cur.fetchone()
        return dict(fila) if fila else None

def opciones_bitacora(empresa_id):
    from app.modules.autenticacion.repositories.perfil_repository import _transaccion
    where,params=_filtros(empresa_id)
    with _transaccion() as cur:
        cur.execute("SELECT DISTINCT b.modulo"+_FROM+where+" ORDER BY b.modulo",params)
        modulos=[r['modulo'] for r in cur.fetchall()]
        cur.execute("SELECT DISTINCT b.usuario_id id,u.username nombre"+_FROM+where+" AND u.id IS NOT NULL ORDER BY u.username",params)
        return {'modulos':modulos,'actores':[dict(r) for r in cur.fetchall()]}
