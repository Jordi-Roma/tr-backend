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
                accion,
                modulo,
                descripcion,
                resultado,
                direccion_ip,
                user_agent
            )
            VALUES (%s, %s, %s, %s, %s, %s::INET, %s);
            """,
            (
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


def listar_bitacora(
    usuario_id: int | None = None,
    accion: str | None = None,
    modulo: str | None = None,
    resultado: str | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    pagina: int = 1,
    por_pagina: int = 50,
) -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        condiciones: list[str] = []
        params: list[object] = []

        if usuario_id is not None:
            condiciones.append("b.usuario_id = %s")
            params.append(usuario_id)

        if accion:
            condiciones.append("UPPER(b.accion) LIKE UPPER(%s)")
            params.append(f"%{accion}%")

        if modulo:
            condiciones.append("UPPER(b.modulo) LIKE UPPER(%s)")
            params.append(f"%{modulo}%")

        if resultado:
            condiciones.append("b.resultado = %s")
            params.append(resultado.upper())

        if fecha_desde:
            condiciones.append("b.fecha >= %s::TIMESTAMPTZ")
            params.append(fecha_desde)

        if fecha_hasta:
            condiciones.append("b.fecha <= %s::TIMESTAMPTZ")
            params.append(fecha_hasta)

        where = "WHERE " + " AND ".join(condiciones) if condiciones else ""
        offset = (pagina - 1) * por_pagina

        cursor.execute(
            f"""
            SELECT
                b.id,
                b.usuario_id,
                u.username AS usuario_username,
                u.nombre   AS usuario_nombre,
                u.apellido AS usuario_apellido,
                b.accion,
                b.modulo,
                b.descripcion,
                b.resultado,
                b.direccion_ip::TEXT AS direccion_ip,
                b.user_agent,
                b.fecha
            FROM bitacora b
            LEFT JOIN usuario u ON u.id = b.usuario_id
            {where}
            ORDER BY b.fecha DESC
            LIMIT %s OFFSET %s;
            """,
            params + [por_pagina, offset],
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def contar_bitacora(
    usuario_id: int | None = None,
    accion: str | None = None,
    modulo: str | None = None,
    resultado: str | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
) -> int:
    connection = get_connection()
    cursor = connection.cursor()

    try:
        condiciones: list[str] = []
        params: list[object] = []

        if usuario_id is not None:
            condiciones.append("b.usuario_id = %s")
            params.append(usuario_id)

        if accion:
            condiciones.append("UPPER(b.accion) LIKE UPPER(%s)")
            params.append(f"%{accion}%")

        if modulo:
            condiciones.append("UPPER(b.modulo) LIKE UPPER(%s)")
            params.append(f"%{modulo}%")

        if resultado:
            condiciones.append("b.resultado = %s")
            params.append(resultado.upper())

        if fecha_desde:
            condiciones.append("b.fecha >= %s::TIMESTAMPTZ")
            params.append(fecha_desde)

        if fecha_hasta:
            condiciones.append("b.fecha <= %s::TIMESTAMPTZ")
            params.append(fecha_hasta)

        where = "WHERE " + " AND ".join(condiciones) if condiciones else ""

        cursor.execute(
            f"""
            SELECT COUNT(*) FROM bitacora b {where};
            """,
            params,
        )
        result = cursor.fetchone()
        return int(result[0]) if result else 0
    finally:
        cursor.close()
        connection.close()


def obtener_registro_bitacora(registro_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT
                b.id,
                b.usuario_id,
                u.username  AS usuario_username,
                u.nombre    AS usuario_nombre,
                u.apellido  AS usuario_apellido,
                u.correo    AS usuario_correo,
                b.accion,
                b.modulo,
                b.descripcion,
                b.resultado,
                b.direccion_ip::TEXT AS direccion_ip,
                b.user_agent,
                b.fecha
            FROM bitacora b
            LEFT JOIN usuario u ON u.id = b.usuario_id
            WHERE b.id = %s
            LIMIT 1;
            """,
            (registro_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        cursor.close()
        connection.close()
