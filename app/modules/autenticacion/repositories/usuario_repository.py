from psycopg2.extras import RealDictCursor

from app.database.connection import get_connection
from app.modules.autenticacion.entities.usuario_entity import UsuarioEntity


def obtener_usuario_por_correo(correo: str) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, apellido, username, correo, password_hash, activo
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


def obtener_usuario_por_username(username: str) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, apellido, username, correo, password_hash, activo
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


def obtener_usuario_por_id(usuario_id: int) -> dict[str, object] | None:
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
                ) AS roles
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


def obtener_rol_por_nombre(nombre: str) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, descripcion, activo
            FROM rol
            WHERE nombre = %s AND activo = TRUE
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


def crear_usuario_cliente(
    usuario: UsuarioEntity,
    telefono: str | None,
) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre
            FROM rol
            WHERE nombre = %s AND activo = TRUE
            LIMIT 1;
            """,
            ("CLIENTE",),
        )
        rol = cursor.fetchone()

        if rol is None:
            raise ValueError("El rol CLIENTE no existe.")

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
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, nombre, apellido, username, correo;
            """,
            (
                usuario.nombre,
                usuario.apellido,
                usuario.username,
                usuario.correo,
                usuario.password_hash,
                usuario.activo,
            ),
        )
        usuario_creado = cursor.fetchone()

        if usuario_creado is None:
            raise ValueError("No se pudo crear el usuario.")

        usuario_id = usuario_creado["id"]
        rol_id = rol["id"]

        cursor.execute(
            """
            INSERT INTO cliente (usuario_id, telefono)
            VALUES (%s, %s);
            """,
            (usuario_id, telefono),
        )

        cursor.execute(
            """
            INSERT INTO usuario_rol (usuario_id, rol_id)
            VALUES (%s, %s);
            """,
            (usuario_id, rol_id),
        )

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
                "REGISTRO_CLIENTE",
                "AUTENTICACION",
                "Registro de cliente en el sistema",
                "EXITOSO",
            ),
        )

        connection.commit()

        resultado = dict(usuario_creado)
        resultado["rol"] = rol["nombre"]

        return resultado
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()
