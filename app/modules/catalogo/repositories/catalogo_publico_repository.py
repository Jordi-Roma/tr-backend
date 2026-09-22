from decimal import Decimal

from psycopg2.extras import RealDictCursor

from app.database.connection import get_connection


def listar_prendas_catalogo(filtros: dict[str, object]) -> tuple[list[dict[str, object]], int]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        where_sql, params = _construir_filtros(filtros)
        orden_sql = _construir_orden(str(filtros.get("orden") or "relevancia"))
        pagina = int(filtros.get("pagina") or 1)
        por_pagina = int(filtros.get("por_pagina") or 12)
        offset = (pagina - 1) * por_pagina

        cursor.execute(
            f"""
            SELECT COUNT(DISTINCT p.id) AS total
            FROM producto p
            JOIN categoria c ON c.id = p.categoria_id
            LEFT JOIN marca m ON m.id = p.marca_id
            LEFT JOIN producto_variante v ON v.producto_id = p.id AND v.activo = TRUE
            LEFT JOIN talla t ON t.id = v.talla_id
            LEFT JOIN color co ON co.id = v.color_id
            LEFT JOIN precio_producto pp
                ON pp.producto_variante_id = v.id
                AND pp.activo = TRUE
                AND CURRENT_DATE BETWEEN pp.fecha_inicio AND COALESCE(pp.fecha_fin, CURRENT_DATE)
            LEFT JOIN inventario_sucursal inv ON inv.producto_variante_id = v.id AND inv.activo = TRUE
            LEFT JOIN producto_coleccion pc ON pc.producto_id = p.id
            LEFT JOIN coleccion col ON col.id = pc.coleccion_id
            WHERE {where_sql};
            """,
            params,
        )
        total = int(cursor.fetchone()["total"])

        cursor.execute(
            f"""
            SELECT p.id
            FROM producto p
            JOIN categoria c ON c.id = p.categoria_id
            LEFT JOIN marca m ON m.id = p.marca_id
            LEFT JOIN producto_variante v ON v.producto_id = p.id AND v.activo = TRUE
            LEFT JOIN talla t ON t.id = v.talla_id
            LEFT JOIN color co ON co.id = v.color_id
            LEFT JOIN precio_producto pp
                ON pp.producto_variante_id = v.id
                AND pp.activo = TRUE
                AND CURRENT_DATE BETWEEN pp.fecha_inicio AND COALESCE(pp.fecha_fin, CURRENT_DATE)
            LEFT JOIN inventario_sucursal inv ON inv.producto_variante_id = v.id AND inv.activo = TRUE
            LEFT JOIN producto_coleccion pc ON pc.producto_id = p.id
            LEFT JOIN coleccion col ON col.id = pc.coleccion_id
            WHERE {where_sql}
            GROUP BY p.id, p.nombre
            {orden_sql}
            LIMIT %s OFFSET %s;
            """,
            [*params, por_pagina, offset],
        )
        producto_ids = [int(row["id"]) for row in cursor.fetchall()]

        return [
            prenda
            for prenda in (
                _armar_prenda(cursor, producto_id, filtros.get("sucursal_id")) for producto_id in producto_ids
            )
            if prenda is not None
        ], total
    finally:
        cursor.close()
        connection.close()


def obtener_prenda_catalogo(
    producto_id: int,
    sucursal_id: int | None = None,
) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        return _armar_prenda(cursor, producto_id, sucursal_id, incluir_detalle=True)
    finally:
        cursor.close()
        connection.close()


def obtener_disponibilidad_producto(
    producto_id: int,
    talla_id: int | None = None,
    color_id: int | None = None,
    sucursal_id: int | None = None,
) -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        return _obtener_disponibilidad(cursor, producto_id, talla_id, color_id, sucursal_id)
    finally:
        cursor.close()
        connection.close()


