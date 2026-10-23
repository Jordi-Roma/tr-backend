from psycopg2.extras import RealDictCursor
from app.database.connection import get_connection


def obtener_datos_prenda_vestidor(producto_id: int, empresa_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT p.id AS producto_id, p.nombre, p.descripcion, p.categoria_id,
                   c.nombre AS categoria, p.marca_id, m.nombre AS marca,
                   p.material, p.genero,
                   COALESCE(p.tipo_prenda, 'SUPERIOR') AS tipo_prenda,
                   COALESCE(p.tipo_corte, 'REGULAR_FIT') AS tipo_corte,
                   COALESCE(p.ancho_base_cm, 53.0) AS ancho_base_cm,
                   COALESCE(p.largo_base_cm, 72.0) AS largo_base_cm,
                   p.modelo_3d_url,
                   (
                       SELECT ip.url
                       FROM imagen_producto ip
                       WHERE ip.producto_id = p.id AND ip.activo = TRUE
                       ORDER BY ip.es_principal DESC, ip.id ASC
                       LIMIT 1
                   ) AS imagen_principal
            FROM producto p
            JOIN categoria c ON c.id = p.categoria_id AND c.empresa_id = p.empresa_id
            LEFT JOIN marca m ON m.id = p.marca_id AND m.empresa_id = p.empresa_id
            WHERE p.id = %s AND p.empresa_id = %s AND p.activo = TRUE
            LIMIT 1;
            """,
            (producto_id, empresa_id),
        )
        prenda = cursor.fetchone()
        if not prenda:
            return None

        # Obtener variantes activas con tallas, colores y precios vigentes
        cursor.execute(
            """
            SELECT v.id AS variante_id, v.sku,
                   t.id AS talla_id, t.nombre AS talla_nombre,
                   co.id AS color_id, co.nombre AS color_nombre, co.codigo_hex AS color_hex,
                   v.ancho_cm AS variante_ancho_cm, v.largo_cm AS variante_largo_cm,
                   t.ancho_cm AS talla_ancho_cm, t.largo_cm AS talla_largo_cm,
                   (
                       SELECT pp.precio
                       FROM precio_producto pp
                       WHERE pp.producto_variante_id = v.id AND pp.empresa_id = v.empresa_id
                         AND pp.activo = TRUE
                         AND CURRENT_DATE BETWEEN pp.fecha_inicio AND COALESCE(pp.fecha_fin, CURRENT_DATE)
                       ORDER BY pp.id DESC
                       LIMIT 1
                   ) AS precio,
                   COALESCE(
                       (
                           SELECT SUM(inv.stock_disponible)
                           FROM inventario_sucursal inv
                           WHERE inv.producto_variante_id = v.id AND inv.empresa_id = v.empresa_id AND inv.activo = TRUE
                       ), 0
                   ) AS stock_total
            FROM producto_variante v
            LEFT JOIN talla t ON t.id = v.talla_id AND t.empresa_id = v.empresa_id
            LEFT JOIN color co ON co.id = v.color_id AND co.empresa_id = v.empresa_id
            WHERE v.producto_id = %s AND v.empresa_id = %s AND v.activo = TRUE
            ORDER BY t.id ASC, co.id ASC;
            """,
            (producto_id, empresa_id),
        )
        variantes = [dict(row) for row in cursor.fetchall()]

        # Obtener todas las imágenes activas del producto (para variantes de color)
        cursor.execute(
            """
            SELECT id, url, es_principal
            FROM imagen_producto
            WHERE producto_id = %s AND activo = TRUE
            ORDER BY es_principal DESC, id ASC;
            """,
            (producto_id,),
        )
        imagenes = [dict(row) for row in cursor.fetchall()]

        return {
            "prenda": dict(prenda),
            "variantes": variantes,
            "imagenes": imagenes,
        }
    finally:
        cursor.close()
        connection.close()


def listar_prendas_catalogo_vestidor(limite: int, empresa_id: int) -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT p.id AS producto_id, p.nombre, c.nombre AS categoria,
                   p.tipo_prenda, p.modelo_3d_url,
                   (
                       SELECT ip.url
                       FROM imagen_producto ip
                       WHERE ip.producto_id = p.id AND ip.activo = TRUE
                       ORDER BY ip.es_principal DESC, ip.id ASC
                       LIMIT 1
                   ) AS imagen_principal,
                   (
                       SELECT pp.precio
                       FROM producto_variante pv
                       JOIN precio_producto pp ON pp.producto_variante_id = pv.id AND pp.empresa_id = pv.empresa_id
                       WHERE pv.producto_id = p.id
                         AND pv.empresa_id = p.empresa_id
                         AND pv.activo = TRUE
                         AND pp.activo = TRUE
                         AND CURRENT_DATE BETWEEN pp.fecha_inicio AND COALESCE(pp.fecha_fin, CURRENT_DATE)
                       ORDER BY pp.precio ASC
                       LIMIT 1
                   ) AS precio_desde
            FROM producto p
            JOIN categoria c ON c.id = p.categoria_id AND c.empresa_id = p.empresa_id
            WHERE p.activo = TRUE AND p.empresa_id = %s
            ORDER BY p.id DESC
            LIMIT %s;
            """,
            (empresa_id, limite),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def registrar_sesion_vestidor(
    cliente_id: int | None,
    producto_id: int,
    variante_id: int | None,
    empresa_id: int,
    origen: str = "MOVIL_AR",
) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            INSERT INTO registro_vestidor (cliente_id, producto_id, variante_id, empresa_id, origen)
            SELECT %s, p.id, %s, p.empresa_id, %s
            FROM producto p
            LEFT JOIN producto_variante v
              ON v.id = %s AND v.producto_id = p.id AND v.empresa_id = p.empresa_id
            WHERE p.id = %s AND p.empresa_id = %s AND p.activo = TRUE
              AND (%s IS NULL OR v.id IS NOT NULL)
            RETURNING id, cliente_id, producto_id, variante_id, fecha, origen;
            """,
            (cliente_id, variante_id, origen, variante_id, producto_id, empresa_id, variante_id),
        )
        row = cursor.fetchone()
        connection.commit()
        return dict(row) if row is not None else None
    finally:
        cursor.close()
        connection.close()
