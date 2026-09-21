from psycopg2.extras import RealDictCursor

from app.database.connection import get_connection


def crear_usuario_con_rol(
    nombre: str,
    apellido: str,
    username: str,
    correo: str,
    password_hash: str,
    rol_id: int,
    usuario_id_admin: int,
) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            INSERT INTO usuario (nombre, apellido, username, correo, password_hash)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (nombre, apellido, username, correo, password_hash),
        )
        usuario = cursor.fetchone()
        if usuario is None:
            raise ValueError("No se pudo crear el usuario.")

        usuario_id = int(usuario["id"])
        cursor.execute(
            """
            INSERT INTO usuario_rol (usuario_id, rol_id, activo)
            VALUES (%s, %s, TRUE);
            """,
            (usuario_id, rol_id),
        )
        registrar_bitacora_con_cursor(
            cursor,
            usuario_id_admin,
            "CREACION_USUARIO",
            f"Creacion de usuario id={usuario_id}.",
        )
        connection.commit()
        resultado = obtener_usuario_admin_por_id(usuario_id)
        if resultado is None:
            raise ValueError("No se pudo recuperar el usuario creado.")
        return resultado
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def listar_usuarios() -> list[dict[str, object]]:
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
                u.activo,
                COALESCE(
                    array_agg(r.nombre) FILTER (WHERE r.nombre IS NOT NULL),
                    ARRAY[]::VARCHAR[]
                ) AS roles,
                EXISTS (
                    SELECT 1
                    FROM cliente c
                    WHERE c.usuario_id = u.id
                        AND c.activo = TRUE
                ) AS es_cliente,
                EXISTS (
                    SELECT 1
                    FROM empleado e
                    WHERE e.usuario_id = u.id
                        AND e.activo = TRUE
                ) AS es_empleado
            FROM usuario u
            LEFT JOIN usuario_rol ur
                ON ur.usuario_id = u.id
                AND ur.activo = TRUE
            LEFT JOIN rol r
                ON r.id = ur.rol_id
                AND r.activo = TRUE
            WHERE u.activo = TRUE
            GROUP BY
                u.id,
                u.nombre,
                u.apellido,
                u.username,
                u.correo,
                u.activo
            ORDER BY u.id ASC;
            """
        )
        return [dict(usuario) for usuario in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def obtener_usuario_admin_por_id(usuario_id: int) -> dict[str, object] | None:
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
                u.activo,
                COALESCE(
                    array_agg(r.nombre) FILTER (WHERE r.nombre IS NOT NULL),
                    ARRAY[]::VARCHAR[]
                ) AS roles,
                EXISTS (
                    SELECT 1
                    FROM cliente c
                    WHERE c.usuario_id = u.id
                        AND c.activo = TRUE
                ) AS es_cliente,
                EXISTS (
                    SELECT 1
                    FROM empleado e
                    WHERE e.usuario_id = u.id
                        AND e.activo = TRUE
                ) AS es_empleado
            FROM usuario u
            LEFT JOIN usuario_rol ur
                ON ur.usuario_id = u.id
                AND ur.activo = TRUE
            LEFT JOIN rol r
                ON r.id = ur.rol_id
                AND r.activo = TRUE
            WHERE u.id = %s
            GROUP BY
                u.id,
                u.nombre,
                u.apellido,
                u.username,
                u.correo,
                u.activo
            LIMIT 1;
            """,
            (usuario_id,),
        )
        usuario = cursor.fetchone()

        if usuario is None:
            return None

        return dict(usuario)
    finally:
        cursor.close()
        connection.close()


def obtener_usuario_por_username(username: str) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, username
            FROM usuario
            WHERE username = %s
            LIMIT 1;
            """,
            (username,),
        )
        usuario = cursor.fetchone()

        if usuario is None:
            return None

        return dict(usuario)
    finally:
        cursor.close()
        connection.close()


def obtener_usuario_por_correo(correo: str) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, correo
            FROM usuario
            WHERE lower(correo) = lower(%s)
            LIMIT 1;
            """,
            (correo,),
        )
        usuario = cursor.fetchone()

        if usuario is None:
            return None

        return dict(usuario)
    finally:
        cursor.close()
        connection.close()