def listar_sucursales_catalogo() -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT s.id, s.nombre, ci.nombre AS ciudad, s.latitud, s.longitud
            FROM sucursal s
            JOIN ciudad ci ON ci.id = s.ciudad_id
            WHERE s.activo = TRUE AND ci.activo = TRUE
            ORDER BY ci.nombre ASC, s.nombre ASC;
            """
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def obtener_filtros_catalogo() -> dict[str, list[dict[str, object]]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre
            FROM categoria
            WHERE activo = TRUE
            ORDER BY nombre ASC;
            """
        )
        categorias = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            """
            SELECT id, nombre
            FROM talla
            WHERE activo = TRUE
            ORDER BY nombre ASC;
            """
        )
        tallas = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            """
            SELECT id, nombre, codigo_hex AS hex
            FROM color
            WHERE activo = TRUE
            ORDER BY nombre ASC;
            """
        )
        colores = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            """
            SELECT id, nombre
            FROM temporada
            WHERE activo = TRUE
            ORDER BY anio DESC, nombre ASC;
            """
        )
        temporadas = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            """
            SELECT id, nombre
            FROM coleccion
            WHERE activo = TRUE
            ORDER BY nombre ASC;
            """
        )
        colecciones = [dict(row) for row in cursor.fetchall()]

        return {
            "categorias": categorias,
            "tallas": tallas,
            "colores": colores,
            "temporadas": temporadas,
            "colecciones": colecciones,
            "sucursales": listar_sucursales_catalogo(),
        }
    finally:
        cursor.close()
        connection.close()


def _armar_prenda(
    cursor,
    producto_id: int,
    sucursal_id: object | None = None,
    incluir_detalle: bool = False,
) -> dict[str, object] | None:
    cursor.execute(
        """
        SELECT p.id AS producto_id, p.nombre, p.descripcion, p.categoria_id,
               c.nombre AS categoria, p.marca_id, m.nombre AS marca,
               p.material, p.genero, p.activo, p.modelo_3d_url,
               (
                   SELECT ip.url
                   FROM imagen_producto ip
                   WHERE ip.producto_id = p.id AND ip.activo = TRUE
                   ORDER BY ip.es_principal DESC, ip.id ASC
                   LIMIT 1
               ) AS imagen_principal
        FROM producto p
        JOIN categoria c ON c.id = p.categoria_id
        LEFT JOIN marca m ON m.id = p.marca_id
        WHERE p.id = %s AND p.activo = TRUE
        LIMIT 1;
        """,
        (producto_id,),
    )
    row = cursor.fetchone()

    if row is None:
        return None

    variantes = _obtener_variantes(cursor, producto_id, sucursal_id)
    disponibilidad = _obtener_disponibilidad(cursor, producto_id, sucursal_id=sucursal_id)
    promocion = _obtener_promocion(cursor, producto_id, sucursal_id)
    precios = [v["precio_vigente"] for v in variantes if v["precio_vigente"] is not None]
    precio_vigente = min(precios) if precios else None
    precio_final = _calcular_precio_final(precio_vigente, promocion)
    stock_total = sum(int(v["stock_total"] or 0) for v in variantes)

    item = dict(row)
    item.update(
        {
            "precio_vigente": precio_vigente,
            "precio_final": precio_final,
            "tiene_promocion": precio_final is not None and precio_vigente is not None and precio_final < precio_vigente,
            "stock_total": stock_total,
            "tallas": _extraer_tallas(variantes),
            "colores": _extraer_colores(variantes),
        }
    )

    if incluir_detalle:
        item["colecciones"] = _obtener_colecciones(cursor, producto_id)
        item["variantes"] = variantes
        item["disponibilidad"] = disponibilidad

    return item


