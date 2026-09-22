from psycopg2.extras import RealDictCursor
from app.database.connection import get_connection

def listar_productos() -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT p.id, p.categoria_id, c.nombre as categoria_nombre,
                   p.marca_id, m.nombre as marca_nombre,
                   p.nombre, p.descripcion, p.material, p.genero, p.activo, p.fecha_creacion,
                   COALESCE(p.tipo_prenda, 'SUPERIOR') AS tipo_prenda,
                   COALESCE(p.tipo_corte, 'REGULAR_FIT') AS tipo_corte,
                   COALESCE(p.ancho_base_cm, 53.0) AS ancho_base_cm,
                   COALESCE(p.largo_base_cm, 72.0) AS largo_base_cm,
                   p.modelo_3d_url
            FROM producto p
            JOIN categoria c ON p.categoria_id = c.id
            LEFT JOIN marca m ON p.marca_id = m.id
            ORDER BY p.id DESC;
            """
        )
        productos = [dict(row) for row in cursor.fetchall()]
        
        for p in productos:
            p['colecciones_ids'] = obtener_colecciones_ids_de_producto(p['id'], cursor)
            p['proveedores_ids'] = obtener_proveedores_ids_de_producto(p['id'], cursor)
            p['imagenes'] = obtener_imagenes_de_producto(p['id'], cursor)
            
        return productos
    finally:
        cursor.close()
        connection.close()

def obtener_producto_por_id(producto_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT p.id, p.categoria_id, c.nombre as categoria_nombre,
                   p.marca_id, m.nombre as marca_nombre,
                   p.nombre, p.descripcion, p.material, p.genero, p.activo, p.fecha_creacion,
                   COALESCE(p.tipo_prenda, 'SUPERIOR') AS tipo_prenda,
                   COALESCE(p.tipo_corte, 'REGULAR_FIT') AS tipo_corte,
                   COALESCE(p.ancho_base_cm, 53.0) AS ancho_base_cm,
                   COALESCE(p.largo_base_cm, 72.0) AS largo_base_cm,
                   p.modelo_3d_url
            FROM producto p
            JOIN categoria c ON p.categoria_id = c.id
            LEFT JOIN marca m ON p.marca_id = m.id
            WHERE p.id = %s
            LIMIT 1;
            """,
            (producto_id,)
        )
        row = cursor.fetchone()
        
        if row is None:
            return None
            
        producto = dict(row)
        producto['colecciones_ids'] = obtener_colecciones_ids_de_producto(producto_id, cursor)
        producto['proveedores_ids'] = obtener_proveedores_ids_de_producto(producto_id, cursor)
        producto['imagenes'] = obtener_imagenes_de_producto(producto_id, cursor)
        
        return producto
    finally:
        cursor.close()
        connection.close()

def obtener_colecciones_ids_de_producto(producto_id: int, cursor) -> list[int]:
    cursor.execute("SELECT coleccion_id FROM producto_coleccion WHERE producto_id = %s", (producto_id,))
    return [row['coleccion_id'] for row in cursor.fetchall()]

def obtener_proveedores_ids_de_producto(producto_id: int, cursor) -> list[int]:
    cursor.execute("SELECT proveedor_id FROM producto_proveedor WHERE producto_id = %s", (producto_id,))
    return [row['proveedor_id'] for row in cursor.fetchall()]

def obtener_imagenes_de_producto(producto_id: int, cursor) -> list[dict[str, object]]:
    cursor.execute(
        """
        SELECT id, producto_id, url, es_principal, activo, fecha_creacion 
        FROM imagen_producto 
        WHERE producto_id = %s
        ORDER BY es_principal DESC, id ASC
        """, 
        (producto_id,)
    )
    return [dict(row) for row in cursor.fetchall()]

