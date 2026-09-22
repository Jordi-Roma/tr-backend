from psycopg2.extras import RealDictCursor

from app.database.connection import get_connection


def listar_promociones() -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, descripcion, tipo_descuento, valor, fecha_inicio,
                   fecha_fin, activo, fecha_creacion
            FROM promocion
            ORDER BY fecha_creacion DESC, id DESC;
            """
        )
        promociones = [dict(row) for row in cursor.fetchall()]
        for promocion in promociones:
            promocion["productos"] = obtener_productos_promocion(int(promocion["id"]), cursor)
            promocion["sucursales"] = obtener_sucursales_promocion(int(promocion["id"]), cursor)
        return promociones
    finally:
        cursor.close()
        connection.close()


def obtener_promocion_por_id(promocion_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, descripcion, tipo_descuento, valor, fecha_inicio,
                   fecha_fin, activo, fecha_creacion
            FROM promocion
            WHERE id = %s
            LIMIT 1;
            """,
            (promocion_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        promocion = dict(row)
        promocion["productos"] = obtener_productos_promocion(promocion_id, cursor)
        promocion["sucursales"] = obtener_sucursales_promocion(promocion_id, cursor)
        return promocion
    finally:
        cursor.close()
        connection.close()


def crear_promocion(
    nombre: str,
    descripcion: str | None,
    tipo_descuento: str,
    valor,
    fecha_inicio,
    fecha_fin,
    producto_ids: list[int],
    sucursal_ids: list[int],
) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            INSERT INTO promocion (nombre, descripcion, tipo_descuento, valor, fecha_inicio, fecha_fin)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (nombre, descripcion, tipo_descuento, valor, fecha_inicio, fecha_fin),
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError("No se pudo crear la promocion.")
        promocion_id = int(row["id"])
        reemplazar_relaciones(cursor, promocion_id, producto_ids, sucursal_ids)
        connection.commit()

        promocion = obtener_promocion_por_id(promocion_id)
        if promocion is None:
            raise ValueError("No se pudo recuperar la promocion creada.")
        return promocion
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def actualizar_promocion(
    promocion_id: int,
    nombre: str,
    descripcion: str | None,
    tipo_descuento: str,
    valor,
    fecha_inicio,
    fecha_fin,
    producto_ids: list[int],
    sucursal_ids: list[int],
) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE promocion
            SET nombre = %s,
                descripcion = %s,
                tipo_descuento = %s,
                valor = %s,
                fecha_inicio = %s,
                fecha_fin = %s
            WHERE id = %s
            RETURNING id;
            """,
            (nombre, descripcion, tipo_descuento, valor, fecha_inicio, fecha_fin, promocion_id),
        )
        if cursor.fetchone() is None:
            connection.rollback()
            return None
        reemplazar_relaciones(cursor, promocion_id, producto_ids, sucursal_ids)
        connection.commit()
        return obtener_promocion_por_id(promocion_id)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def cambiar_estado_promocion(promocion_id: int, activo: bool) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE promocion
            SET activo = %s
            WHERE id = %s
            RETURNING id;
            """,
            (activo, promocion_id),
        )
        if cursor.fetchone() is None:
            connection.rollback()
            return None
        connection.commit()
        return obtener_promocion_por_id(promocion_id)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def reemplazar_relaciones(cursor, promocion_id: int, producto_ids: list[int], sucursal_ids: list[int]) -> None:
    cursor.execute("DELETE FROM promocion_producto WHERE promocion_id = %s", (promocion_id,))
    for producto_id in producto_ids:
        cursor.execute(
            """
            INSERT INTO promocion_producto (promocion_id, producto_id)
            VALUES (%s, %s);
            """,
            (promocion_id, producto_id),
        )

    cursor.execute("DELETE FROM promocion_sucursal WHERE promocion_id = %s", (promocion_id,))
    for sucursal_id in sucursal_ids:
        cursor.execute(
            """
            INSERT INTO promocion_sucursal (promocion_id, sucursal_id)
            VALUES (%s, %s);
            """,
            (promocion_id, sucursal_id),
        )


def obtener_productos_promocion(promocion_id: int, cursor) -> list[dict[str, object]]:
    cursor.execute(
        """
        SELECT p.id, p.nombre
        FROM promocion_producto pp
        JOIN producto p ON p.id = pp.producto_id
        WHERE pp.promocion_id = %s
        ORDER BY p.nombre ASC;
        """,
        (promocion_id,),
    )
    return [dict(row) for row in cursor.fetchall()]


def obtener_sucursales_promocion(promocion_id: int, cursor) -> list[dict[str, object]]:
    cursor.execute(
        """
        SELECT s.id, s.nombre, c.nombre AS ciudad
        FROM promocion_sucursal ps
        JOIN sucursal s ON s.id = ps.sucursal_id
        JOIN ciudad c ON c.id = s.ciudad_id
        WHERE ps.promocion_id = %s
        ORDER BY c.nombre ASC, s.nombre ASC;
        """,
        (promocion_id,),
    )
    return [dict(row) for row in cursor.fetchall()]