def _obtener_variantes(cursor, producto_id: int, sucursal_id: object | None = None) -> list[dict[str, object]]:
    params: list[object] = [producto_id]
    sucursal_filter = ""

    if sucursal_id is not None:
        sucursal_filter = "AND inv.sucursal_id = %s"
        params.append(sucursal_id)

    cursor.execute(
        f"""
        SELECT v.id, v.sku, v.talla_id, t.nombre AS talla,
               v.color_id, co.nombre AS color, co.codigo_hex AS color_hex,
               pp.precio AS precio_vigente,
               COALESCE(SUM(GREATEST(inv.stock_disponible - inv.stock_reservado, 0)), 0)::INT AS stock_total,
               v.activo
        FROM producto_variante v
        JOIN talla t ON t.id = v.talla_id
        JOIN color co ON co.id = v.color_id
        LEFT JOIN precio_producto pp
            ON pp.producto_variante_id = v.id
            AND pp.activo = TRUE
            AND CURRENT_DATE BETWEEN pp.fecha_inicio AND COALESCE(pp.fecha_fin, CURRENT_DATE)
        LEFT JOIN inventario_sucursal inv
            ON inv.producto_variante_id = v.id
            AND inv.activo = TRUE
            {sucursal_filter}
        WHERE v.producto_id = %s AND v.activo = TRUE
        GROUP BY v.id, v.sku, v.talla_id, t.nombre, v.color_id, co.nombre, co.codigo_hex, pp.precio, v.activo
        ORDER BY t.nombre ASC, co.nombre ASC, v.id ASC;
        """,
        [*params[1:], params[0]] if sucursal_id is not None else params,
    )
    rows = [dict(row) for row in cursor.fetchall()]

    promocion = _obtener_promocion(cursor, producto_id, sucursal_id)
    for row in rows:
        row["precio_final"] = _calcular_precio_final(row["precio_vigente"], promocion)
        row["tiene_promocion"] = (
            row["precio_vigente"] is not None
            and row["precio_final"] is not None
            and row["precio_final"] < row["precio_vigente"]
        )

    return rows


def _obtener_disponibilidad(
    cursor,
    producto_id: int,
    talla_id: int | None = None,
    color_id: int | None = None,
    sucursal_id: object | None = None,
) -> list[dict[str, object]]:
    filtros = ["v.producto_id = %s", "v.activo = TRUE", "inv.activo = TRUE"]
    params: list[object] = [producto_id]

    if talla_id is not None:
        filtros.append("v.talla_id = %s")
        params.append(talla_id)

    if color_id is not None:
        filtros.append("v.color_id = %s")
        params.append(color_id)

    if sucursal_id is not None:
        filtros.append("s.id = %s")
        params.append(sucursal_id)

    cursor.execute(
        f"""
        SELECT s.id AS sucursal_id, s.nombre AS sucursal, ci.nombre AS ciudad,
               v.id AS variante_id, v.talla_id, t.nombre AS talla,
               v.color_id, co.nombre AS color,
               inv.stock_disponible, inv.stock_reservado,
               (inv.stock_disponible - inv.stock_reservado) > 0 AS disponible
        FROM inventario_sucursal inv
        JOIN sucursal s ON s.id = inv.sucursal_id
        JOIN ciudad ci ON ci.id = s.ciudad_id
        JOIN producto_variante v ON v.id = inv.producto_variante_id
        JOIN talla t ON t.id = v.talla_id
        JOIN color co ON co.id = v.color_id
        WHERE {' AND '.join(filtros)}
        ORDER BY ci.nombre ASC, s.nombre ASC, t.nombre ASC, co.nombre ASC;
        """,
        params,
    )
    return [dict(row) for row in cursor.fetchall()]


def _obtener_promocion(cursor, producto_id: int, sucursal_id: object | None = None) -> dict[str, object] | None:
    cursor.execute(
        """
        SELECT pr.tipo_descuento, pr.valor
        FROM promocion pr
        JOIN promocion_producto pp ON pp.promocion_id = pr.id
        WHERE pp.producto_id = %s
          AND pr.activo = TRUE
          AND CURRENT_DATE BETWEEN pr.fecha_inicio AND pr.fecha_fin
          AND (
              NOT EXISTS (
                  SELECT 1 FROM promocion_sucursal ps0
                  WHERE ps0.promocion_id = pr.id
              )
              OR (
                  %s IS NOT NULL
                  AND EXISTS (
                      SELECT 1 FROM promocion_sucursal ps
                      WHERE ps.promocion_id = pr.id AND ps.sucursal_id = %s
                  )
              )
          )
        ORDER BY pr.valor DESC, pr.id DESC
        LIMIT 1;
        """,
        (producto_id, sucursal_id, sucursal_id),
    )
    row = cursor.fetchone()
    return dict(row) if row is not None else None


