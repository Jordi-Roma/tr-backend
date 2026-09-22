from decimal import Decimal

from psycopg2.extras import RealDictCursor

from app.database.connection import get_connection
from app.modules.catalogo.repositories.catalogo_publico_repository import (
    _calcular_precio_final,
    _obtener_promocion,
)


def obtener_cliente_id_por_usuario(usuario_id: int) -> int | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        return _obtener_cliente_id_por_usuario_cursor(cursor, usuario_id)
    finally:
        cursor.close()
        connection.close()


def obtener_carrito(cliente_id: int) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        carrito_id = _obtener_o_crear_carrito_cursor(cursor, cliente_id)
        connection.commit()
        return _armar_carrito_cursor(cursor, carrito_id)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def agregar_item_carrito(
    cliente_id: int,
    producto_variante_id: int,
    sucursal_id: int | None,
    cantidad: int,
) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        carrito_id = _obtener_o_crear_carrito_cursor(cursor, cliente_id)
        precio = _obtener_precio_final_variante_cursor(cursor, producto_variante_id, sucursal_id)

        if precio is None:
            raise ValueError("La variante no tiene precio vigente.")

        if sucursal_id is not None:
            stock = _obtener_stock_disponible_cursor(cursor, producto_variante_id, sucursal_id)
            cantidad_actual = _obtener_cantidad_item_cursor(cursor, carrito_id, producto_variante_id, sucursal_id)

            if stock < cantidad_actual + cantidad:
                raise ValueError("No hay stock suficiente para agregar esa cantidad.")

        cursor.execute(
            """
            SELECT id, cantidad
            FROM carrito_item
            WHERE carrito_id = %s
              AND producto_variante_id = %s
              AND COALESCE(sucursal_id, 0) = COALESCE(%s, 0)
              AND activo = TRUE
            LIMIT 1;
            """,
            (carrito_id, producto_variante_id, sucursal_id),
        )
        existente = cursor.fetchone()

        if existente is None:
            cursor.execute(
                """
                INSERT INTO carrito_item (
                    carrito_id,
                    producto_variante_id,
                    sucursal_id,
                    cantidad,
                    precio_unitario
                )
                VALUES (%s, %s, %s, %s, %s);
                """,
                (carrito_id, producto_variante_id, sucursal_id, cantidad, precio),
            )
        else:
            cursor.execute(
                """
                UPDATE carrito_item
                SET cantidad = cantidad + %s,
                    precio_unitario = %s,
                    fecha_actualizacion = CURRENT_TIMESTAMP
                WHERE id = %s;
                """,
                (cantidad, precio, existente["id"]),
            )

        cursor.execute(
            """
            UPDATE carrito
            SET fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id = %s;
            """,
            (carrito_id,),
        )
        connection.commit()
        return _armar_carrito_cursor(cursor, carrito_id)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def actualizar_item_carrito(cliente_id: int, item_id: int, cantidad: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        carrito_id = _obtener_o_crear_carrito_cursor(cursor, cliente_id)
        cursor.execute(
            """
            SELECT producto_variante_id, sucursal_id
            FROM carrito_item
            WHERE id = %s AND carrito_id = %s AND activo = TRUE
            LIMIT 1;
            """,
            (item_id, carrito_id),
        )
        item = cursor.fetchone()

        if item is None:
            connection.rollback()
            return None

        if item["sucursal_id"] is not None:
            stock = _obtener_stock_disponible_cursor(
                cursor,
                int(item["producto_variante_id"]),
                int(item["sucursal_id"]),
            )

            if stock < cantidad:
                raise ValueError("No hay stock suficiente para esa cantidad.")

        cursor.execute(
            """
            UPDATE carrito_item
            SET cantidad = %s,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id = %s AND carrito_id = %s AND activo = TRUE;
            """,
            (cantidad, item_id, carrito_id),
        )
        connection.commit()
        return _armar_carrito_cursor(cursor, carrito_id)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def eliminar_item_carrito(cliente_id: int, item_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        carrito_id = _obtener_o_crear_carrito_cursor(cursor, cliente_id)
        cursor.execute(
            """
            UPDATE carrito_item
            SET activo = FALSE,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id = %s AND carrito_id = %s AND activo = TRUE
            RETURNING id;
            """,
            (item_id, carrito_id),
        )

        if cursor.fetchone() is None:
            connection.rollback()
            return None

        connection.commit()
        return _armar_carrito_cursor(cursor, carrito_id)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def vaciar_carrito(cliente_id: int) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        carrito_id = _obtener_o_crear_carrito_cursor(cursor, cliente_id)
        cursor.execute(
            """
            UPDATE carrito_item
            SET activo = FALSE,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE carrito_id = %s AND activo = TRUE;
            """,
            (carrito_id,),
        )
        connection.commit()
        return _armar_carrito_cursor(cursor, carrito_id)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def _obtener_cliente_id_por_usuario_cursor(cursor, usuario_id: int) -> int | None:
    cursor.execute(
        """
        SELECT id
        FROM cliente
        WHERE usuario_id = %s AND activo = TRUE
        LIMIT 1;
        """,
        (usuario_id,),
    )
    row = cursor.fetchone()
    return int(row["id"]) if row is not None else None


def _obtener_o_crear_carrito_cursor(cursor, cliente_id: int) -> int:
    cursor.execute(
        """
        SELECT id
        FROM carrito
        WHERE cliente_id = %s AND activo = TRUE
        ORDER BY id DESC
        LIMIT 1;
        """,
        (cliente_id,),
    )
    row = cursor.fetchone()

    if row is not None:
        return int(row["id"])

    cursor.execute(
        """
        INSERT INTO carrito (cliente_id)
        VALUES (%s)
        RETURNING id;
        """,
        (cliente_id,),
    )
    return int(cursor.fetchone()["id"])


def _armar_carrito_cursor(cursor, carrito_id: int) -> dict[str, object]:
    cursor.execute(
        """
        SELECT
            ci.id,
            ci.producto_variante_id,
            p.id AS producto_id,
            p.nombre AS producto,
            ca.nombre AS categoria,
            t.nombre AS talla,
            co.nombre AS color,
            ci.sucursal_id,
            s.nombre AS sucursal,
            cd.nombre AS ciudad,
            ci.cantidad,
            pp.precio AS precio_base,
            COALESCE(GREATEST(inv.stock_disponible - inv.stock_reservado, 0), 0)::INT AS stock_disponible
        FROM carrito_item ci
        JOIN producto_variante pv ON pv.id = ci.producto_variante_id
        JOIN producto p ON p.id = pv.producto_id
        JOIN categoria ca ON ca.id = p.categoria_id
        JOIN talla t ON t.id = pv.talla_id
        JOIN color co ON co.id = pv.color_id
        LEFT JOIN sucursal s ON s.id = ci.sucursal_id
        LEFT JOIN ciudad cd ON cd.id = s.ciudad_id
        LEFT JOIN precio_producto pp
            ON pp.producto_variante_id = pv.id
            AND pp.activo = TRUE
            AND CURRENT_DATE BETWEEN pp.fecha_inicio AND COALESCE(pp.fecha_fin, CURRENT_DATE)
        LEFT JOIN inventario_sucursal inv
            ON inv.producto_variante_id = pv.id
            AND inv.sucursal_id = ci.sucursal_id
            AND inv.activo = TRUE
        WHERE ci.carrito_id = %s AND ci.activo = TRUE
        ORDER BY ci.id ASC;
        """,
        (carrito_id,),
    )
    items = []
    for row in cursor.fetchall():
        item = dict(row)
        precio_base = item.pop("precio_base", None)
        promocion = _obtener_promocion(cursor, int(item["producto_id"]), item["sucursal_id"])
        precio_final = _calcular_precio_final(precio_base, promocion) or Decimal("0.00")
        item["precio_unitario"] = precio_final
        item["subtotal"] = precio_final * int(item["cantidad"])
        items.append(item)
    total = sum((item["subtotal"] or Decimal("0.00") for item in items), Decimal("0.00"))

    return {
        "id": carrito_id,
        "items": items,
        "total": total,
        "sucursales_disponibles": _obtener_sucursales_disponibles_carrito_cursor(cursor, carrito_id),
    }


def _obtener_sucursales_disponibles_carrito_cursor(cursor, carrito_id: int) -> list[dict[str, object]]:
    cursor.execute(
        """
        WITH requerimientos AS (
            SELECT producto_variante_id, SUM(cantidad)::INT AS cantidad
            FROM carrito_item
            WHERE carrito_id = %s
              AND activo = TRUE
            GROUP BY producto_variante_id
        )
        SELECT
            s.id,
            s.nombre,
            c.nombre AS ciudad,
            s.latitud,
            s.longitud
        FROM sucursal s
        JOIN ciudad c ON c.id = s.ciudad_id
        WHERE s.activo = TRUE
          AND c.activo = TRUE
          AND EXISTS (SELECT 1 FROM requerimientos)
          AND NOT EXISTS (
              SELECT 1
              FROM requerimientos r
              LEFT JOIN inventario_sucursal inv
                ON inv.sucursal_id = s.id
               AND inv.producto_variante_id = r.producto_variante_id
               AND inv.activo = TRUE
              WHERE COALESCE(GREATEST(inv.stock_disponible - inv.stock_reservado, 0), 0) < r.cantidad
          )
        ORDER BY c.nombre ASC, s.nombre ASC;
        """,
        (carrito_id,),
    )
    return [dict(row) for row in cursor.fetchall()]


def _obtener_precio_variante_cursor(cursor, producto_variante_id: int) -> Decimal | None:
    cursor.execute(
        """
        SELECT pp.precio
        FROM producto_variante pv
        JOIN precio_producto pp
            ON pp.producto_variante_id = pv.id
            AND pp.activo = TRUE
            AND CURRENT_DATE BETWEEN pp.fecha_inicio AND COALESCE(pp.fecha_fin, CURRENT_DATE)
        WHERE pv.id = %s AND pv.activo = TRUE
        ORDER BY pp.fecha_inicio DESC, pp.id DESC
        LIMIT 1;
        """,
        (producto_variante_id,),
    )
    row = cursor.fetchone()
    return row["precio"] if row is not None else None


def _obtener_precio_final_variante_cursor(
    cursor,
    producto_variante_id: int,
    sucursal_id: int | None = None,
) -> Decimal | None:
    cursor.execute(
        """
        SELECT pv.producto_id, pp.precio
        FROM producto_variante pv
        JOIN precio_producto pp
            ON pp.producto_variante_id = pv.id
            AND pp.activo = TRUE
            AND CURRENT_DATE BETWEEN pp.fecha_inicio AND COALESCE(pp.fecha_fin, CURRENT_DATE)
        WHERE pv.id = %s AND pv.activo = TRUE
        ORDER BY pp.fecha_inicio DESC, pp.id DESC
        LIMIT 1;
        """,
        (producto_variante_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None

    promocion = _obtener_promocion(cursor, int(row["producto_id"]), sucursal_id)
    return _calcular_precio_final(row["precio"], promocion)


def _obtener_stock_disponible_cursor(cursor, producto_variante_id: int, sucursal_id: int) -> int:
    cursor.execute(
        """
        SELECT GREATEST(stock_disponible - stock_reservado, 0)::INT AS stock
        FROM inventario_sucursal
        WHERE producto_variante_id = %s
          AND sucursal_id = %s
          AND activo = TRUE
        LIMIT 1;
        """,
        (producto_variante_id, sucursal_id),
    )
    row = cursor.fetchone()
    return int(row["stock"]) if row is not None else 0


def _obtener_cantidad_item_cursor(
    cursor,
    carrito_id: int,
    producto_variante_id: int,
    sucursal_id: int | None,
) -> int:
    cursor.execute(
        """
        SELECT cantidad
        FROM carrito_item
        WHERE carrito_id = %s
          AND producto_variante_id = %s
          AND COALESCE(sucursal_id, 0) = COALESCE(%s, 0)
          AND activo = TRUE
        LIMIT 1;
        """,
        (carrito_id, producto_variante_id, sucursal_id),
    )
    row = cursor.fetchone()
    return int(row["cantidad"]) if row is not None else 0
