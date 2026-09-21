from psycopg2.extras import RealDictCursor

from app.database.connection import get_connection


def listar_proveedores() -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, nit, telefono, correo, direccion, activo, fecha_creacion
            FROM proveedor
            ORDER BY nombre ASC;
            """
        )
        return [dict(proveedor) for proveedor in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def obtener_proveedor_por_id(proveedor_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, nit, telefono, correo, direccion, activo, fecha_creacion
            FROM proveedor
            WHERE id = %s
            LIMIT 1;
            """,
            (proveedor_id,),
        )
        proveedor = cursor.fetchone()

        if proveedor is None:
            return None

        return dict(proveedor)
    finally:
        cursor.close()
        connection.close()


def obtener_proveedor_por_nit(nit: str) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nit
            FROM proveedor
            WHERE nit = %s
            LIMIT 1;
            """,
            (nit,),
        )
        proveedor = cursor.fetchone()

        if proveedor is None:
            return None

        return dict(proveedor)
    finally:
        cursor.close()
        connection.close()


def crear_proveedor(
    nombre: str,
    nit: str | None,
    telefono: str | None,
    correo: str | None,
    direccion: str | None,
) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            INSERT INTO proveedor (nombre, nit, telefono, correo, direccion)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, nombre, nit, telefono, correo, direccion, activo, fecha_creacion;
            """,
            (nombre, nit, telefono, correo, direccion),
        )
        proveedor = cursor.fetchone()
        connection.commit()
        return dict(proveedor)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def actualizar_proveedor(
    proveedor_id: int,
    nombre: str,
    telefono: str | None,
    correo: str | None,
    direccion: str | None,
) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE proveedor
            SET nombre = %s,
                telefono = %s,
                correo = %s,
                direccion = %s
            WHERE id = %s
            RETURNING id, nombre, nit, telefono, correo, direccion, activo, fecha_creacion;
            """,
            (nombre, telefono, correo, direccion, proveedor_id),
        )
        proveedor = cursor.fetchone()

        if proveedor is None:
            connection.rollback()
            return None

        connection.commit()
        return dict(proveedor)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def desactivar_proveedor(proveedor_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE proveedor
            SET activo = FALSE
            WHERE id = %s
                AND activo = TRUE
            RETURNING id;
            """,
            (proveedor_id,),
        )
        proveedor = cursor.fetchone()

        if proveedor is None:
            connection.rollback()
            return False

        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def activar_proveedor(proveedor_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE proveedor
            SET activo = TRUE
            WHERE id = %s
            RETURNING id, nombre, nit, telefono, correo, direccion, activo, fecha_creacion;
            """,
            (proveedor_id,),
        )
        proveedor = cursor.fetchone()

        if proveedor is None:
            connection.rollback()
            return None

        connection.commit()
        return dict(proveedor)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()