def _obtener_colecciones(cursor, producto_id: int) -> list[str]:
    cursor.execute(
        """
        SELECT col.nombre
        FROM producto_coleccion pc
        JOIN coleccion col ON col.id = pc.coleccion_id
        WHERE pc.producto_id = %s AND col.activo = TRUE
        ORDER BY col.nombre ASC;
        """,
        (producto_id,),
    )
    return [str(row["nombre"]) for row in cursor.fetchall()]


def _calcular_precio_final(precio: Decimal | None, promocion: dict[str, object] | None) -> Decimal | None:
    if precio is None:
        return None

    if promocion is None:
        return precio

    valor = Decimal(promocion["valor"])

    if promocion["tipo_descuento"] == "PORCENTAJE":
        return max(Decimal("0.00"), precio - (precio * valor / Decimal("100"))).quantize(Decimal("0.01"))

    return max(Decimal("0.00"), precio - valor).quantize(Decimal("0.01"))


def _extraer_tallas(variantes: list[dict[str, object]]) -> list[dict[str, object]]:
    tallas: dict[int, str] = {}
    for variante in variantes:
        if variante.get("talla_id") is not None and variante.get("talla") is not None:
            tallas[int(variante["talla_id"])] = str(variante["talla"])
    return [{"id": id_, "nombre": nombre} for id_, nombre in sorted(tallas.items(), key=lambda item: item[1])]


def _extraer_colores(variantes: list[dict[str, object]]) -> list[dict[str, object]]:
    colores: dict[int, dict[str, object]] = {}
    for variante in variantes:
        if variante.get("color_id") is not None and variante.get("color") is not None:
            colores[int(variante["color_id"])] = {
                "id": int(variante["color_id"]),
                "nombre": str(variante["color"]),
                "hex": variante.get("color_hex"),
            }
    return sorted(colores.values(), key=lambda item: str(item["nombre"]))


def _construir_filtros(filtros: dict[str, object]) -> tuple[str, list[object]]:
    condiciones = ["p.activo = TRUE"]
    params: list[object] = []

    q = filtros.get("q")
    if q:
        condiciones.append(
            """
            (
                p.nombre ILIKE %s
                OR COALESCE(p.descripcion, '') ILIKE %s
                OR c.nombre ILIKE %s
                OR COALESCE(m.nombre, '') ILIKE %s
                OR COALESCE(p.material, '') ILIKE %s
            )
            """
        )
        like = f"%{q}%"
        params.extend([like, like, like, like, like])

    for campo, columna in (
        ("categoria_id", "p.categoria_id"),
        ("talla_id", "v.talla_id"),
        ("color_id", "v.color_id"),
        ("coleccion_id", "pc.coleccion_id"),
        ("temporada_id", "col.temporada_id"),
        ("sucursal_id", "inv.sucursal_id"),
    ):
        valor = filtros.get(campo)
        if valor is not None:
            condiciones.append(f"{columna} = %s")
            params.append(valor)

    if filtros.get("precio_min") is not None:
        condiciones.append("pp.precio >= %s")
        params.append(filtros["precio_min"])

    if filtros.get("precio_max") is not None:
        condiciones.append("pp.precio <= %s")
        params.append(filtros["precio_max"])

    if filtros.get("solo_disponibles"):
        condiciones.append("GREATEST(COALESCE(inv.stock_disponible, 0) - COALESCE(inv.stock_reservado, 0), 0) > 0")

    return " AND ".join(condiciones), params


def _construir_orden(orden: str) -> str:
    if orden == "nombre":
        return "ORDER BY p.nombre ASC"
    if orden == "precio-asc":
        return "ORDER BY MIN(pp.precio) ASC NULLS LAST, p.nombre ASC"
    if orden == "precio-desc":
        return "ORDER BY MIN(pp.precio) DESC NULLS LAST, p.nombre ASC"
    return "ORDER BY p.id DESC"
