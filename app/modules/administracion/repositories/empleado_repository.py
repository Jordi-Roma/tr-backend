from psycopg2.extras import RealDictCursor

from app.database.connection import get_connection

ROLES_LABORALES = ("CAJERO", "ENCARGADO_SUCURSAL", "PERSONAL_VENTAS")


def obtener_empleado_activo_por_usuario_id(
    usuario_id: int,
) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, usuario_id, sucursal_id, codigo_empleado, cargo, activo
            FROM empleado
            WHERE usuario_id = %s
                AND activo = TRUE
            LIMIT 1;
            """,
            (usuario_id,),
        )
        empleado = cursor.fetchone()

        if empleado is None:
            return None

        return dict(empleado)
    finally:
        cursor.close()
        connection.close()


def listar_empleados(sucursal_id: int | None = None) -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        parametros: tuple[object, ...] = ()
        filtro_sucursal = ""

        if sucursal_id is not None:
            filtro_sucursal = "AND e.sucursal_id = %s"
            parametros = (sucursal_id,)

        cursor.execute(
            f"""
            SELECT
                e.id AS empleado_id,
                u.id AS usuario_id,
                u.nombre,
                u.apellido,
                u.username,
                u.correo,
                s.id AS sucursal_id,
                s.nombre AS sucursal_nombre,
                e.codigo_empleado,
                e.cargo,
                e.fecha_ingreso,
                e.activo,
                COALESCE(
                    array_agg(r.nombre) FILTER (WHERE r.nombre IS NOT NULL),
                    ARRAY[]::VARCHAR[]
                ) AS roles
            FROM empleado e
            INNER JOIN usuario u ON u.id = e.usuario_id
            INNER JOIN sucursal s ON s.id = e.sucursal_id
            LEFT JOIN usuario_rol ur
                ON ur.usuario_id = u.id
                AND ur.activo = TRUE
            LEFT JOIN rol r
                ON r.id = ur.rol_id
                AND r.activo = TRUE
            WHERE e.activo = TRUE
                AND u.activo = TRUE
                AND s.activo = TRUE
                {filtro_sucursal}
            GROUP BY
                e.id,
                u.id,
                u.nombre,
                u.apellido,
                u.username,
                u.correo,
                s.id,
                s.nombre,
                e.codigo_empleado,
                e.cargo,
                e.fecha_ingreso,
                e.activo
            ORDER BY e.id ASC;
            """,
            parametros,
        )
        return [dict(empleado) for empleado in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def obtener_empleado_por_id(empleado_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT
                e.id AS empleado_id,
                u.id AS usuario_id,
                u.nombre,
                u.apellido,
                u.username,
                u.correo,
                s.id AS sucursal_id,
                s.nombre AS sucursal_nombre,
                e.codigo_empleado,
                e.cargo,
                e.fecha_ingreso,
                e.activo,
                COALESCE(
                    array_agg(r.nombre) FILTER (WHERE r.nombre IS NOT NULL),
                    ARRAY[]::VARCHAR[]
                ) AS roles
            FROM empleado e
            INNER JOIN usuario u ON u.id = e.usuario_id
            INNER JOIN sucursal s ON s.id = e.sucursal_id
            LEFT JOIN usuario_rol ur
                ON ur.usuario_id = u.id
                AND ur.activo = TRUE
            LEFT JOIN rol r
                ON r.id = ur.rol_id
                AND r.activo = TRUE
            WHERE e.id = %s
            GROUP BY
                e.id,
                u.id,
                u.nombre,
                u.apellido,
                u.username,
                u.correo,
                s.id,
                s.nombre,
                e.codigo_empleado,
                e.cargo,
                e.fecha_ingreso,
                e.activo
            LIMIT 1;
            """,
            (empleado_id,),
        )
        empleado = cursor.fetchone()

        if empleado is None:
            return None

        return dict(empleado)
    finally:
        cursor.close()
        connection.close()


