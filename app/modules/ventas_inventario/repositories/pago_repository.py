from decimal import Decimal
from uuid import uuid4

from psycopg2.extras import RealDictCursor

from app.database.connection import get_connection
from app.modules.reservas.repositories.carrito_repository import _obtener_precio_final_variante_cursor
from app.modules.ventas_inventario.repositories.inventario_repository import _aplicar_movimiento


def usuario_tiene_permiso(usuario_id: int, accion: str) -> bool:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT 1
                FROM usuario_rol ur
                JOIN rol_permiso rp
                    ON rp.rol_id = ur.rol_id
                    AND rp.activo = TRUE
                JOIN permiso p
                    ON p.id = rp.permiso_id
                    AND p.activo = TRUE
                WHERE ur.usuario_id = %s
                  AND ur.activo = TRUE
                  AND p.modulo = 'VENTAS_INVENTARIO'
                  AND p.accion = %s
                LIMIT 1;
                """,
                (usuario_id, accion),
            )
            return cursor.fetchone() is not None
    finally:
        connection.close()


def obtener_sucursal_id_por_usuario_empleado(usuario_id: int) -> int | None:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT sucursal_id
                FROM empleado
                WHERE usuario_id = %s
                  AND activo = TRUE
                LIMIT 1;
                """,
                (usuario_id,),
            )
            row = cursor.fetchone()
            return int(row["sucursal_id"]) if row else None
    finally:
        connection.close()


def obtener_cliente_id_por_usuario(usuario_id: int) -> int | None:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
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
            return int(row["id"]) if row else None
    finally:
        connection.close()


