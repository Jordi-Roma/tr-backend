from decimal import Decimal
from uuid import uuid4

from psycopg2.extras import RealDictCursor

from app.database.connection import get_connection

TIPOS_SUMA = {"ENTRADA", "AJUSTE_POSITIVO", "TRANSFERENCIA_ENTRADA"}
TIPOS_RESTA = {"SALIDA", "AJUSTE_NEGATIVO", "TRANSFERENCIA_SALIDA", "VENTA_PRESENCIAL", "VENTA_DIGITAL"}


def obtener_sucursal_empleado(usuario_id: int) -> int | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT sucursal_id
            FROM empleado
            WHERE usuario_id = %s AND activo = TRUE
            LIMIT 1;
            """,
            (usuario_id,),
        )
        row = cursor.fetchone()
        return int(row["sucursal_id"]) if row else None
    finally:
        cursor.close()
        connection.close()


def listar_inventario(filtros: dict[str, object]) -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        condiciones = ["inv.activo = TRUE"]
        params: list[object] = []

        for key, column in (
            ("inventario_id", "inv.id"),
            ("sucursal_id", "inv.sucursal_id"),
            ("producto_id", "p.id"),
            ("producto_variante_id", "pv.id"),
            ("categoria_id", "p.categoria_id"),
            ("talla_id", "pv.talla_id"),
            ("color_id", "pv.color_id"),
        ):
            value = filtros.get(key)
            if value is not None:
                condiciones.append(f"{column} = %s")
                params.append(value)

        if filtros.get("solo_bajo_stock"):
            condiciones.append("(inv.stock_disponible - inv.stock_reservado) <= inv.stock_minimo")

        cursor.execute(
            f"""
            SELECT
                inv.id,
                inv.sucursal_id,
                s.nombre AS sucursal,
                ci.nombre AS ciudad,
                inv.producto_variante_id,
                p.id AS producto_id,
                p.nombre AS producto,
                ca.nombre AS categoria,
                t.nombre AS talla,
                co.nombre AS color,
                inv.stock_disponible,
                inv.stock_reservado,
                (inv.stock_disponible - inv.stock_reservado)::INT AS stock_real,
                inv.stock_minimo,
                ((inv.stock_disponible - inv.stock_reservado) <= inv.stock_minimo) AS bajo_stock
            FROM inventario_sucursal inv
            JOIN sucursal s ON s.id = inv.sucursal_id
            JOIN ciudad ci ON ci.id = s.ciudad_id
            JOIN producto_variante pv ON pv.id = inv.producto_variante_id
            JOIN producto p ON p.id = pv.producto_id
            JOIN categoria ca ON ca.id = p.categoria_id
            JOIN talla t ON t.id = pv.talla_id
            JOIN color co ON co.id = pv.color_id
            WHERE {' AND '.join(condiciones)}
            ORDER BY ci.nombre ASC, s.nombre ASC, p.nombre ASC, t.nombre ASC, co.nombre ASC;
            """,
            params,
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def obtener_inventario(inventario_id: int) -> dict[str, object] | None:
    rows = listar_inventario({"inventario_id": inventario_id})
    return rows[0] if rows else None


def actualizar_stock_minimo(inventario_id: int, stock_minimo: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            UPDATE inventario_sucursal
            SET stock_minimo = %s,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id = %s AND activo = TRUE
            RETURNING id;
            """,
            (stock_minimo, inventario_id),
        )
        row = cursor.fetchone()
        if row is None:
            connection.rollback()
            return None
        connection.commit()
        return listar_inventario_por_id(int(row["id"]))
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def listar_inventario_por_id(inventario_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT sucursal_id, producto_variante_id
            FROM inventario_sucursal
            WHERE id = %s AND activo = TRUE;
            """,
            (inventario_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        rows = listar_inventario(
            {
                "sucursal_id": row["sucursal_id"],
                "producto_variante_id": row["producto_variante_id"],
            }
        )
        return rows[0] if rows else None
    finally:
        cursor.close()
        connection.close()


def registrar_movimiento_manual(
    usuario_id: int,
    sucursal_id: int,
    producto_variante_id: int,
    tipo: str,
    cantidad: int,
    motivo: str | None,
) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        movimiento_id = _aplicar_movimiento(
            cursor,
            usuario_id,
            sucursal_id,
            producto_variante_id,
            tipo,
            cantidad,
            motivo,
            None,
            None,
        )
        connection.commit()
        movimiento = _obtener_movimiento_cursor(cursor, movimiento_id)
        if movimiento is None:
            raise RuntimeError("No se pudo recuperar el movimiento creado.")
        return movimiento
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def listar_movimientos(filtros: dict[str, object]) -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        condiciones = ["mi.activo = TRUE"]
        params: list[object] = []
        for key, column in (
            ("id", "mi.id"),
            ("sucursal_id", "mi.sucursal_id"),
            ("producto_variante_id", "mi.producto_variante_id"),
            ("tipo", "mi.tipo"),
        ):
            value = filtros.get(key)
            if value is not None:
                condiciones.append(f"{column} = %s")
                params.append(value)
        cursor.execute(
            f"""
            SELECT
                mi.id,
                mi.sucursal_id,
                s.nombre AS sucursal,
                ci.nombre AS ciudad,
                mi.producto_variante_id,
                p.id AS producto_id,
                p.nombre AS producto,
                t.nombre AS talla,
                co.nombre AS color,
                mi.tipo,
                mi.cantidad,
                mi.stock_anterior,
                mi.stock_nuevo,
                mi.motivo,
                mi.referencia_tipo,
                mi.referencia_id,
                mi.fecha_movimiento
            FROM movimiento_inventario mi
            JOIN sucursal s ON s.id = mi.sucursal_id
            JOIN ciudad ci ON ci.id = s.ciudad_id
            JOIN producto_variante pv ON pv.id = mi.producto_variante_id
            JOIN producto p ON p.id = pv.producto_id
            JOIN talla t ON t.id = pv.talla_id
            JOIN color co ON co.id = pv.color_id
            WHERE {' AND '.join(condiciones)}
            ORDER BY mi.fecha_movimiento DESC, mi.id DESC;
            """,
            params,
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def crear_transferencia(
    usuario_id: int,
    sucursal_origen_id: int,
    sucursal_destino_id: int,
    observacion: str | None,
    items: list[dict[str, int]],
) -> dict[str, object]:
    if sucursal_origen_id == sucursal_destino_id:
        raise ValueError("La sucursal origen y destino deben ser distintas.")
    if not items:
        raise ValueError("La transferencia debe tener al menos un item.")

    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            INSERT INTO transferencia_stock (
                sucursal_origen_id,
                sucursal_destino_id,
                usuario_id,
                estado,
                observacion
            )
            VALUES (%s, %s, %s, 'COMPLETADA', %s)
            RETURNING id;
            """,
            (sucursal_origen_id, sucursal_destino_id, usuario_id, observacion),
        )
        transferencia_id = int(cursor.fetchone()["id"])
        for item in items:
            variante_id = int(item["producto_variante_id"])
            cantidad = int(item["cantidad"])
            cursor.execute(
                """
                INSERT INTO transferencia_stock_detalle (transferencia_id, producto_variante_id, cantidad)
                VALUES (%s, %s, %s);
                """,
                (transferencia_id, variante_id, cantidad),
            )
            _aplicar_movimiento(
                cursor,
                usuario_id,
                sucursal_origen_id,
                variante_id,
                "TRANSFERENCIA_SALIDA",
                cantidad,
                observacion,
                "TRANSFERENCIA_STOCK",
                transferencia_id,
            )
            _aplicar_movimiento(
                cursor,
                usuario_id,
                sucursal_destino_id,
                variante_id,
                "TRANSFERENCIA_ENTRADA",
                cantidad,
                observacion,
                "TRANSFERENCIA_STOCK",
                transferencia_id,
            )
        connection.commit()
        transferencia = _obtener_transferencia_cursor(cursor, transferencia_id)
        if transferencia is None:
            raise RuntimeError("No se pudo recuperar la transferencia creada.")
        return transferencia
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def listar_transferencias(sucursal_id: int | None = None) -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        params: list[object] = []
        where = "ts.activo = TRUE"
        if sucursal_id is not None:
            where += " AND (ts.sucursal_origen_id = %s OR ts.sucursal_destino_id = %s)"
            params.extend([sucursal_id, sucursal_id])
        cursor.execute(
            f"""
            SELECT ts.id
            FROM transferencia_stock ts
            WHERE {where}
            ORDER BY ts.fecha_transferencia DESC, ts.id DESC;
            """,
            params,
        )
        return [
            transferencia
            for transferencia in (_obtener_transferencia_cursor(cursor, int(row["id"])) for row in cursor.fetchall())
            if transferencia is not None
        ]
    finally:
        cursor.close()
        connection.close()