def crear_producto(
    categoria_id: int,
    marca_id: int | None,
    nombre: str,
    descripcion: str | None,
    material: str | None,
    genero: str | None,
    colecciones_ids: list[int],
    proveedores_ids: list[int],
    imagenes: list[dict],
    tipo_prenda: str = "SUPERIOR",
    tipo_corte: str = "REGULAR_FIT",
    ancho_base_cm: float = 53.0,
    largo_base_cm: float = 72.0,
    modelo_3d_url: str | None = None,
) -> int:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            INSERT INTO producto (
                categoria_id, marca_id, nombre, descripcion, material, genero,
                tipo_prenda, tipo_corte, ancho_base_cm, largo_base_cm, modelo_3d_url
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (
                categoria_id, marca_id, nombre, descripcion, material, genero,
                tipo_prenda, tipo_corte, ancho_base_cm, largo_base_cm, modelo_3d_url,
            ),
        )
        producto_id = cursor.fetchone()["id"]
        
        for col_id in colecciones_ids:
            cursor.execute("INSERT INTO producto_coleccion (producto_id, coleccion_id) VALUES (%s, %s)", (producto_id, col_id))
            
        for prov_id in proveedores_ids:
            cursor.execute("INSERT INTO producto_proveedor (producto_id, proveedor_id) VALUES (%s, %s)", (producto_id, prov_id))
            
        for img in imagenes:
            cursor.execute(
                "INSERT INTO imagen_producto (producto_id, url, es_principal) VALUES (%s, %s, %s)",
                (producto_id, img["url"], img["es_principal"])
            )

        connection.commit()
        return producto_id
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

def actualizar_producto(
    producto_id: int,
    categoria_id: int,
    marca_id: int | None,
    nombre: str,
    descripcion: str | None,
    material: str | None,
    genero: str | None,
    colecciones_ids: list[int],
    proveedores_ids: list[int],
    imagenes: list[dict],
    tipo_prenda: str = "SUPERIOR",
    tipo_corte: str = "REGULAR_FIT",
    ancho_base_cm: float = 53.0,
    largo_base_cm: float = 72.0,
    modelo_3d_url: str | None = None,
) -> bool:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE producto
            SET categoria_id = %s,
                marca_id = %s,
                nombre = %s,
                descripcion = %s,
                material = %s,
                genero = %s,
                tipo_prenda = %s,
                tipo_corte = %s,
                ancho_base_cm = %s,
                largo_base_cm = %s,
                modelo_3d_url = %s
            WHERE id = %s
            RETURNING id;
            """,
            (
                categoria_id, marca_id, nombre, descripcion, material, genero,
                tipo_prenda, tipo_corte, ancho_base_cm, largo_base_cm, modelo_3d_url, producto_id,
            ),
        )
        if cursor.fetchone() is None:
            connection.rollback()
            return False
            
        cursor.execute("DELETE FROM producto_coleccion WHERE producto_id = %s", (producto_id,))
        for col_id in colecciones_ids:
            cursor.execute("INSERT INTO producto_coleccion (producto_id, coleccion_id) VALUES (%s, %s)", (producto_id, col_id))
            
        cursor.execute("DELETE FROM producto_proveedor WHERE producto_id = %s", (producto_id,))
        for prov_id in proveedores_ids:
            cursor.execute("INSERT INTO producto_proveedor (producto_id, proveedor_id) VALUES (%s, %s)", (producto_id, prov_id))
            
        cursor.execute("DELETE FROM imagen_producto WHERE producto_id = %s", (producto_id,))
        for img in imagenes:
            cursor.execute(
                "INSERT INTO imagen_producto (producto_id, url, es_principal) VALUES (%s, %s, %s)",
                (producto_id, img["url"], img["es_principal"])
            )

        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

def desactivar_producto(producto_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE producto
            SET activo = FALSE
            WHERE id = %s AND activo = TRUE
            RETURNING id;
            """,
            (producto_id,),
        )
        row = cursor.fetchone()
        if row is None:
            connection.rollback()
            return False
            
        cursor.execute("UPDATE producto_variante SET activo = FALSE WHERE producto_id = %s", (producto_id,))

        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

def activar_producto(producto_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE producto
            SET activo = TRUE
            WHERE id = %s
            RETURNING id;
            """,
            (producto_id,),
        )
        row = cursor.fetchone()
        if row is None:
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