def crear_orden_desde_carrito(
    cliente_id: int,
    usuario_id: int,
    sucursal_id: int | None,
    delivery: dict | None = None,
) -> dict:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            carrito_id = _obtener_carrito_activo(cursor, cliente_id)
            if carrito_id is None:
                raise ValueError("El carrito esta vacio.")

            items = _obtener_items_carrito(cursor, carrito_id, sucursal_id)
            if not items:
                raise ValueError("El carrito esta vacio.")

            for item in items:
                if item["sucursal_id"] is None:
                    raise ValueError("Selecciona una sucursal para todos los items del carrito.")
                if Decimal(item["precio_unitario"]) <= 0:
                    raise ValueError("Una prenda no tiene precio vigente.")
                if int(item["stock_disponible"]) < int(item["cantidad"]):
                    raise ValueError("No hay stock suficiente para completar la compra.")

            sucursales = {int(item["sucursal_id"]) for item in items}
            if len(sucursales) != 1:
                raise ValueError("La compra digital debe realizarse desde una sola sucursal.")

            subtotal_total = sum((Decimal(item["subtotal"]) for item in items), Decimal("0.00"))
            costo_delivery = Decimal(str(delivery.get("costo_delivery", 0))) if delivery else Decimal("0.00")
            total = subtotal_total + costo_delivery
            sucursal_compra_id = next(iter(sucursales))
            venta_id = _crear_venta_pendiente(
                cursor,
                usuario_id,
                cliente_id,
                sucursal_compra_id,
                subtotal_total,
                total,
                costo_delivery,
                "DELIVERY" if delivery else "RECOJO_SUCURSAL",
            )
            for item in items:
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
                    VALUES (%s, %s, %s, %s, 0, %s);
                    """,
                    (
                        venta_id,
                        item["producto_variante_id"],
                        item["cantidad"],
                        item["precio_unitario"],
                        item["subtotal"],
                    ),
                )

            cursor.execute(
                """
                INSERT INTO orden_pago (
                    venta_id,
                    cliente_id,
                    concepto,
                    monto_total,
                    moneda,
                    metodo,
                    estado,
                    proveedor
                )
                VALUES (%s, %s, 'COMPRA', %s, 'BOB', 'TARJETA', 'PENDIENTE', 'STRIPE')
                RETURNING *;
                """,
                (venta_id, cliente_id, total),
            )
            orden = dict(cursor.fetchone())
            if delivery:
                from app.modules.ventas_inventario.repositories.delivery_repository import crear_delivery_para_venta

                crear_delivery_para_venta(
                    cursor,
                    venta_id=venta_id,
                    cliente_id=cliente_id,
                    sucursal_id=sucursal_compra_id,
                    direccion_entrega=str(delivery["direccion_entrega"]),
                    referencia=delivery.get("referencia"),
                    latitud_entrega=delivery["latitud_entrega"],
                    longitud_entrega=delivery["longitud_entrega"],
                    distancia_km=delivery["distancia_km"],
                    tiempo_estimado_min=int(delivery["tiempo_estimado_min"]),
                    costo_delivery=costo_delivery,
                )
            connection.commit()
            orden["items"] = items
            orden["costo_delivery"] = costo_delivery
            return orden
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def actualizar_checkout_stripe(orden_id: int, session_id: str, checkout_url: str, payment_intent_id: str | None) -> dict:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                UPDATE orden_pago
                SET proveedor_session_id = %s,
                    proveedor_payment_intent_id = %s,
                    checkout_url = %s,
                    fecha_actualizacion = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING *;
                """,
                (session_id, payment_intent_id, checkout_url, orden_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise ValueError("Orden de pago no encontrada.")
        connection.commit()
        return dict(row)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def obtener_orden_pago(orden_id: int) -> dict | None:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM orden_pago
                WHERE id = %s AND activo = TRUE
                LIMIT 1;
                """,
                (orden_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    finally:
        connection.close()


def listar_historial_pagos(
    *,
    cliente_id: int | None = None,
    sucursal_id: int | None = None,
    estado: str | None = None,
    metodo: str | None = None,
    proveedor: str | None = None,
    cliente: str | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
) -> list[dict]:
    where = ["op.activo = TRUE"]
    params: list[object] = []

    if cliente_id is not None:
        where.append("op.cliente_id = %s")
        params.append(cliente_id)

    if sucursal_id is not None:
        where.append("v.sucursal_id = %s")
        params.append(sucursal_id)

    if estado:
        where.append("op.estado = %s")
        params.append(estado.strip().upper())

    if metodo:
        where.append("op.metodo = %s")
        params.append(metodo.strip().upper())

    if proveedor:
        where.append("op.proveedor = %s")
        params.append(proveedor.strip().upper())

    if cliente:
        where.append(
            """
            (
                LOWER(COALESCE(u.nombre, '')) LIKE %s
                OR LOWER(COALESCE(u.apellido, '')) LIKE %s
                OR LOWER(COALESCE(u.correo, '')) LIKE %s
            )
            """
        )
        term = f"%{cliente.strip().lower()}%"
        params.extend([term, term, term])

    if fecha_desde:
        where.append("op.fecha_creacion::date >= %s")
        params.append(fecha_desde)

    if fecha_hasta:
        where.append("op.fecha_creacion::date <= %s")
        params.append(fecha_hasta)

    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                f"""
                SELECT
                    op.id AS orden_id,
                    op.venta_id,
                    op.cliente_id,
                    op.reserva_id,
                    op.concepto,
                    op.monto_total,
                    op.moneda,
                    op.metodo,
                    op.estado,
                    op.proveedor,
                    op.fecha_creacion,
                    op.fecha_pago,
                    v.codigo AS venta_codigo,
                    v.sucursal_id,
                    s.nombre AS sucursal_nombre,
                    u.correo AS cliente_correo,
                    TRIM(CONCAT(COALESCE(u.nombre, ''), ' ', COALESCE(u.apellido, ''))) AS cliente_nombre
                FROM orden_pago op
                JOIN venta v ON v.id = op.venta_id
                LEFT JOIN sucursal s ON s.id = v.sucursal_id
                LEFT JOIN cliente c ON c.id = op.cliente_id
                LEFT JOIN usuario u ON u.id = c.usuario_id
                WHERE {' AND '.join(where)}
                ORDER BY op.fecha_creacion DESC, op.id DESC;
                """,
                params,
            )
            return [dict(row) for row in cursor.fetchall()]
    finally:
        connection.close()


def obtener_historial_pago_detalle(orden_id: int) -> dict | None:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT
                    op.id AS orden_id,
                    op.venta_id,
                    op.cliente_id,
                    op.reserva_id,
                    op.concepto,
                    op.monto_total,
                    op.moneda,
                    op.metodo,
                    op.estado,
                    op.proveedor,
                    op.proveedor_session_id,
                    op.proveedor_payment_intent_id,
                    op.checkout_url,
                    op.fecha_creacion,
                    op.fecha_pago,
                    v.codigo AS venta_codigo,
                    v.sucursal_id,
                    s.nombre AS sucursal_nombre,
                    u.correo AS cliente_correo,
                    TRIM(CONCAT(COALESCE(u.nombre, ''), ' ', COALESCE(u.apellido, ''))) AS cliente_nombre
                FROM orden_pago op
                JOIN venta v ON v.id = op.venta_id
                LEFT JOIN sucursal s ON s.id = v.sucursal_id
                LEFT JOIN cliente c ON c.id = op.cliente_id
                LEFT JOIN usuario u ON u.id = c.usuario_id
                WHERE op.id = %s
                  AND op.activo = TRUE
                LIMIT 1;
                """,
                (orden_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            pago = dict(row)
            pago["productos"] = _listar_productos_pago_cursor(cursor, int(pago["venta_id"]))
            return pago
    finally:
        connection.close()


def _listar_productos_pago_cursor(cursor, venta_id: int) -> list[dict]:
    cursor.execute(
        """
        SELECT
            p.nombre AS producto,
            ca.nombre AS categoria,
            t.nombre AS talla,
            co.nombre AS color,
            vd.cantidad,
            vd.precio_unitario,
            vd.subtotal
        FROM venta_detalle vd
        JOIN producto_variante pv ON pv.id = vd.producto_variante_id
        JOIN producto p ON p.id = pv.producto_id
        LEFT JOIN categoria ca ON ca.id = p.categoria_id
        LEFT JOIN talla t ON t.id = pv.talla_id
        LEFT JOIN color co ON co.id = pv.color_id
        WHERE vd.venta_id = %s
        ORDER BY vd.id ASC;
        """,
        (venta_id,),
    )
    return [dict(row) for row in cursor.fetchall()]


def obtener_orden_por_session(session_id: str) -> dict | None:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM orden_pago
                WHERE proveedor_session_id = %s AND activo = TRUE
                LIMIT 1;
                """,
                (session_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    finally:
        connection.close()


def marcar_orden_pagada(orden_id: int, usuario_id_movimiento: int | None = None) -> dict:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT op.*, v.sucursal_id, v.usuario_id
                FROM orden_pago op
                JOIN venta v ON v.id = op.venta_id
                WHERE op.id = %s AND op.activo = TRUE
                FOR UPDATE;
                """,
                (orden_id,),
            )
            orden = cursor.fetchone()
            if orden is None:
                raise ValueError("Orden de pago no encontrada.")
            orden = dict(orden)
            if orden["estado"] == "PAGADO":
                connection.commit()
                return _obtener_orden_cursor(cursor, orden_id)
            if orden["estado"] != "PENDIENTE":
                raise ValueError("La orden no esta pendiente.")

            if str(orden.get("concepto") or "COMPRA") in {"RESERVA_ANTICIPO", "RESERVA_SALDO"}:
                connection.rollback()
                from app.modules.reservas.repositories.reserva_repository import confirmar_pago_stripe_reserva

                return confirmar_pago_stripe_reserva(orden_id, usuario_id_movimiento)

            cursor.execute(
                """
                SELECT producto_variante_id, cantidad
                FROM venta_detalle
                WHERE venta_id = %s
                ORDER BY id ASC;
                """,
                (orden["venta_id"],),
            )
            detalles = [dict(row) for row in cursor.fetchall()]
            usuario_movimiento = usuario_id_movimiento or orden["usuario_id"]
            for detalle in detalles:
                _aplicar_movimiento(
                    cursor,
                    usuario_movimiento,
                    int(orden["sucursal_id"]),
                    int(detalle["producto_variante_id"]),
                    "VENTA_DIGITAL",
                    int(detalle["cantidad"]),
                    "Pago digital confirmado por Stripe",
                    "VENTA",
                    int(orden["venta_id"]),
                )

            cursor.execute(
                """
                UPDATE venta
                SET estado = 'COMPLETADA',
                    metodo_pago = 'STRIPE'
                WHERE id = %s;
                """,
                (orden["venta_id"],),
            )
            cursor.execute(
                """
                UPDATE orden_pago
                SET estado = 'PAGADO',
                    fecha_pago = CURRENT_TIMESTAMP,
                    fecha_actualizacion = CURRENT_TIMESTAMP
                WHERE id = %s;
                """,
                (orden_id,),
            )
            cursor.execute(
                """
                UPDATE carrito_item
                SET activo = FALSE,
                    fecha_actualizacion = CURRENT_TIMESTAMP
                WHERE carrito_id IN (
                    SELECT id FROM carrito WHERE cliente_id = %s AND activo = TRUE
                );
                """,
                (orden["cliente_id"],),
            )
            resultado = _obtener_orden_cursor(cursor, orden_id)
        connection.commit()
        return resultado
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def marcar_orden_no_pagada(orden_id: int, estado_orden: str, estado_venta: str) -> dict:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT venta_id, estado
                FROM orden_pago
                WHERE id = %s AND activo = TRUE
                FOR UPDATE;
                """,
                (orden_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise ValueError("Orden de pago no encontrada.")
            if row["estado"] == "PAGADO":
                return _obtener_orden_cursor(cursor, orden_id)
            cursor.execute(
                """
                UPDATE orden_pago
                SET estado = %s,
                    fecha_actualizacion = CURRENT_TIMESTAMP
                WHERE id = %s;
                """,
                (estado_orden, orden_id),
            )
            cursor.execute(
                """
                UPDATE venta
                SET estado = %s
                WHERE id = %s AND estado = 'PENDIENTE_PAGO';
                """,
                (estado_venta, row["venta_id"]),
            )
            resultado = _obtener_orden_cursor(cursor, orden_id)
        connection.commit()
        return resultado
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _obtener_carrito_activo(cursor, cliente_id: int) -> int | None:
    cursor.execute(
        """
        SELECT c.id
        FROM carrito c
        JOIN carrito_item ci ON ci.carrito_id = c.id AND ci.activo = TRUE
        WHERE c.cliente_id = %s AND c.activo = TRUE
        ORDER BY c.id DESC
        LIMIT 1;
        """,
        (cliente_id,),
    )
    row = cursor.fetchone()
    return int(row["id"]) if row else None


def _obtener_items_carrito(cursor, carrito_id: int, sucursal_id: int | None) -> list[dict]:
    cursor.execute(
        """
        SELECT
            ci.id,
            ci.producto_variante_id,
            p.nombre AS producto,
            ca.nombre AS categoria,
            t.nombre AS talla,
            co.nombre AS color,
            %s AS sucursal_id,
            ci.cantidad,
            COALESCE(GREATEST(inv.stock_disponible - inv.stock_reservado, 0), 0)::INT AS stock_disponible
        FROM carrito_item ci
        JOIN producto_variante pv ON pv.id = ci.producto_variante_id AND pv.activo = TRUE
        JOIN producto p ON p.id = pv.producto_id AND p.activo = TRUE
        JOIN categoria ca ON ca.id = p.categoria_id
        JOIN talla t ON t.id = pv.talla_id
        JOIN color co ON co.id = pv.color_id
        LEFT JOIN inventario_sucursal inv
            ON inv.producto_variante_id = pv.id
            AND inv.sucursal_id = %s
            AND inv.activo = TRUE
        WHERE ci.carrito_id = %s AND ci.activo = TRUE
        ORDER BY ci.id ASC;
        """,
        (sucursal_id, sucursal_id, carrito_id),
    )
    items = []
    for row in cursor.fetchall():
        item = dict(row)
        precio = _obtener_precio_final_variante_cursor(
            cursor,
            int(item["producto_variante_id"]),
            sucursal_id,
        )
        item["precio_unitario"] = precio or Decimal("0.00")
        item["subtotal"] = item["precio_unitario"] * int(item["cantidad"])
        items.append(item)
    return items


def _crear_venta_pendiente(
    cursor,
    usuario_id: int,
    cliente_id: int,
    sucursal_id: int,
    subtotal: Decimal,
    total: Decimal,
    costo_delivery: Decimal,
    tipo_entrega: str,
) -> int:
    codigo = f"WEB-{uuid4().hex[:10].upper()}"
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
            tipo_entrega,
            costo_delivery,
            metodo_pago,
            observacion
        )
        VALUES (%s, %s, %s, %s, 'WEB', 'PENDIENTE_PAGO', %s, 0, %s, %s, %s, 'STRIPE', 'Compra digital pendiente de pago')
        RETURNING id;
        """,
        (codigo, sucursal_id, usuario_id, cliente_id, subtotal, total, tipo_entrega, costo_delivery),
    )
    return int(cursor.fetchone()["id"])


def _obtener_orden_cursor(cursor, orden_id: int) -> dict:
    cursor.execute(
        """
        SELECT *
        FROM orden_pago
        WHERE id = %s
        LIMIT 1;
        """,
        (orden_id,),
    )
    return dict(cursor.fetchone())