def actualizar_usuario(
    usuario_id: int,
    nombre: str,
    apellido: str,
    username: str,
    correo: str,
    usuario_id_admin: int,
) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE usuario
            SET nombre = %s,
                apellido = %s,
                username = %s,
                correo = %s
            WHERE id = %s
                AND activo = TRUE
            RETURNING id;
            """,
            (nombre, apellido, username, correo, usuario_id),
        )
        usuario = cursor.fetchone()

        if usuario is None:
            connection.rollback()
            return None

        registrar_bitacora_con_cursor(
            cursor,
            usuario_id_admin,
            "ACTUALIZACION_USUARIO",
            "Actualizacion de usuario.",
        )

        connection.commit()
        return obtener_usuario_admin_por_id(usuario_id)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def desactivar_usuario(usuario_id: int, usuario_id_admin: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE usuario
            SET activo = FALSE
            WHERE id = %s
                AND activo = TRUE;
            """,
            (usuario_id,),
        )
        desactivado = cursor.rowcount > 0

        if desactivado:
            registrar_bitacora_con_cursor(
                cursor,
                usuario_id_admin,
                "DESACTIVACION_USUARIO",
                "Desactivacion de usuario.",
            )
            connection.commit()
        else:
            connection.rollback()

        return desactivado
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def activar_usuario(usuario_id: int, usuario_id_admin: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE usuario
            SET activo = TRUE
            WHERE id = %s;
            """,
            (usuario_id,),
        )
        activado = cursor.rowcount > 0

        if activado:
            registrar_bitacora_con_cursor(
                cursor,
                usuario_id_admin,
                "ACTIVACION_USUARIO",
                "Activacion de usuario.",
            )
            connection.commit()
        else:
            connection.rollback()

        return activado
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def obtener_rol_por_id(rol_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, activo
            FROM rol
            WHERE id = %s
            LIMIT 1;
            """,
            (rol_id,),
        )
        rol = cursor.fetchone()

        if rol is None:
            return None

        return dict(rol)
    finally:
        cursor.close()
        connection.close()


def asignar_rol_a_usuario(
    usuario_id: int,
    rol_id: int,
    usuario_id_admin: int,
) -> bool:
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE usuario_rol
            SET activo = TRUE
            WHERE usuario_id = %s
                AND rol_id = %s;
            """,
            (usuario_id, rol_id),
        )

        if cursor.rowcount == 0:
            cursor.execute(
                """
                INSERT INTO usuario_rol (usuario_id, rol_id, activo)
                VALUES (%s, %s, TRUE);
                """,
                (usuario_id, rol_id),
            )

        registrar_bitacora_con_cursor(
            cursor,
            usuario_id_admin,
            "ASIGNACION_ROL_USUARIO",
            "Asignacion de rol a usuario.",
        )

        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def desactivar_rol_de_usuario(
    usuario_id: int,
    rol_id: int,
    usuario_id_admin: int,
) -> bool:
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE usuario_rol
            SET activo = FALSE
            WHERE usuario_id = %s
                AND rol_id = %s
                AND activo = TRUE;
            """,
            (usuario_id, rol_id),
        )
        desactivado = cursor.rowcount > 0

        if desactivado:
            registrar_bitacora_con_cursor(
                cursor,
                usuario_id_admin,
                "DESACTIVACION_ROL_USUARIO",
                "Desactivacion de rol del usuario.",
            )
            connection.commit()
        else:
            connection.rollback()

        return desactivado
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def activar_rol_de_usuario(
    usuario_id: int,
    rol_id: int,
    usuario_id_admin: int,
) -> bool:
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE usuario_rol
            SET activo = TRUE
            WHERE usuario_id = %s
                AND rol_id = %s;
            """,
            (usuario_id, rol_id),
        )

        if cursor.rowcount == 0:
            cursor.execute(
                """
                INSERT INTO usuario_rol (usuario_id, rol_id, activo)
                VALUES (%s, %s, TRUE);
                """,
                (usuario_id, rol_id),
            )

        registrar_bitacora_con_cursor(
            cursor,
            usuario_id_admin,
            "ACTIVACION_ROL_USUARIO",
            "Activacion de rol del usuario.",
        )

        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def registrar_bitacora(
    usuario_id_admin: int,
    accion: str,
    descripcion: str,
) -> None:
    connection = get_connection()
    cursor = connection.cursor()

    try:
        registrar_bitacora_con_cursor(
            cursor,
            usuario_id_admin,
            accion,
            descripcion,
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def registrar_bitacora_con_cursor(
    cursor: RealDictCursor,
    usuario_id_admin: int,
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
            usuario_id_admin,
            accion,
            "AUTENTICACION",
            descripcion,
            "EXITOSO",
        ),
    )