def obtener_usuario_por_id(usuario_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, apellido, username, correo, activo
            FROM usuario
            WHERE id = %s
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


def obtener_sucursal_por_id(sucursal_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, direccion, telefono, activo
            FROM sucursal
            WHERE id = %s
            LIMIT 1;
            """,
            (sucursal_id,),
        )
        sucursal = cursor.fetchone()

        if sucursal is None:
            return None

        return dict(sucursal)
    finally:
        cursor.close()
        connection.close()


def obtener_rol_por_nombre(nombre: str) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, activo
            FROM rol
            WHERE nombre = %s
            LIMIT 1;
            """,
            (nombre,),
        )
        rol = cursor.fetchone()

        if rol is None:
            return None

        return dict(rol)
    finally:
        cursor.close()
        connection.close()


def usuario_tiene_empleado_activo(usuario_id: int) -> bool:
    return obtener_empleado_activo_por_usuario_id(usuario_id) is not None


def crear_empleado_usuario_existente(
    usuario_id: int,
    sucursal_id: int,
    codigo_empleado: str,
    cargo: str,
    rol_id: int,
    usuario_admin_id: int,
) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            INSERT INTO empleado (usuario_id, sucursal_id, codigo_empleado, cargo)
            VALUES (%s, %s, %s, %s)
            RETURNING id;
            """,
            (usuario_id, sucursal_id, codigo_empleado, cargo),
        )
        empleado = cursor.fetchone()

        asignar_rol_con_cursor(cursor, usuario_id, rol_id)
        registrar_bitacora_con_cursor(
            cursor,
            usuario_admin_id,
            "REGISTRO_EMPLEADO",
            "Registro de empleado usando usuario existente.",
        )

        connection.commit()
        return obtener_empleado_por_id(int(empleado["id"]))
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def crear_usuario_empleado(
    nombre: str,
    apellido: str,
    username: str,
    correo: str,
    password_hash: str,
    sucursal_id: int,
    codigo_empleado: str,
    cargo: str,
    rol_id: int,
    usuario_admin_id: int,
) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            INSERT INTO usuario (
                nombre,
                apellido,
                username,
                correo,
                password_hash,
                activo
            )
            VALUES (%s, %s, %s, %s, %s, TRUE)
            RETURNING id;
            """,
            (nombre, apellido, username, correo, password_hash),
        )
        usuario = cursor.fetchone()
        usuario_id = int(usuario["id"])

        cursor.execute(
            """
            INSERT INTO empleado (usuario_id, sucursal_id, codigo_empleado, cargo)
            VALUES (%s, %s, %s, %s)
            RETURNING id;
            """,
            (usuario_id, sucursal_id, codigo_empleado, cargo),
        )
        empleado = cursor.fetchone()

        asignar_rol_con_cursor(cursor, usuario_id, rol_id)
        registrar_bitacora_con_cursor(
            cursor,
            usuario_admin_id,
            "REGISTRO_EMPLEADO",
            "Registro de usuario nuevo como empleado.",
        )

        connection.commit()
        return obtener_empleado_por_id(int(empleado["id"]))
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def actualizar_empleado(
    empleado_id: int,
    sucursal_id: int,
    codigo_empleado: str,
    cargo: str,
    rol_id: int,
    usuario_admin_id: int,
) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE empleado
            SET sucursal_id = %s,
                codigo_empleado = %s,
                cargo = %s
            WHERE id = %s
                AND activo = TRUE
            RETURNING usuario_id;
            """,
            (sucursal_id, codigo_empleado, cargo, empleado_id),
        )
        empleado = cursor.fetchone()

        if empleado is None:
            connection.rollback()
            return None

        usuario_id = int(empleado["usuario_id"])
        desactivar_roles_laborales_con_cursor(cursor, usuario_id)
        asignar_rol_con_cursor(cursor, usuario_id, rol_id)
        registrar_bitacora_con_cursor(
            cursor,
            usuario_admin_id,
            "ACTUALIZACION_EMPLEADO",
            "Actualizacion de empleado.",
        )

        connection.commit()
        return obtener_empleado_por_id(empleado_id)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def desactivar_empleado(empleado_id: int, usuario_admin_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE empleado
            SET activo = FALSE
            WHERE id = %s
                AND activo = TRUE
            RETURNING usuario_id;
            """,
            (empleado_id,),
        )
        empleado = cursor.fetchone()

        if empleado is None:
            connection.rollback()
            return False

        desactivar_roles_laborales_con_cursor(cursor, int(empleado["usuario_id"]))
        registrar_bitacora_con_cursor(
            cursor,
            usuario_admin_id,
            "DESACTIVACION_EMPLEADO",
            "Desactivacion de empleado.",
        )

        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def activar_empleado(
    empleado_id: int,
    rol_id: int,
    usuario_admin_id: int,
) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE empleado
            SET activo = TRUE
            WHERE id = %s
            RETURNING usuario_id;
            """,
            (empleado_id,),
        )
        empleado = cursor.fetchone()

        if empleado is None:
            connection.rollback()
            return None

        usuario_id = int(empleado["usuario_id"])
        desactivar_roles_laborales_con_cursor(cursor, usuario_id)
        asignar_rol_con_cursor(cursor, usuario_id, rol_id)
        registrar_bitacora_con_cursor(
            cursor,
            usuario_admin_id,
            "ACTIVACION_EMPLEADO",
            "Activacion de empleado.",
        )

        connection.commit()
        return obtener_empleado_por_id(empleado_id)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def asignar_rol_con_cursor(
    cursor: RealDictCursor,
    usuario_id: int,
    rol_id: int,
) -> None:
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


def desactivar_rol_laboral_usuario(usuario_id: int, rol_id: int) -> None:
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
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def desactivar_roles_laborales_con_cursor(
    cursor: RealDictCursor,
    usuario_id: int,
) -> None:
    cursor.execute(
        """
        UPDATE usuario_rol ur
        SET activo = FALSE
        FROM rol r
        WHERE r.id = ur.rol_id
            AND ur.usuario_id = %s
            AND r.nombre = ANY(%s)
            AND ur.activo = TRUE;
        """,
        (usuario_id, list(ROLES_LABORALES)),
    )


def registrar_bitacora(
    usuario_id: int,
    accion: str,
    descripcion: str,
) -> None:
    connection = get_connection()
    cursor = connection.cursor()

    try:
        registrar_bitacora_con_cursor(cursor, usuario_id, accion, descripcion)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


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
            "ADMINISTRACION_COMERCIAL",
            descripcion,
            "EXITOSO",
        ),
    )
