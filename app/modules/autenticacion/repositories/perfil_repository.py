from psycopg2.extras import RealDictCursor

from app.database.connection import get_connection


def obtener_perfil_cliente(usuario_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT
                u.id,
                u.nombre,
                u.apellido,
                u.username,
                u.correo,
                c.telefono,
                COALESCE(
                    array_agg(r.nombre) FILTER (WHERE r.nombre IS NOT NULL),
                    ARRAY[]::VARCHAR[]
                ) AS roles
            FROM usuario u
            INNER JOIN cliente c
                ON c.usuario_id = u.id
                AND c.activo = TRUE
            LEFT JOIN usuario_rol ur
                ON ur.usuario_id = u.id
                AND ur.activo = TRUE
            LEFT JOIN rol r
                ON r.id = ur.rol_id
                AND r.activo = TRUE
            WHERE u.id = %s
                AND u.activo = TRUE
            GROUP BY
                u.id,
                u.nombre,
                u.apellido,
                u.username,
                u.correo,
                c.telefono
            LIMIT 1;
            """,
            (usuario_id,),
        )
        perfil = cursor.fetchone()

        if perfil is None:
            return None

        return dict(perfil)
    finally:
        cursor.close()
        connection.close()


def actualizar_perfil_cliente(
    usuario_id: int,
    nombre: str,
    apellido: str,
    telefono: str | None,
) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE usuario
            SET nombre = %s,
                apellido = %s
            WHERE id = %s
                AND activo = TRUE;
            """,
            (nombre, apellido, usuario_id),
        )

        cursor.execute(
            """
            UPDATE cliente
            SET telefono = %s
            WHERE usuario_id = %s
                AND activo = TRUE;
            """,
            (telefono, usuario_id),
        )

        if cursor.rowcount == 0:
            connection.rollback()
            return None

        registrar_bitacora_con_cursor(
            cursor,
            usuario_id,
            "ACTUALIZACION_PERFIL",
            "Actualizacion de perfil del cliente.",
        )

        connection.commit()
        return obtener_perfil_cliente(usuario_id)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def obtener_password_hash(usuario_id: int) -> str | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT password_hash
            FROM usuario
            WHERE id = %s
                AND activo = TRUE
            LIMIT 1;
            """,
            (usuario_id,),
        )
        usuario = cursor.fetchone()

        if usuario is None:
            return None

        return str(usuario["password_hash"])
    finally:
        cursor.close()
        connection.close()


def actualizar_password_hash(usuario_id: int, password_hash: str) -> bool:
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE usuario
            SET password_hash = %s
            WHERE id = %s
                AND activo = TRUE;
            """,
            (password_hash, usuario_id),
        )

        actualizado = cursor.rowcount > 0

        if actualizado:
            registrar_bitacora_con_cursor(
                cursor,
                usuario_id,
                "CAMBIO_PASSWORD",
                "Cambio de contrasena del cliente.",
            )
            connection.commit()
        else:
            connection.rollback()

        return actualizado
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def listar_direcciones_cliente(usuario_id: int) -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT
                dc.id,
                dc.ciudad_id,
                dc.direccion,
                dc.referencia,
                dc.es_principal
            FROM direccion_cliente dc
            INNER JOIN cliente c
                ON c.id = dc.cliente_id
            WHERE c.usuario_id = %s
                AND c.activo = TRUE
                AND dc.activo = TRUE
            ORDER BY dc.es_principal DESC, dc.id ASC;
            """,
            (usuario_id,),
        )
        direcciones = cursor.fetchall()

        return [dict(direccion) for direccion in direcciones]
    finally:
        cursor.close()
        connection.close()


def crear_direccion_cliente(
    usuario_id: int,
    ciudad_id: int,
    direccion: str,
    referencia: str | None,
    es_principal: bool,
) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cliente_id = obtener_cliente_id_con_cursor(cursor, usuario_id)

        if cliente_id is None:
            connection.rollback()
            return None

        if es_principal:
            quitar_direccion_principal_con_cursor(cursor, cliente_id)

        cursor.execute(
            """
            INSERT INTO direccion_cliente (
                cliente_id,
                ciudad_id,
                direccion,
                referencia,
                es_principal
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, ciudad_id, direccion, referencia, es_principal;
            """,
            (cliente_id, ciudad_id, direccion, referencia, es_principal),
        )
        direccion_creada = cursor.fetchone()

        registrar_bitacora_con_cursor(
            cursor,
            usuario_id,
            "CREACION_DIRECCION_CLIENTE",
            "Creacion de direccion del cliente.",
        )

        connection.commit()

        if direccion_creada is None:
            return None

        return dict(direccion_creada)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def actualizar_direccion_cliente(
    usuario_id: int,
    direccion_id: int,
    ciudad_id: int,
    direccion: str,
    referencia: str | None,
    es_principal: bool,
) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cliente_id = obtener_cliente_id_con_cursor(cursor, usuario_id)

        if cliente_id is None:
            connection.rollback()
            return None

        if es_principal:
            quitar_direccion_principal_con_cursor(cursor, cliente_id)

        cursor.execute(
            """
            UPDATE direccion_cliente
            SET ciudad_id = %s,
                direccion = %s,
                referencia = %s,
                es_principal = %s
            WHERE id = %s
                AND cliente_id = %s
                AND activo = TRUE
            RETURNING id, ciudad_id, direccion, referencia, es_principal;
            """,
            (
                ciudad_id,
                direccion,
                referencia,
                es_principal,
                direccion_id,
                cliente_id,
            ),
        )
        direccion_actualizada = cursor.fetchone()

        if direccion_actualizada is None:
            connection.rollback()
            return None

        registrar_bitacora_con_cursor(
            cursor,
            usuario_id,
            "ACTUALIZACION_DIRECCION_CLIENTE",
            "Actualizacion de direccion del cliente.",
        )

        connection.commit()
        return dict(direccion_actualizada)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def desactivar_direccion_cliente(usuario_id: int, direccion_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE direccion_cliente dc
            SET activo = FALSE
            FROM cliente c
            WHERE dc.cliente_id = c.id
                AND c.usuario_id = %s
                AND c.activo = TRUE
                AND dc.id = %s
                AND dc.activo = TRUE;
            """,
            (usuario_id, direccion_id),
        )
        desactivada = cursor.rowcount > 0

        if desactivada:
            registrar_bitacora_con_cursor(
                cursor,
                usuario_id,
                "DESACTIVACION_DIRECCION_CLIENTE",
                "Desactivacion de direccion del cliente.",
            )
            connection.commit()
        else:
            connection.rollback()

        return desactivada
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def obtener_cliente_id_con_cursor(cursor: RealDictCursor, usuario_id: int) -> int | None:
    cursor.execute(
        """
        SELECT id
        FROM cliente
        WHERE usuario_id = %s
            AND activo = TRUE
        LIMIT 1;
        """,
        (usuario_id,),
    )
    cliente = cursor.fetchone()

    if cliente is None:
        return None

    return int(cliente["id"])


def quitar_direccion_principal_con_cursor(
    cursor: RealDictCursor,
    cliente_id: int,
) -> None:
    cursor.execute(
        """
        UPDATE direccion_cliente
        SET es_principal = FALSE
        WHERE cliente_id = %s
            AND activo = TRUE;
        """,
        (cliente_id,),
    )


def registrar_bitacora_con_cursor(
    cursor: RealDictCursor,
    usuario_id: int,
    accion: str,
    descripcion: str,
) -> None:
    cursor.execute(
        """
        INSERT INTO bitacora (
            usuario_id,
            accion,
            modulo,
            descripcion,
            resultado
        )
        VALUES (%s, %s, %s, %s, %s);
        """,
        (
            usuario_id,
            accion,
            "AUTENTICACION",
            descripcion,
            "EXITOSO",
        ),
    )
