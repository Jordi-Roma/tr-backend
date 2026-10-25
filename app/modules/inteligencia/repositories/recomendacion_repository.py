from psycopg2.extras import RealDictCursor

from app.database.connection import get_connection


def listar_productos_para_indice(empresa_id: int) -> list[dict]:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT p.id, p.categoria_id, p.nombre, p.descripcion, p.material, p.genero,
                       c.nombre AS categoria, m.nombre AS marca,
                       COALESCE((SELECT string_agg(DISTINCT co.nombre, ', ')
                           FROM producto_variante v JOIN color co ON co.id = v.color_id
                           WHERE v.producto_id = p.id AND v.activo = TRUE), '') AS colores,
                       COALESCE((SELECT string_agg(DISTINCT col.nombre, ', ')
                           FROM producto_coleccion pc JOIN coleccion col ON col.id = pc.coleccion_id
                           WHERE pc.producto_id = p.id AND pc.empresa_id=p.empresa_id AND pc.activo AND col.activo = TRUE), '') AS colecciones
                FROM producto p JOIN categoria c ON c.id = p.categoria_id
                LEFT JOIN marca m ON m.id = p.marca_id
                WHERE p.activo = TRUE AND p.empresa_id = %s AND c.activo = TRUE
                ORDER BY p.id;
            """, (empresa_id,))
            return [dict(row) for row in cursor.fetchall()]
    finally:
        connection.close()


def obtener_embeddings(modelo: str, empresa_id: int) -> dict[int, dict]:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""SELECT pe.producto_id, pe.texto_hash, pe.embedding
                              FROM producto_embedding pe JOIN producto p ON p.id = pe.producto_id
                              WHERE pe.modelo = %s AND p.empresa_id = %s""", (modelo, empresa_id))
            return {int(row['producto_id']): dict(row) for row in cursor.fetchall()}
    finally:
        connection.close()


def guardar_embedding(producto_id: int, modelo: str, texto_hash: str, embedding: list[float], empresa_id: int) -> None:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO producto_embedding (producto_id, modelo, texto_hash, embedding)
                SELECT p.id, %s, %s, %s FROM producto p WHERE p.id = %s AND p.empresa_id = %s
                ON CONFLICT (producto_id) DO UPDATE SET modelo = EXCLUDED.modelo,
                    texto_hash = EXCLUDED.texto_hash, embedding = EXCLUDED.embedding,
                    fecha_actualizacion = CURRENT_TIMESTAMP;
            """, (modelo, texto_hash, embedding, producto_id, empresa_id))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def obtener_cliente_id(usuario_id: int, empresa_id: int) -> int | None:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM cliente WHERE usuario_id = %s AND empresa_id = %s", (usuario_id, empresa_id))
            row = cursor.fetchone()
            return int(row[0]) if row else None
    finally:
        connection.close()


def listar_favoritos(cliente_id: int, empresa_id: int) -> list[int]:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""SELECT cf.producto_id FROM cliente_favorito cf
                              JOIN producto p ON p.id = cf.producto_id AND p.empresa_id = %s
                              JOIN cliente c ON c.id = cf.cliente_id AND c.empresa_id = p.empresa_id
                              WHERE cf.cliente_id = %s ORDER BY cf.fecha_creacion DESC""", (empresa_id, cliente_id))
            return [int(row[0]) for row in cursor.fetchall()]
    finally:
        connection.close()


def guardar_favorito(cliente_id: int, producto_id: int, empresa_id: int) -> None:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO cliente_favorito (cliente_id, producto_id)
                SELECT c.id, p.id FROM producto p JOIN cliente c ON c.id = %s AND c.empresa_id = p.empresa_id
                WHERE p.id = %s AND p.empresa_id = %s AND p.activo = TRUE
                ON CONFLICT DO NOTHING;
            """, (cliente_id, producto_id, empresa_id))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def quitar_favorito(cliente_id: int, producto_id: int, empresa_id: int) -> None:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""DELETE FROM cliente_favorito cf WHERE cf.cliente_id = %s AND cf.producto_id = %s
                              AND EXISTS (SELECT 1 FROM cliente c JOIN producto p ON p.empresa_id = c.empresa_id
                                          WHERE c.id = cf.cliente_id AND p.id = cf.producto_id AND c.empresa_id = %s)""", (cliente_id, producto_id, empresa_id))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def listar_compras_confirmadas(cliente_id: int, empresa_id: int) -> list[dict]:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT v.producto_id, SUM(LEAST(vd.cantidad, 3)) AS peso,
                       MAX(venta.fecha_venta) AS ultima_compra
                FROM venta JOIN venta_detalle vd ON vd.venta_id = venta.id
                JOIN producto_variante v ON v.id = vd.producto_variante_id
                WHERE venta.cliente_id = %s AND venta.empresa_id = %s AND venta.estado = 'COMPLETADA' AND venta.activo = TRUE
                GROUP BY v.producto_id ORDER BY ultima_compra DESC LIMIT 30;
            """, (cliente_id, empresa_id))
            return [dict(row) for row in cursor.fetchall()]
    finally:
        connection.close()


def obtener_preferencias(cliente_id: int, empresa_id: int) -> dict:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""SELECT pref.categorias, pref.usar_historial
                              FROM cliente_preferencia_ia pref
                              JOIN cliente c ON c.id = pref.cliente_id
                              WHERE pref.cliente_id = %s AND c.empresa_id = %s""", (cliente_id, empresa_id))
            row = cursor.fetchone()
            return dict(row) if row else {'categorias': [], 'usar_historial': True}
    finally:
        connection.close()


def guardar_preferencias(cliente_id: int, categorias: list[int], usar_historial: bool, empresa_id: int) -> dict:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO cliente_preferencia_ia (cliente_id, categorias, usar_historial)
                SELECT id, %s, %s FROM cliente WHERE id = %s AND empresa_id = %s
                ON CONFLICT (cliente_id) DO UPDATE SET categorias = EXCLUDED.categorias,
                    usar_historial = EXCLUDED.usar_historial,
                    fecha_actualizacion = CURRENT_TIMESTAMP;
            """, (categorias, usar_historial, cliente_id, empresa_id))
        connection.commit()
        return {'categorias': categorias, 'usar_historial': usar_historial}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def categorias_validas(categorias: list[int], empresa_id: int) -> bool:
    if not categorias:
        return True
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM categoria WHERE id = ANY(%s) AND empresa_id = %s AND activo = TRUE", (categorias, empresa_id))
            return int(cursor.fetchone()[0]) == len(set(categorias))
    finally:
        connection.close()