def obtener_transferencia(transferencia_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        return _obtener_transferencia_cursor(cursor, transferencia_id)
    finally:
        cursor.close()
        connection.close()


def crear_venta_presencial(
    usuario_id: int,
    sucursal_id: int,
    cliente_id: int | None,
    metodo_pago: str | None,
    observacion: str | None,
    items: list[dict[str, object]],
) -> dict[str, object]:
    if not items:
        raise ValueError("La venta debe tener al menos un item.")
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        subtotal_total = Decimal("0.00")
        descuento_total = Decimal("0.00")
        codigo = f"VEN-{uuid4().hex[:10].upper()}"
        cursor.execute(
            """
            INSERT INTO venta (
                codigo,
                sucursal_id,
                usuario_id,
                cliente_id,
                tipo,
                estado,
                subtotal,
                descuento,
                total,
                metodo_pago,
                observacion
            )
            VALUES (%s, %s, %s, %s, 'PRESENCIAL', 'COMPLETADA', 0, 0, 0, %s, %s)
            RETURNING id;
            """,
            (codigo, sucursal_id, usuario_id, cliente_id, metodo_pago, observacion),
        )
        venta_id = int(cursor.fetchone()["id"])
        for item in items:
            variante_id = int(item["producto_variante_id"])
            cantidad = int(item["cantidad"])
            descuento = Decimal(str(item.get("descuento") or "0.00"))
            precio = _obtener_precio_vigente(cursor, variante_id)
            if precio is None:
                raise ValueError("Una variante no tiene precio vigente.")
            bruto = precio * cantidad
            subtotal = max(Decimal("0.00"), bruto - descuento)
            subtotal_total += bruto
            descuento_total += descuento
            _aplicar_movimiento(
                cursor,
                usuario_id,
                sucursal_id,
                variante_id,
                "VENTA_PRESENCIAL",
                cantidad,
                observacion,
                "VENTA",
                venta_id,
            )
            cursor.execute(
                """
                INSERT INTO venta_detalle (
                    venta_id,
                    producto_variante_id,
                    cantidad,
                    precio_unitario,
                    descuento,
                    subtotal
                )
                VALUES (%s, %s, %s, %s, %s, %s);
                """,
                (venta_id, variante_id, cantidad, precio, descuento, subtotal),
            )
        total = max(Decimal("0.00"), subtotal_total - descuento_total)
        cursor.execute(
            """
            UPDATE venta
            SET subtotal = %s,
                descuento = %s,
                total = %s
            WHERE id = %s;
            """,
            (subtotal_total, descuento_total, total, venta_id),
        )
        connection.commit()
        venta = _obtener_venta_cursor(cursor, venta_id)
        if venta is None:
            raise RuntimeError("No se pudo recuperar la venta creada.")
        return venta
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def listar_ventas(sucursal_id: int | None = None) -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        params: list[object] = []
        where = "v.activo = TRUE AND v.tipo = 'PRESENCIAL'"
        if sucursal_id is not None:
            where += " AND v.sucursal_id = %s"
            params.append(sucursal_id)
        cursor.execute(
            f"""
            SELECT id
            FROM venta v
            WHERE {where}
            ORDER BY fecha_venta DESC, id DESC;
            """,
            params,
        )
        return [
            venta
            for venta in (_obtener_venta_cursor(cursor, int(row["id"])) for row in cursor.fetchall())
            if venta is not None
        ]
    finally:
        cursor.close()
        connection.close()


def obtener_venta(venta_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        return _obtener_venta_cursor(cursor, venta_id)
    finally:
        cursor.close()
        connection.close()


def _obtener_o_crear_inventario(cursor, sucursal_id: int, producto_variante_id: int) -> dict[str, object]:
    cursor.execute(
        """
        SELECT id, stock_disponible, stock_reservado, stock_minimo
        FROM inventario_sucursal
        WHERE sucursal_id = %s
          AND producto_variante_id = %s
          AND activo = TRUE
        FOR UPDATE;
        """,
        (sucursal_id, producto_variante_id),
    )
    row = cursor.fetchone()
    if row is not None:
        return dict(row)
    cursor.execute(
        """
        INSERT INTO inventario_sucursal (sucursal_id, producto_variante_id, stock_disponible, stock_reservado, stock_minimo)
        VALUES (%s, %s, 0, 0, 0)
        RETURNING id, stock_disponible, stock_reservado, stock_minimo;
        """,
        (sucursal_id, producto_variante_id),
    )
    return dict(cursor.fetchone())


def _aplicar_movimiento(
    cursor,
    usuario_id: int,
    sucursal_id: int,
    producto_variante_id: int,
    tipo: str,
    cantidad: int,
    motivo: str | None,
    referencia_tipo: str | None,
    referencia_id: int | None,
) -> int:
    if tipo not in TIPOS_SUMA and tipo not in TIPOS_RESTA:
        raise ValueError("Tipo de movimiento invalido.")
    inventario = _obtener_o_crear_inventario(cursor, sucursal_id, producto_variante_id)
    stock_anterior = int(inventario["stock_disponible"])
    stock_reservado = int(inventario["stock_reservado"])
    if tipo in TIPOS_SUMA:
        stock_nuevo = stock_anterior + cantidad
    else:
        stock_real = stock_anterior - stock_reservado
        if stock_real < cantidad:
            raise ValueError("No hay stock real suficiente para la operacion.")
        stock_nuevo = stock_anterior - cantidad
    cursor.execute(
        """
        UPDATE inventario_sucursal
        SET stock_disponible = %s,
            fecha_actualizacion = CURRENT_TIMESTAMP
        WHERE id = %s;
        """,
        (stock_nuevo, inventario["id"]),
    )
    cursor.execute(
        """
        INSERT INTO movimiento_inventario (
            sucursal_id,
            producto_variante_id,
            usuario_id,
            tipo,
            cantidad,
            stock_anterior,
            stock_nuevo,
            motivo,
            referencia_tipo,
            referencia_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
        """,
        (
            sucursal_id,
            producto_variante_id,
            usuario_id,
            tipo,
            cantidad,
            stock_anterior,
            stock_nuevo,
            motivo,
            referencia_tipo,
            referencia_id,
        ),
    )
    return int(cursor.fetchone()["id"])


def _obtener_precio_vigente(cursor, producto_variante_id: int) -> Decimal | None:
    cursor.execute(
        """
        SELECT precio
        FROM precio_producto
        WHERE producto_variante_id = %s
          AND activo = TRUE
          AND CURRENT_DATE BETWEEN fecha_inicio AND COALESCE(fecha_fin, CURRENT_DATE)
        ORDER BY fecha_inicio DESC, id DESC
        LIMIT 1;
        """,
        (producto_variante_id,),
    )
    row = cursor.fetchone()
    return row["precio"] if row else None


def _obtener_movimiento_cursor(cursor, movimiento_id: int) -> dict[str, object] | None:
    cursor.execute("SELECT id FROM movimiento_inventario WHERE id = %s;", (movimiento_id,))
    if cursor.fetchone() is None:
        return None
    rows = listar_movimientos({"id": movimiento_id})
    if rows:
        return rows[0]
    cursor.execute(
        """
        SELECT
            mi.id,
            mi.sucursal_id,
            s.nombre AS sucursal,
            ci.nombre AS ciudad,
            mi.producto_variante_id,
            p.id AS producto_id,
            p.nombre AS producto,
            t.nombre AS talla,
            co.nombre AS color,
            mi.tipo,
            mi.cantidad,
            mi.stock_anterior,
            mi.stock_nuevo,
            mi.motivo,
            mi.referencia_tipo,
            mi.referencia_id,
            mi.fecha_movimiento
        FROM movimiento_inventario mi
        JOIN sucursal s ON s.id = mi.sucursal_id
        JOIN ciudad ci ON ci.id = s.ciudad_id
        JOIN producto_variante pv ON pv.id = mi.producto_variante_id
        JOIN producto p ON p.id = pv.producto_id
        JOIN talla t ON t.id = pv.talla_id
        JOIN color co ON co.id = pv.color_id
        WHERE mi.id = %s
        LIMIT 1;
        """,
        (movimiento_id,),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def _obtener_transferencia_cursor(cursor, transferencia_id: int) -> dict[str, object] | None:
    cursor.execute(
        """
        SELECT
            ts.id,
            ts.sucursal_origen_id,
            so.nombre AS sucursal_origen,
            ts.sucursal_destino_id,
            sd.nombre AS sucursal_destino,
            ts.estado,
            ts.observacion,
            ts.fecha_transferencia
        FROM transferencia_stock ts
        JOIN sucursal so ON so.id = ts.sucursal_origen_id
        JOIN sucursal sd ON sd.id = ts.sucursal_destino_id
        WHERE ts.id = %s AND ts.activo = TRUE
        LIMIT 1;
        """,
        (transferencia_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    data = dict(row)
    cursor.execute(
        """
        SELECT
            td.id,
            td.producto_variante_id,
            p.id AS producto_id,
            p.nombre AS producto,
            t.nombre AS talla,
            co.nombre AS color,
            td.cantidad
        FROM transferencia_stock_detalle td
        JOIN producto_variante pv ON pv.id = td.producto_variante_id
        JOIN producto p ON p.id = pv.producto_id
        JOIN talla t ON t.id = pv.talla_id
        JOIN color co ON co.id = pv.color_id
        WHERE td.transferencia_id = %s
        ORDER BY td.id ASC;
        """,
        (transferencia_id,),
    )
    data["detalles"] = [dict(item) for item in cursor.fetchall()]
    return data


def _obtener_venta_cursor(cursor, venta_id: int) -> dict[str, object] | None:
    cursor.execute(
        """
        SELECT
            v.id,
            v.codigo,
            v.sucursal_id,
            s.nombre AS sucursal,
            v.estado,
            v.subtotal,
            v.descuento,
            v.total,
            v.metodo_pago,
            v.observacion,
            v.fecha_venta
        FROM venta v
        JOIN sucursal s ON s.id = v.sucursal_id
        WHERE v.id = %s AND v.activo = TRUE
        LIMIT 1;
        """,
        (venta_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    data = dict(row)
    cursor.execute(
        """
        SELECT
            vd.id,
            vd.producto_variante_id,
            p.id AS producto_id,
            p.nombre AS producto,
            t.nombre AS talla,
            co.nombre AS color,
            vd.cantidad,
            vd.precio_unitario,
            vd.descuento,
            vd.subtotal
        FROM venta_detalle vd
        JOIN producto_variante pv ON pv.id = vd.producto_variante_id
        JOIN producto p ON p.id = pv.producto_id
        JOIN talla t ON t.id = pv.talla_id
        JOIN color co ON co.id = pv.color_id
        WHERE vd.venta_id = %s
        ORDER BY vd.id ASC;
        """,
        (venta_id,),
    )
    data["detalles"] = [dict(item) for item in cursor.fetchall()]
    return data
