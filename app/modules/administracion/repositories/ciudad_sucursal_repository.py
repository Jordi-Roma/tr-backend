from psycopg2.extras import RealDictCursor

from app.database.connection import get_connection


def listar_ciudades() -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, departamento, activo
            FROM ciudad
            WHERE activo = TRUE
            ORDER BY nombre ASC;
            """
        )
        return [dict(ciudad) for ciudad in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def obtener_ciudad_por_id(ciudad_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, departamento, activo
            FROM ciudad
            WHERE id = %s
            LIMIT 1;
            """,
            (ciudad_id,),
        )
        ciudad = cursor.fetchone()

        if ciudad is None:
            return None

        return dict(ciudad)
    finally:
        cursor.close()
        connection.close()


def crear_ciudad(
    nombre: str,
    departamento: str | None,
    usuario_id: int,
) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            INSERT INTO ciudad (nombre, departamento)
            VALUES (%s, %s)
            RETURNING id, nombre, departamento, activo;
            """,
            (nombre, departamento),
        )
        ciudad = cursor.fetchone()

        registrar_bitacora_con_cursor(
            cursor,
            usuario_id,
            "CREACION_CIUDAD",
            "Creacion de ciudad.",
        )

        connection.commit()
        return dict(ciudad)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def actualizar_ciudad(
    ciudad_id: int,
    nombre: str,
    departamento: str | None,
    usuario_id: int,
) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE ciudad
            SET nombre = %s,
                departamento = %s
            WHERE id = %s
                AND activo = TRUE
            RETURNING id, nombre, departamento, activo;
            """,
            (nombre, departamento, ciudad_id),
        )
        ciudad = cursor.fetchone()

        if ciudad is None:
            connection.rollback()
            return None

        registrar_bitacora_con_cursor(
            cursor,
            usuario_id,
            "ACTUALIZACION_CIUDAD",
            "Actualizacion de ciudad.",
        )

        connection.commit()
        return dict(ciudad)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def desactivar_ciudad(ciudad_id: int, usuario_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE ciudad
            SET activo = FALSE
            WHERE id = %s
                AND activo = TRUE;
            """,
            (ciudad_id,),
        )
        desactivada = cursor.rowcount > 0

        if desactivada:
            registrar_bitacora_con_cursor(
                cursor,
                usuario_id,
                "DESACTIVACION_CIUDAD",
                "Desactivacion de ciudad.",
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


def activar_ciudad(ciudad_id: int, usuario_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE ciudad
            SET activo = TRUE
            WHERE id = %s;
            """,
            (ciudad_id,),
        )
        activada = cursor.rowcount > 0

        if activada:
            registrar_bitacora_con_cursor(
                cursor,
                usuario_id,
                "ACTIVACION_CIUDAD",
                "Activacion de ciudad.",
            )
            connection.commit()
        else:
            connection.rollback()

        return activada
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def ciudad_tiene_sucursales_activas(ciudad_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT 1
            FROM sucursal
            WHERE ciudad_id = %s
                AND activo = TRUE
            LIMIT 1;
            """,
            (ciudad_id,),
        )
        return cursor.fetchone() is not None
    finally:
        cursor.close()
        connection.close()


def listar_sucursales() -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT
                s.id,
                s.ciudad_id,
                c.nombre AS ciudad_nombre,
                c.activo AS ciudad_activa,
                s.nombre,
                s.direccion,
                s.telefono,
                s.latitud,
                s.longitud,
                s.activo
            FROM sucursal s
            INNER JOIN ciudad c
                ON c.id = s.ciudad_id
            WHERE s.activo = TRUE
                AND c.activo = TRUE
            ORDER BY s.id ASC;
            """
        )
        return [dict(sucursal) for sucursal in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def obtener_sucursal_por_id(sucursal_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT
                s.id,
                s.ciudad_id,
                c.nombre AS ciudad_nombre,
                c.activo AS ciudad_activa,
                s.nombre,
                s.direccion,
                s.telefono,
                s.latitud,
                s.longitud,
                s.activo
            FROM sucursal s
            INNER JOIN ciudad c
                ON c.id = s.ciudad_id
            WHERE s.id = %s
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


def crear_sucursal(
    ciudad_id: int,
    nombre: str,
    direccion: str,
    telefono: str | None,
    latitud,
    longitud,
    usuario_id: int,
) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            INSERT INTO sucursal (ciudad_id, nombre, direccion, telefono, latitud, longitud)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, ciudad_id, nombre, direccion, telefono, latitud, longitud, activo;
            """,
            (ciudad_id, nombre, direccion, telefono, latitud, longitud),
        )
        sucursal = cursor.fetchone()

        registrar_bitacora_con_cursor(
            cursor,
            usuario_id,
            "CREACION_SUCURSAL",
            "Creacion de sucursal.",
        )

        connection.commit()
        return obtener_sucursal_por_id(int(sucursal["id"]))
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def actualizar_sucursal(
    sucursal_id: int,
    ciudad_id: int,
    nombre: str,
    direccion: str,
    telefono: str | None,
    latitud,
    longitud,
    usuario_id: int,
) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE sucursal
            SET ciudad_id = %s,
                nombre = %s,
                direccion = %s,
                telefono = %s,
                latitud = %s,
                longitud = %s
            WHERE id = %s
                AND activo = TRUE
            RETURNING id;
            """,
            (ciudad_id, nombre, direccion, telefono, latitud, longitud, sucursal_id),
        )
        sucursal = cursor.fetchone()

        if sucursal is None:
            connection.rollback()
            return None

        registrar_bitacora_con_cursor(
            cursor,
            usuario_id,
            "ACTUALIZACION_SUCURSAL",
            "Actualizacion de sucursal.",
        )

        connection.commit()
        return obtener_sucursal_por_id(sucursal_id)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def desactivar_sucursal(sucursal_id: int, usuario_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE sucursal
            SET activo = FALSE
            WHERE id = %s
                AND activo = TRUE;
            """,
            (sucursal_id,),
        )
        desactivada = cursor.rowcount > 0

        if desactivada:
            registrar_bitacora_con_cursor(
                cursor,
                usuario_id,
                "DESACTIVACION_SUCURSAL",
                "Desactivacion de sucursal.",
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


def activar_sucursal(sucursal_id: int, usuario_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE sucursal
            SET activo = TRUE
            WHERE id = %s;
            """,
            (sucursal_id,),
        )
        activada = cursor.rowcount > 0

        if activada:
            registrar_bitacora_con_cursor(
                cursor,
                usuario_id,
                "ACTIVACION_SUCURSAL",
                "Activacion de sucursal.",
            )
            connection.commit()
        else:
            connection.rollback()

        return activada
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


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
