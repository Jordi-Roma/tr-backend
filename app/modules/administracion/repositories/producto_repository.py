from psycopg2.extras import RealDictCursor
from fastapi import HTTPException
from app.database.connection import get_connection
from app.core.plan_empresa import bloquear_empresa_y_obtener_limite


def _exigir_cupo_producto_cursor(cursor, empresa_id: int) -> None:
    # El lock de empresa serializa altas/reactivaciones de la misma empresa.
    limite = bloquear_empresa_y_obtener_limite(cursor, empresa_id, "productos")
    if limite is None:
        return
    cursor.execute(
        "SELECT count(*) AS total FROM producto WHERE empresa_id = %s AND activo = TRUE",
        (empresa_id,),
    )
    if int(cursor.fetchone()["total"]) >= limite:
        raise HTTPException(status_code=409, detail="Se alcanzo el limite de productos del plan.")

def listar_productos(empresa_id: int) -> list[dict[str, object]]:
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
            JOIN categoria c ON p.categoria_id = c.id AND c.empresa_id = p.empresa_id
            LEFT JOIN marca m ON p.marca_id = m.id AND m.empresa_id = p.empresa_id
            WHERE p.empresa_id = %s
            ORDER BY p.id DESC;
            """,
            (empresa_id,),
        )
        productos = [dict(row) for row in cursor.fetchall()]
        
        for p in productos:
            p['colecciones_ids'] = obtener_colecciones_ids_de_producto(p['id'], empresa_id, cursor)
            p['proveedores_ids'] = obtener_proveedores_ids_de_producto(p['id'], empresa_id, cursor)
            p['imagenes'] = obtener_imagenes_de_producto(p['id'], empresa_id, cursor)
            
        return productos
    finally:
        cursor.close()
        connection.close()

def obtener_producto_por_id(producto_id: int, empresa_id: int) -> dict[str, object] | None:
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
            JOIN categoria c ON p.categoria_id = c.id AND c.empresa_id = p.empresa_id
            LEFT JOIN marca m ON p.marca_id = m.id AND m.empresa_id = p.empresa_id
            WHERE p.id = %s AND p.empresa_id = %s
            LIMIT 1;
            """,
            (producto_id, empresa_id)
        )
        row = cursor.fetchone()
        
        if row is None:
            return None
            
        producto = dict(row)
        producto['colecciones_ids'] = obtener_colecciones_ids_de_producto(producto_id, empresa_id, cursor)
        producto['proveedores_ids'] = obtener_proveedores_ids_de_producto(producto_id, empresa_id, cursor)
        producto['imagenes'] = obtener_imagenes_de_producto(producto_id, empresa_id, cursor)
        
        return producto
    finally:
        cursor.close()
        connection.close()

def obtener_colecciones_ids_de_producto(producto_id: int, empresa_id: int, cursor) -> list[int]:
    cursor.execute("SELECT coleccion_id FROM producto_coleccion WHERE producto_id = %s AND empresa_id = %s", (producto_id, empresa_id))
    return [row['coleccion_id'] for row in cursor.fetchall()]

def obtener_proveedores_ids_de_producto(producto_id: int, empresa_id: int, cursor) -> list[int]:
    cursor.execute("SELECT proveedor_id FROM producto_proveedor WHERE producto_id = %s AND empresa_id = %s", (producto_id, empresa_id))
    return [row['proveedor_id'] for row in cursor.fetchall()]

def obtener_imagenes_de_producto(producto_id: int, empresa_id: int, cursor) -> list[dict[str, object]]:
    cursor.execute(
        """
        SELECT id, producto_id, url, es_principal, activo, fecha_creacion 
        FROM imagen_producto 
        WHERE producto_id = %s AND empresa_id = %s
        ORDER BY es_principal DESC, id ASC
        """, 
        (producto_id, empresa_id)
    )
    return [dict(row) for row in cursor.fetchall()]


def _validar_referencias_producto(
    cursor,
    empresa_id: int,
    categoria_id: int,
    marca_id: int | None,
    colecciones_ids: list[int],
    proveedores_ids: list[int],
) -> None:
    referencias = [("categoria", categoria_id)]
    if marca_id is not None:
        referencias.append(("marca", marca_id))
    referencias.extend(("coleccion", value) for value in colecciones_ids)
    referencias.extend(("proveedor", value) for value in proveedores_ids)
    for tabla, registro_id in referencias:
        cursor.execute(
            f"SELECT 1 FROM {tabla} WHERE id = %s AND empresa_id = %s AND activo = TRUE LIMIT 1",
            (registro_id, empresa_id),
        )
        if cursor.fetchone() is None:
            raise ValueError(f"{tabla.capitalize()} no encontrada en esta empresa.")

