from decimal import Decimal
from psycopg2.extras import RealDictCursor
from app.database.connection import get_connection

def listar_variantes(producto_id: int | None = None) -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        query = """
            SELECT v.id, v.producto_id, p.nombre as producto_nombre,
                   v.talla_id, t.nombre as talla_nombre,
                   v.color_id, c.nombre as color_nombre,
                   v.sku, v.ancho_cm, v.largo_cm, v.activo, v.fecha_creacion
            FROM producto_variante v
            JOIN producto p ON v.producto_id = p.id
            LEFT JOIN talla t ON v.talla_id = t.id
            LEFT JOIN color c ON v.color_id = c.id
        """
        params = []
        if producto_id is not None:
            query += " WHERE v.producto_id = %s "
            params.append(producto_id)
            
        query += " ORDER BY v.id DESC;"
        
        cursor.execute(query, tuple(params))
        variantes = [dict(row) for row in cursor.fetchall()]
        
        for v in variantes:
            v['precios'] = obtener_precios_de_variante(v['id'], cursor)
            
        return variantes
    finally:
        cursor.close()
        connection.close()

def obtener_variante_por_id(variante_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT v.id, v.producto_id, p.nombre as producto_nombre,
                   v.talla_id, t.nombre as talla_nombre,
                   v.color_id, c.nombre as color_nombre,
                   v.sku, v.ancho_cm, v.largo_cm, v.activo, v.fecha_creacion
            FROM producto_variante v
            JOIN producto p ON v.producto_id = p.id
            LEFT JOIN talla t ON v.talla_id = t.id
            LEFT JOIN color c ON v.color_id = c.id
            WHERE v.id = %s
            LIMIT 1;
            """,
            (variante_id,)
        )
        row = cursor.fetchone()
        
        if row is None:
            return None
            
        variante = dict(row)
        variante['precios'] = obtener_precios_de_variante(variante_id, cursor)
        return variante
    finally:
        cursor.close()
        connection.close()

def obtener_precios_de_variante(variante_id: int, cursor) -> list[dict[str, object]]:
    cursor.execute(
        """
        SELECT id, producto_variante_id as variante_id, precio as monto, fecha_inicio, fecha_fin, activo, fecha_creacion
        FROM precio_producto
        WHERE producto_variante_id = %s
        ORDER BY fecha_inicio DESC, id DESC
        """,
        (variante_id,)
    )
    return [dict(row) for row in cursor.fetchall()]

def crear_variante(
    producto_id: int,
    talla_id: int | None,
    color_id: int | None,
    sku: str,
    ancho_cm: float | None = None,
    largo_cm: float | None = None,
) -> int:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            INSERT INTO producto_variante (producto_id, talla_id, color_id, sku, ancho_cm, largo_cm)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (producto_id, talla_id, color_id, sku, ancho_cm, largo_cm),
        )
        variante_id = cursor.fetchone()["id"]
        connection.commit()
        return variante_id
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

def actualizar_variante(
    variante_id: int,
    talla_id: int | None,
    color_id: int | None,
    sku: str,
    ancho_cm: float | None = None,
    largo_cm: float | None = None,
) -> bool:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE producto_variante
            SET talla_id = %s, color_id = %s, sku = %s, ancho_cm = %s, largo_cm = %s
            WHERE id = %s
            RETURNING id;
            """,
            (talla_id, color_id, sku, ancho_cm, largo_cm, variante_id),
        )
        if cursor.fetchone() is None:
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

def desactivar_variante(variante_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE producto_variante
            SET activo = FALSE
            WHERE id = %s AND activo = TRUE
            RETURNING id;
            """,
            (variante_id,),
        )
        if cursor.fetchone() is None:
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

def activar_variante(variante_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE producto_variante
            SET activo = TRUE
            WHERE id = %s
            RETURNING id;
            """,
            (variante_id,),
        )
        if cursor.fetchone() is None:
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

def asignar_precio(variante_id: int, monto: Decimal, fecha_inicio: object | None, fecha_fin: object | None) -> int:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        # Desactivar precio actual
        cursor.execute(
            "UPDATE precio_producto SET activo = FALSE WHERE producto_variante_id = %s",
            (variante_id,)
        )
            
        cursor.execute(
            """
            INSERT INTO precio_producto (producto_variante_id, precio, fecha_inicio, fecha_fin)
            VALUES (%s, %s, %s, %s)
            RETURNING id;
            """,
            (variante_id, monto, fecha_inicio, fecha_fin),
        )
        precio_id = cursor.fetchone()["id"]
        connection.commit()
        return precio_id
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()
