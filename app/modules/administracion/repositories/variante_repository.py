from decimal import Decimal
from psycopg2.extras import RealDictCursor
from app.database.connection import get_connection

def listar_variantes(empresa_id: int, producto_id: int | None = None) -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        query = """
            SELECT v.id, v.producto_id, p.nombre as producto_nombre,
                   v.talla_id, t.nombre as talla_nombre,
                   v.color_id, c.nombre as color_nombre,
                   v.sku, v.ancho_cm, v.largo_cm, v.activo, v.fecha_creacion
            FROM producto_variante v
            JOIN producto p ON v.producto_id = p.id AND p.empresa_id = v.empresa_id
            LEFT JOIN talla t ON v.talla_id = t.id AND t.empresa_id = v.empresa_id
            LEFT JOIN color c ON v.color_id = c.id AND c.empresa_id = v.empresa_id
            WHERE v.empresa_id = %s
        """
        params = [empresa_id]
        if producto_id is not None:
            query += " AND v.producto_id = %s "
            params.append(producto_id)
            
        query += " ORDER BY v.id DESC;"
        
        cursor.execute(query, tuple(params))
        variantes = [dict(row) for row in cursor.fetchall()]
        
        for v in variantes:
            v['precios'] = obtener_precios_de_variante(v['id'], empresa_id, cursor)
            
        return variantes
    finally:
        cursor.close()
        connection.close()

def obtener_variante_por_id(variante_id: int, empresa_id: int) -> dict[str, object] | None:
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
            JOIN producto p ON v.producto_id = p.id AND p.empresa_id = v.empresa_id
            LEFT JOIN talla t ON v.talla_id = t.id AND t.empresa_id = v.empresa_id
            LEFT JOIN color c ON v.color_id = c.id AND c.empresa_id = v.empresa_id
            WHERE v.id = %s AND v.empresa_id = %s
            LIMIT 1;
            """,
            (variante_id, empresa_id)
        )
        row = cursor.fetchone()
        
        if row is None:
            return None
            
        variante = dict(row)
        variante['precios'] = obtener_precios_de_variante(variante_id, empresa_id, cursor)
        return variante
    finally:
        cursor.close()
        connection.close()

def obtener_precios_de_variante(variante_id: int, empresa_id: int, cursor) -> list[dict[str, object]]:
    cursor.execute(
        """
        SELECT id, producto_variante_id as variante_id, precio as monto, fecha_inicio, fecha_fin, activo, fecha_creacion
        FROM precio_producto
        WHERE producto_variante_id = %s AND empresa_id = %s
        ORDER BY fecha_inicio DESC, id DESC
        """,
        (variante_id, empresa_id)
    )
    return [dict(row) for row in cursor.fetchall()]


def _validar_referencias_variante(cursor, empresa_id: int, talla_id: int | None, color_id: int | None) -> None:
    for tabla, registro_id in (("talla", talla_id), ("color", color_id)):
        if registro_id is None:
            continue
        cursor.execute(
            f"SELECT 1 FROM {tabla} WHERE id = %s AND empresa_id = %s AND activo = TRUE LIMIT 1",
            (registro_id, empresa_id),
        )
        if cursor.fetchone() is None:
            raise ValueError(f"{tabla.capitalize()} no encontrada en esta empresa.")

def crear_variante(
    empresa_id: int,
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
        _validar_referencias_variante(cursor, empresa_id, talla_id, color_id)
        cursor.execute(
            """
            INSERT INTO producto_variante (empresa_id, producto_id, talla_id, color_id, sku, ancho_cm, largo_cm)
            SELECT p.empresa_id, p.id, %s, %s, %s, %s, %s
            FROM producto p WHERE p.id = %s AND p.empresa_id = %s AND p.activo = TRUE
            RETURNING id;
            """,
            (talla_id, color_id, sku, ancho_cm, largo_cm, producto_id, empresa_id),
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError("Producto no encontrado en esta empresa.")
        variante_id = row["id"]
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
    empresa_id: int,
    talla_id: int | None,
    color_id: int | None,
    sku: str,
    ancho_cm: float | None = None,
    largo_cm: float | None = None,
) -> bool:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        _validar_referencias_variante(cursor, empresa_id, talla_id, color_id)
        cursor.execute(
            """
            UPDATE producto_variante
            SET talla_id = %s, color_id = %s, sku = %s, ancho_cm = %s, largo_cm = %s
            WHERE id = %s AND empresa_id = %s
            RETURNING id;
            """,
            (talla_id, color_id, sku, ancho_cm, largo_cm, variante_id, empresa_id),
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

def desactivar_variante(variante_id: int, empresa_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE producto_variante
            SET activo = FALSE
            WHERE id = %s AND empresa_id = %s AND activo = TRUE
            RETURNING id;
            """,
            (variante_id, empresa_id),
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

def activar_variante(variante_id: int, empresa_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE producto_variante
            SET activo = TRUE
            WHERE id = %s AND empresa_id = %s
            RETURNING id;
            """,
            (variante_id, empresa_id),
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

def asignar_precio(variante_id: int, empresa_id: int, monto: Decimal, fecha_inicio: object | None, fecha_fin: object | None) -> int:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        # Desactivar precio actual
        cursor.execute(
            "UPDATE precio_producto SET activo = FALSE WHERE producto_variante_id = %s AND empresa_id = %s",
            (variante_id, empresa_id)
        )
            
        cursor.execute(
            """
            INSERT INTO precio_producto (empresa_id, producto_variante_id, precio, fecha_inicio, fecha_fin)
            SELECT v.empresa_id, v.id, %s, COALESCE(%s, CURRENT_DATE), %s
            FROM producto_variante v WHERE v.id = %s AND v.empresa_id = %s
            RETURNING id;
            """,
            (monto, fecha_inicio, fecha_fin, variante_id, empresa_id),
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError("Variante no encontrada en esta empresa.")
        precio_id = row["id"]
        connection.commit()
        return precio_id
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()