def crear_producto(
    empresa_id: int,
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
        _exigir_cupo_producto_cursor(cursor, empresa_id)
        _validar_referencias_producto(cursor, empresa_id, categoria_id, marca_id, colecciones_ids, proveedores_ids)
        cursor.execute(
            """
            INSERT INTO producto (
                empresa_id, categoria_id, marca_id, nombre, descripcion, material, genero,
                tipo_prenda, tipo_corte, ancho_base_cm, largo_base_cm, modelo_3d_url
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (
                empresa_id, categoria_id, marca_id, nombre, descripcion, material, genero,
                tipo_prenda, tipo_corte, ancho_base_cm, largo_base_cm, modelo_3d_url,
            ),
        )
        producto_id = cursor.fetchone()["id"]
        
        for col_id in colecciones_ids:
            cursor.execute("INSERT INTO producto_coleccion (empresa_id, producto_id, coleccion_id) VALUES (%s, %s, %s)", (empresa_id, producto_id, col_id))
            
        for prov_id in proveedores_ids:
            cursor.execute("INSERT INTO producto_proveedor (empresa_id, producto_id, proveedor_id) VALUES (%s, %s, %s)", (empresa_id, producto_id, prov_id))
            
        for img in imagenes:
            cursor.execute(
                "INSERT INTO imagen_producto (empresa_id, producto_id, url, es_principal) VALUES (%s, %s, %s, %s)",
                (empresa_id, producto_id, img["url"], img["es_principal"])
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
    empresa_id: int,
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
        _validar_referencias_producto(cursor, empresa_id, categoria_id, marca_id, colecciones_ids, proveedores_ids)
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
            WHERE id = %s AND empresa_id = %s
            RETURNING id;
            """,
            (
                categoria_id, marca_id, nombre, descripcion, material, genero,
                tipo_prenda, tipo_corte, ancho_base_cm, largo_base_cm, modelo_3d_url, producto_id, empresa_id,
            ),
        )
        if cursor.fetchone() is None:
            connection.rollback()
            return False
            
        cursor.execute("DELETE FROM producto_coleccion WHERE producto_id = %s AND empresa_id = %s", (producto_id, empresa_id))
        for col_id in colecciones_ids:
            cursor.execute("INSERT INTO producto_coleccion (empresa_id, producto_id, coleccion_id) VALUES (%s, %s, %s)", (empresa_id, producto_id, col_id))
            
        cursor.execute("DELETE FROM producto_proveedor WHERE producto_id = %s AND empresa_id = %s", (producto_id, empresa_id))
        for prov_id in proveedores_ids:
            cursor.execute("INSERT INTO producto_proveedor (empresa_id, producto_id, proveedor_id) VALUES (%s, %s, %s)", (empresa_id, producto_id, prov_id))
            
        cursor.execute("DELETE FROM imagen_producto WHERE producto_id = %s AND empresa_id = %s", (producto_id, empresa_id))
        for img in imagenes:
            cursor.execute(
                "INSERT INTO imagen_producto (empresa_id, producto_id, url, es_principal) VALUES (%s, %s, %s, %s)",
                (empresa_id, producto_id, img["url"], img["es_principal"])
            )

        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

def desactivar_producto(producto_id: int, empresa_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE producto
            SET activo = FALSE
            WHERE id = %s AND empresa_id = %s AND activo = TRUE
            RETURNING id;
            """,
            (producto_id, empresa_id),
        )
        row = cursor.fetchone()
        if row is None:
            connection.rollback()
            return False
            
        cursor.execute("UPDATE producto_variante SET activo = FALSE WHERE producto_id = %s AND empresa_id = %s", (producto_id, empresa_id))

        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

def activar_producto(producto_id: int, empresa_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        # Serializar también la reactivación, incluso si dos solicitudes apuntan
        # al mismo producto cuando queda un único cupo.
        limite = bloquear_empresa_y_obtener_limite(cursor, empresa_id, "productos")
        cursor.execute("SELECT activo FROM producto WHERE id = %s AND empresa_id = %s", (producto_id, empresa_id))
        actual = cursor.fetchone()
        if actual is None:
            return False
        if actual["activo"]:
            return True
        if limite is not None:
            cursor.execute("SELECT count(*) AS total FROM producto WHERE empresa_id = %s AND activo = TRUE", (empresa_id,))
            if int(cursor.fetchone()["total"]) >= limite:
                raise HTTPException(status_code=409, detail="Se alcanzo el limite de productos del plan.")
        cursor.execute(
            """
            UPDATE producto
            SET activo = TRUE
            WHERE id = %s AND empresa_id = %s
            RETURNING id;
            """,
            (producto_id, empresa_id),
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
