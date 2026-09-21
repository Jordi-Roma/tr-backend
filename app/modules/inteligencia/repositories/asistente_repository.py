from psycopg2.extras import RealDictCursor

from app.database.connection import get_connection


def buscar_productos_para_asistente(
    terminos: list[str],
    color_patrones: list[str] | None = None,
    talla_patrones: list[str] | None = None,
    sucursal_patrones: list[str] | None = None,
    precio_max: float | None = None,
    producto_id: int | None = None,
    sucursal_id: int | None = None,
    limite: int = 8,
) -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        condiciones = [
            "p.activo = TRUE",
            "pv.activo = TRUE",
            "inv.activo = TRUE",
            "(inv.stock_disponible - inv.stock_reservado) > 0",
        ]
        filtros_params: list[object] = []

        if producto_id is not None:
            condiciones.append("p.id = %s")
            filtros_params.append(producto_id)

        if sucursal_id is not None:
            condiciones.append("s.id = %s")
            filtros_params.append(sucursal_id)

        for patron in color_patrones or []:
            condiciones.append("co.nombre ILIKE %s")
            filtros_params.append(f"%{patron}%")

        for patron in talla_patrones or []:
            condiciones.append("t.nombre ILIKE %s")
            filtros_params.append(f"%{patron}%")

        for patron in sucursal_patrones or []:
            condiciones.append("(s.nombre ILIKE %s OR ci.nombre ILIKE %s)")
            filtros_params.extend([f"%{patron}%", f"%{patron}%"])

        if precio_max is not None:
            condiciones.append("pp.precio <= %s")
            filtros_params.append(precio_max)

        busqueda_sql = "TRUE"
        score_sql = "1"
        busqueda_params: list[object] = []
        score_params: list[object] = []
        if terminos:
            bloques = []
            scores = []
            for termino in terminos[:8]:
                like = f"%{termino}%"
                bloques.append(
                    """
                    (
                        p.nombre ILIKE %s OR COALESCE(p.descripcion, '') ILIKE %s
                        OR c.nombre ILIKE %s OR COALESCE(m.nombre, '') ILIKE %s
                        OR COALESCE(p.material, '') ILIKE %s OR t.nombre ILIKE %s
                        OR co.nombre ILIKE %s OR s.nombre ILIKE %s OR ci.nombre ILIKE %s
                    )
                    """
                )
                busqueda_params.extend([like] * 9)
                scores.append(
                    """
                    CASE WHEN (
                        p.nombre ILIKE %s OR COALESCE(p.descripcion, '') ILIKE %s
                        OR c.nombre ILIKE %s OR COALESCE(m.nombre, '') ILIKE %s
                        OR COALESCE(p.material, '') ILIKE %s OR t.nombre ILIKE %s
                        OR co.nombre ILIKE %s OR s.nombre ILIKE %s OR ci.nombre ILIKE %s
                    ) THEN 1 ELSE 0 END
                    """
                )
                score_params.extend([like] * 9)
            busqueda_sql = "(" + " OR ".join(bloques) + ")"
            score_sql = " + ".join(scores)

        cursor.execute(
            f"""
            SELECT
                p.id AS producto_id,
                p.nombre,
                c.nombre AS categoria,
                m.nombre AS marca,
                t.nombre AS talla,
                co.nombre AS color,
                s.nombre AS sucursal,
                ci.nombre AS ciudad,
                inv.stock_disponible::INT,
                inv.stock_reservado::INT,
                (inv.stock_disponible - inv.stock_reservado)::INT AS stock_real,
                pp.precio AS precio_vigente,
                ({score_sql}) AS relevancia
            FROM inventario_sucursal inv
            JOIN sucursal s ON s.id = inv.sucursal_id AND s.activo = TRUE
            JOIN ciudad ci ON ci.id = s.ciudad_id AND ci.activo = TRUE
            JOIN producto_variante pv ON pv.id = inv.producto_variante_id
            JOIN producto p ON p.id = pv.producto_id
            JOIN categoria c ON c.id = p.categoria_id
            LEFT JOIN marca m ON m.id = p.marca_id
            JOIN talla t ON t.id = pv.talla_id
            JOIN color co ON co.id = pv.color_id
            LEFT JOIN precio_producto pp
                ON pp.producto_variante_id = pv.id
                AND pp.activo = TRUE
                AND CURRENT_DATE BETWEEN pp.fecha_inicio AND COALESCE(pp.fecha_fin, CURRENT_DATE)
            WHERE {' AND '.join(condiciones)}
              AND {busqueda_sql}
            ORDER BY relevancia DESC, p.nombre ASC, s.nombre ASC, t.nombre ASC, co.nombre ASC
            LIMIT %s;
            """,
            [*score_params, *filtros_params, *busqueda_params, limite],
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def listar_sucursales_para_asistente(limite: int = 10) -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT s.id, s.nombre, ci.nombre AS ciudad
            FROM sucursal s
            JOIN ciudad ci ON ci.id = s.ciudad_id
            WHERE s.activo = TRUE AND ci.activo = TRUE
            ORDER BY ci.nombre ASC, s.nombre ASC
            LIMIT %s;
            """,
            (limite,),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()
