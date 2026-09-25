from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from psycopg2.extras import RealDictCursor

from app.database.connection import get_connection
from app.modules.ventas_inventario.repositories.inventario_repository import _aplicar_movimiento

CENTAVO = Decimal("0.01")
ESTADOS_QUE_RESERVAN = ("SOLICITADA", "EN_REVISION", "APROBADA", "REEMBOLSO_PENDIENTE", "ERROR_REEMBOLSO", "REEMBOLSADA")


def cliente_id_por_usuario(usuario_id: int) -> int | None:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT id FROM cliente WHERE usuario_id = %s AND activo = TRUE LIMIT 1;", (usuario_id,))
            row = cursor.fetchone()
            return int(row["id"]) if row else None
    finally:
        connection.close()


def usuario_tiene_permiso(usuario_id: int, accion: str) -> bool:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT 1 FROM usuario_rol ur
                   JOIN rol_permiso rp ON rp.rol_id = ur.rol_id AND rp.activo = TRUE
                   JOIN permiso p ON p.id = rp.permiso_id AND p.activo = TRUE
                   WHERE ur.usuario_id = %s AND ur.activo = TRUE
                     AND p.modulo = 'VENTAS_INVENTARIO' AND p.accion = %s LIMIT 1;""",
                (usuario_id, accion),
            )
            return cursor.fetchone() is not None
    finally:
        connection.close()


def sucursal_id_por_usuario(usuario_id: int) -> int | None:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT sucursal_id FROM empleado WHERE usuario_id = %s AND activo = TRUE LIMIT 1;", (usuario_id,))
            row = cursor.fetchone()
            return int(row["sucursal_id"]) if row else None
    finally:
        connection.close()


def listar_ventas_elegibles(cliente_id: int, dias_plazo: int) -> list[dict]:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """SELECT v.id FROM venta v
                   WHERE v.cliente_id = %s AND v.activo = TRUE AND v.estado = 'COMPLETADA'
                     AND v.fecha_venta >= CURRENT_TIMESTAMP - (%s * INTERVAL '1 day')
                     AND (v.tipo = 'PRESENCIAL' OR EXISTS (
                         SELECT 1 FROM orden_pago op WHERE op.venta_id = v.id AND op.estado = 'PAGADO' AND op.activo = TRUE
                     ))
                   ORDER BY v.fecha_venta DESC, v.id DESC;""",
                (cliente_id, dias_plazo),
            )
            ventas = []
            for row in cursor.fetchall():
                venta = _obtener_venta_elegible_cursor(cursor, int(row["id"]))
                if venta and any(item["cantidad_disponible"] > 0 for item in venta["detalles"]):
                    ventas.append(venta)
            return ventas
    finally:
        connection.close()


def crear_devolucion(
    cliente_id: int,
    usuario_id: int,
    venta_id: int,
    motivo: str,
    observacion: str | None,
    items: list[dict],
    dias_plazo: int,
) -> dict:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT * FROM venta WHERE id = %s FOR UPDATE;", (venta_id,))
            venta = cursor.fetchone()
            if venta is None or int(venta["cliente_id"] or 0) != cliente_id or not venta["activo"]:
                raise ValueError("No se encontró una compra elegible para este cliente.")
            if venta["estado"] != "COMPLETADA":
                raise ValueError("Solo se pueden devolver compras completadas.")
            if venta["fecha_venta"] < _fecha_limite_cursor(cursor, dias_plazo):
                raise ValueError(f"El plazo para solicitar la devolución es de {dias_plazo} días desde la compra.")
            if venta["tipo"] != "PRESENCIAL":
                cursor.execute("SELECT 1 FROM orden_pago WHERE venta_id = %s AND estado = 'PAGADO' AND activo = TRUE LIMIT 1;", (venta_id,))
                if cursor.fetchone() is None:
                    raise ValueError("La compra digital todavía no tiene un pago confirmado.")

            cursor.execute("SELECT id, cantidad, subtotal FROM venta_detalle WHERE venta_id = %s ORDER BY id FOR UPDATE;", (venta_id,))
            lineas = {int(row["id"]): dict(row) for row in cursor.fetchall()}
            if not items:
                raise ValueError("Selecciona al menos un artículo para devolver.")
            monto_solicitado = Decimal("0.00")
            for item in items:
                detalle_id = int(item["venta_detalle_id"])
                cantidad = int(item["cantidad"])
                linea = lineas.get(detalle_id)
                if linea is None:
                    raise ValueError("Un artículo no pertenece a la compra seleccionada.")
                reservada = _cantidad_comprometida_cursor(cursor, detalle_id)
                disponible = int(linea["cantidad"]) - reservada
                if cantidad > disponible:
                    raise ValueError("La cantidad solicitada supera las unidades todavía disponibles para devolución.")
                monto_solicitado += _calcular_parcial(Decimal(linea["subtotal"]), int(linea["cantidad"]), cantidad)

            codigo = f"DEV-{uuid4().hex[:10].upper()}"
            clave_idempotencia = f"devolucion-{uuid4().hex}"
            cursor.execute(
                """INSERT INTO devolucion (
                       codigo, venta_id, cliente_id, sucursal_id, solicitado_por_usuario_id,
                       estado, motivo, observacion, monto_solicitado, clave_idempotencia
                   ) VALUES (%s, %s, %s, %s, %s, 'SOLICITADA', %s, %s, %s, %s)
                   RETURNING id;""",
                (codigo, venta_id, cliente_id, venta["sucursal_id"], usuario_id, motivo.strip(), observacion, monto_solicitado, clave_idempotencia),
            )
            devolucion_id = int(cursor.fetchone()["id"])
            for item in items:
                cursor.execute(
                    "INSERT INTO devolucion_detalle (devolucion_id, venta_detalle_id, cantidad_solicitada) VALUES (%s, %s, %s);",
                    (devolucion_id, int(item["venta_detalle_id"]), int(item["cantidad"])),
                )
            resultado = _obtener_devolucion_cursor(cursor, devolucion_id)
        connection.commit()
        return resultado
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def listar_devoluciones_propias(cliente_id: int, estado: str | None = None) -> list[dict]:
    return _listar_devoluciones(cliente_id=cliente_id, estado=estado)


def listar_devoluciones_sucursal(
    *, sucursal_id: int | None, ver_todas: bool, estado: str | None = None,
    venta_id: int | None = None, cliente: str | None = None,
) -> list[dict]:
    return _listar_devoluciones(
        sucursal_id=sucursal_id, ver_todas=ver_todas, estado=estado, venta_id=venta_id, cliente=cliente
    )


def obtener_devolucion(devolucion_id: int) -> dict | None:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            return _obtener_devolucion_cursor(cursor, devolucion_id)
    finally:
        connection.close()


def revisar_devolucion(devolucion_id: int, usuario_id: int, aprobar: bool, observacion: str | None) -> dict:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT estado FROM devolucion WHERE id = %s AND activo = TRUE FOR UPDATE;", (devolucion_id,))
            row = cursor.fetchone()
            if row is None:
                raise LookupError("Devolución no encontrada.")
            if row["estado"] not in {"SOLICITADA", "EN_REVISION"}:
                raise ValueError("La devolución ya fue revisada y no puede cambiarse desde esta acción.")
            estado = "APROBADA" if aprobar else "RECHAZADA"
            cursor.execute(
                """UPDATE devolucion SET estado = %s, revisado_por_usuario_id = %s,
                       observacion = COALESCE(%s, observacion), fecha_revision = CURRENT_TIMESTAMP
                   WHERE id = %s;""",
                (estado, usuario_id, observacion, devolucion_id),
            )
            resultado = _obtener_devolucion_cursor(cursor, devolucion_id)
        connection.commit()
        return resultado
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def registrar_recepcion(devolucion_id: int, usuario_id: int, items: list[dict]) -> dict:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT * FROM devolucion WHERE id = %s AND activo = TRUE FOR UPDATE;", (devolucion_id,))
            devolucion = cursor.fetchone()
            if devolucion is None:
                raise LookupError("Devolución no encontrada.")
            if devolucion["estado"] != "APROBADA":
                raise ValueError("Solo se pueden recibir artículos de una devolución aprobada.")
            cursor.execute(
                """SELECT dd.id, dd.venta_detalle_id, dd.cantidad_solicitada,
                          vd.cantidad AS cantidad_vendida, vd.subtotal, vd.producto_variante_id
                   FROM devolucion_detalle dd
                   JOIN venta_detalle vd ON vd.id = dd.venta_detalle_id
                   WHERE dd.devolucion_id = %s ORDER BY dd.id FOR UPDATE OF dd, vd;""",
                (devolucion_id,),
            )
            detalles = {int(row["id"]): dict(row) for row in cursor.fetchall()}
            if set(int(item["detalle_id"]) for item in items) != set(detalles):
                raise ValueError("Debes registrar la revisión de todos los artículos solicitados.")

            monto_aprobado = Decimal("0.00")
            for item in items:
                detalle_id = int(item["detalle_id"])
                detalle = detalles[detalle_id]
                aceptada = int(item["cantidad_aceptada"])
                solicitada = int(detalle["cantidad_solicitada"])
                if aceptada > solicitada:
                    raise ValueError("La cantidad aceptada no puede superar la cantidad solicitada.")
                cursor.execute(
                    """SELECT COALESCE(SUM(dd.cantidad_aceptada), 0) AS cantidad,
                              COALESCE(SUM(dd.monto_aprobado), 0) AS monto
                       FROM devolucion_detalle dd JOIN devolucion d ON d.id = dd.devolucion_id
                       WHERE dd.venta_detalle_id = %s AND d.id <> %s
                         AND d.estado IN ('REEMBOLSO_PENDIENTE', 'ERROR_REEMBOLSO', 'REEMBOLSADA');""",
                    (detalle["venta_detalle_id"], devolucion_id),
                )
                previo = cursor.fetchone()
                cantidad_previa = int(previo["cantidad"])
                monto_previo = Decimal(previo["monto"])
                cantidad_vendida = int(detalle["cantidad_vendida"])
                if cantidad_previa + aceptada > cantidad_vendida:
                    raise ValueError("La cantidad aceptada supera las unidades que quedan por devolver.")
                subtotal = Decimal(detalle["subtotal"])
                cantidad_final = cantidad_previa + aceptada
                if aceptada == 0:
                    monto_linea = Decimal("0.00")
                elif cantidad_final == cantidad_vendida:
                    monto_linea = max(Decimal("0.00"), subtotal - monto_previo)
                else:
                    monto_linea = min(
                        max(Decimal("0.00"), subtotal - monto_previo),
                        _calcular_parcial(subtotal, cantidad_vendida, aceptada),
                    )
                monto_aprobado += monto_linea
                cursor.execute(
                    """UPDATE devolucion_detalle
                       SET cantidad_aceptada = %s, cantidad_rechazada = %s,
                           monto_aprobado = %s, observacion = %s, inventario_repuesto = %s
                       WHERE id = %s;""",
                    (aceptada, solicitada - aceptada, monto_linea, item.get("observacion"), aceptada > 0, detalle_id),
                )
                if aceptada > 0:
                    _aplicar_movimiento(
                        cursor,
                        usuario_id,
                        int(devolucion["sucursal_id"]),
                        int(detalle["producto_variante_id"]),
                        "DEVOLUCION_VENTA",
                        aceptada,
                        f"Devolución {devolucion['codigo']}",
                        "DEVOLUCION",
                        devolucion_id,
                    )
            estado = "REEMBOLSO_PENDIENTE" if monto_aprobado > 0 else "RECHAZADA"
            cursor.execute(
                """UPDATE devolucion SET estado = %s, monto_aprobado = %s,
                       recibido_por_usuario_id = %s, fecha_recepcion = CURRENT_TIMESTAMP
                   WHERE id = %s;""",
                (estado, monto_aprobado, usuario_id, devolucion_id),
            )
            resultado = _obtener_devolucion_cursor(cursor, devolucion_id)
        connection.commit()
        return resultado
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def preparar_reembolso_stripe(devolucion_id: int, usuario_id: int) -> dict | None:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """SELECT d.*, v.metodo_pago, op.id AS orden_pago_id,
                          op.proveedor, op.proveedor_payment_intent_id, op.estado AS estado_pago
                   FROM devolucion d JOIN venta v ON v.id = d.venta_id
                   LEFT JOIN LATERAL (
                       SELECT * FROM orden_pago WHERE venta_id = v.id AND activo = TRUE
                       ORDER BY id DESC LIMIT 1
                   ) op ON TRUE
                   WHERE d.id = %s AND d.activo = TRUE FOR UPDATE OF d;""",
                (devolucion_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise LookupError("Devolución no encontrada.")
            if row["estado"] == "REEMBOLSADA":
                connection.commit()
                return dict(row)
            if row["estado"] not in {"REEMBOLSO_PENDIENTE", "ERROR_REEMBOLSO"}:
                raise ValueError("La devolución todavía no está lista para reembolso.")
            if row["orden_pago_id"] is None or row["estado_pago"] != "PAGADO":
                return None
            if row["proveedor"] != "STRIPE" or not row["proveedor_payment_intent_id"]:
                return None
            cursor.execute(
                """UPDATE devolucion SET estado = 'REEMBOLSO_PENDIENTE', metodo_reembolso = 'STRIPE',
                       error_reembolso = NULL,
                       reembolso_iniciado_por_usuario_id = COALESCE(reembolso_iniciado_por_usuario_id, %s),
                       fecha_reembolso_solicitud = COALESCE(fecha_reembolso_solicitud, CURRENT_TIMESTAMP)
                   WHERE id = %s;""",
                (usuario_id, devolucion_id),
            )
            resultado = dict(row)
            resultado["estado"] = "REEMBOLSO_PENDIENTE"
        connection.commit()
        return resultado
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def registrar_reembolso_manual(devolucion_id: int, usuario_id: int, metodo: str, referencia: str, observacion: str | None) -> dict:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """SELECT d.estado, d.monto_aprobado, op.proveedor
                   FROM devolucion d JOIN venta v ON v.id = d.venta_id
                   LEFT JOIN LATERAL (
                       SELECT proveedor FROM orden_pago WHERE venta_id = v.id AND activo = TRUE
                       ORDER BY id DESC LIMIT 1
                   ) op ON TRUE
                   WHERE d.id = %s AND d.activo = TRUE FOR UPDATE OF d;""",
                (devolucion_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise LookupError("Devolución no encontrada.")
            if row["estado"] == "REEMBOLSADA":
                raise ValueError("Este reembolso ya fue registrado.")
            if row["estado"] not in {"REEMBOLSO_PENDIENTE", "ERROR_REEMBOLSO"}:
                raise ValueError("La devolución todavía no está lista para reembolso.")
            if Decimal(row["monto_aprobado"]) <= 0:
                raise ValueError("El importe del reembolso debe ser mayor a cero.")
            if str(row.get("proveedor") or "").upper() == "STRIPE":
                raise ValueError("Esta compra se pagó con Stripe; usa el reembolso automático para evitar duplicarlo.")
            cursor.execute(
                """UPDATE devolucion SET estado = 'REEMBOLSADA', metodo_reembolso = %s,
                       referencia_reembolso = %s, observacion = COALESCE(%s, observacion),
                       reembolsada_por_usuario_id = %s,
                       fecha_reembolso = CURRENT_TIMESTAMP, error_reembolso = NULL
                   WHERE id = %s;""",
                (metodo, referencia.strip(), observacion, usuario_id, devolucion_id),
            )
            resultado = _obtener_devolucion_cursor(cursor, devolucion_id)
        connection.commit()
        return resultado
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def actualizar_resultado_stripe(
    devolucion_id: int, refund_id: str, estado: str, error: str | None = None,
    usuario_id: int | None = None,
) -> dict | None:
    estado_normalizado = estado.lower()
    estado_devolucion = "REEMBOLSADA" if estado_normalizado == "succeeded" else "ERROR_REEMBOLSO" if estado_normalizado == "failed" else "REEMBOLSO_PENDIENTE"
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """UPDATE devolucion SET estado = %s, metodo_reembolso = 'STRIPE',
                   proveedor_refund_id = %s, proveedor_refund_estado = %s,
                   fecha_reembolso = CASE WHEN %s = 'REEMBOLSADA' THEN CURRENT_TIMESTAMP ELSE fecha_reembolso END,
                   reembolsada_por_usuario_id = CASE WHEN %s = 'REEMBOLSADA'
                       THEN COALESCE(reembolsada_por_usuario_id, %s) ELSE reembolsada_por_usuario_id END,
                   error_reembolso = %s
                   WHERE id = %s AND activo = TRUE AND estado <> 'REEMBOLSADA' RETURNING id;""",
                (estado_devolucion, refund_id, estado_normalizado, estado_devolucion,
                 estado_devolucion, usuario_id, error, devolucion_id),
            )
            if cursor.fetchone() is None:
                connection.commit()
                return None
            resultado = _obtener_devolucion_cursor(cursor, devolucion_id)
        connection.commit()
        return resultado
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def actualizar_resultado_stripe_por_refund(refund_id: str, estado: str, error: str | None = None) -> None:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM devolucion WHERE proveedor_refund_id = %s LIMIT 1;", (refund_id,))
            row = cursor.fetchone()
        if row:
            actualizar_resultado_stripe(int(row[0]), refund_id, estado, error)
    finally:
        connection.close()


def actualizar_resultado_stripe_por_devolucion(
    devolucion_id: int, refund_id: str, estado: str, error: str | None = None,
    usuario_id: int | None = None,
) -> None:
    actualizar_resultado_stripe(devolucion_id, refund_id, estado, error, usuario_id)


def cancelar_devolucion(devolucion_id: int, cliente_id: int, usuario_id: int) -> dict:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """SELECT estado, cliente_id FROM devolucion
                   WHERE id = %s AND activo = TRUE FOR UPDATE;""",
                (devolucion_id,),
            )
            row = cursor.fetchone()
            if row is None or int(row["cliente_id"] or 0) != cliente_id:
                raise LookupError("Devolución no encontrada.")
            if row["estado"] != "SOLICITADA":
                raise ValueError("Solo puedes cancelar una solicitud que aún no fue revisada.")
            cursor.execute(
                """UPDATE devolucion SET estado = 'CANCELADA', cancelada_por_usuario_id = %s,
                       fecha_cancelacion = CURRENT_TIMESTAMP WHERE id = %s;""",
                (usuario_id, devolucion_id),
            )
            resultado = _obtener_devolucion_cursor(cursor, devolucion_id)
        connection.commit()
        return resultado
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def marcar_error_reembolso(devolucion_id: int, mensaje: str) -> dict | None:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """UPDATE devolucion SET estado = 'ERROR_REEMBOLSO', error_reembolso = %s
                   WHERE id = %s AND estado = 'REEMBOLSO_PENDIENTE' RETURNING id;""",
                (mensaje[:1000], devolucion_id),
            )
            if cursor.fetchone() is None:
                connection.commit()
                return None
            resultado = _obtener_devolucion_cursor(cursor, devolucion_id)
        connection.commit()
        return resultado
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _listar_devoluciones(
    *, cliente_id: int | None = None, sucursal_id: int | None = None, ver_todas: bool = False,
    estado: str | None = None, venta_id: int | None = None, cliente: str | None = None,
) -> list[dict]:
    condiciones = ["d.activo = TRUE"]
    parametros: list[object] = []
    if cliente_id is not None:
        condiciones.append("d.cliente_id = %s")
        parametros.append(cliente_id)
    if not ver_todas and sucursal_id is not None:
        condiciones.append("d.sucursal_id = %s")
        parametros.append(sucursal_id)
    if estado:
        condiciones.append("d.estado = %s")
        parametros.append(estado.upper())
    if venta_id is not None:
        condiciones.append("d.venta_id = %s")
        parametros.append(venta_id)
    if cliente:
        condiciones.append("(u.nombre ILIKE %s OR u.apellido ILIKE %s OR u.correo ILIKE %s)")
        busqueda = f"%{cliente.strip()}%"
        parametros.extend([busqueda, busqueda, busqueda])
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                f"""SELECT d.id FROM devolucion d
                    LEFT JOIN cliente c ON c.id = d.cliente_id
                    LEFT JOIN usuario u ON u.id = c.usuario_id
                    WHERE {' AND '.join(condiciones)}
                    ORDER BY d.fecha_solicitud DESC, d.id DESC;""",
                parametros,
            )
            return [
                item for row in cursor.fetchall()
                if (item := _obtener_devolucion_cursor(cursor, int(row["id"]))) is not None
            ]
    finally:
        connection.close()


def _obtener_venta_elegible_cursor(cursor, venta_id: int) -> dict | None:
    cursor.execute(
        """SELECT v.id AS venta_id, v.codigo AS venta_codigo, v.tipo AS venta_tipo,
                  v.estado AS estado_venta, v.fecha_venta, v.sucursal_id, s.nombre AS sucursal,
                  v.metodo_pago, v.total
           FROM venta v JOIN sucursal s ON s.id = v.sucursal_id
           WHERE v.id = %s AND v.activo = TRUE;""",
        (venta_id,),
    )
    venta = cursor.fetchone()
    if venta is None:
        return None
    data = dict(venta)
    cursor.execute(
        """SELECT vd.id AS venta_detalle_id, vd.producto_variante_id, p.nombre AS producto,
                  t.nombre AS talla, co.nombre AS color, vd.cantidad AS cantidad_vendida,
                  vd.precio_unitario, vd.subtotal,
                  GREATEST(vd.cantidad - COALESCE((
                      SELECT SUM(CASE
                          WHEN d.estado IN ('SOLICITADA', 'EN_REVISION', 'APROBADA') THEN dd.cantidad_solicitada
                          WHEN d.estado IN ('REEMBOLSO_PENDIENTE', 'ERROR_REEMBOLSO', 'REEMBOLSADA') THEN dd.cantidad_aceptada
                          ELSE 0 END)
                      FROM devolucion_detalle dd JOIN devolucion d ON d.id = dd.devolucion_id
                      WHERE dd.venta_detalle_id = vd.id AND d.activo = TRUE
                  ), 0), 0)::INTEGER AS cantidad_disponible
           FROM venta_detalle vd
           JOIN producto_variante pv ON pv.id = vd.producto_variante_id
           JOIN producto p ON p.id = pv.producto_id
           JOIN talla t ON t.id = pv.talla_id
           JOIN color co ON co.id = pv.color_id
           WHERE vd.venta_id = %s ORDER BY vd.id;""",
        (venta_id,),
    )
    data["detalles"] = [dict(row) for row in cursor.fetchall()]
    return data


def _obtener_devolucion_cursor(cursor, devolucion_id: int) -> dict | None:
    cursor.execute(
        """SELECT d.*, v.codigo AS venta_codigo, v.metodo_pago AS metodo_pago_original,
                  op.proveedor AS proveedor_pago_original,
                  c.usuario_id AS cliente_usuario_id,
                  NULLIF(TRIM(CONCAT_WS(' ', u.nombre, u.apellido)), '') AS cliente_nombre,
                  u.correo AS cliente_correo, s.nombre AS sucursal
           FROM devolucion d JOIN venta v ON v.id = d.venta_id
           JOIN sucursal s ON s.id = d.sucursal_id
           LEFT JOIN cliente c ON c.id = d.cliente_id
           LEFT JOIN usuario u ON u.id = c.usuario_id
           LEFT JOIN LATERAL (
               SELECT proveedor FROM orden_pago WHERE venta_id = v.id AND activo = TRUE
               ORDER BY id DESC LIMIT 1
           ) op ON TRUE
           WHERE d.id = %s AND d.activo = TRUE LIMIT 1;""",
        (devolucion_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    data = dict(row)
    cursor.execute(
        """SELECT dd.id, dd.venta_detalle_id, vd.producto_variante_id, p.nombre AS producto,
                  t.nombre AS talla, co.nombre AS color, vd.cantidad AS cantidad_vendida,
                  dd.cantidad_solicitada, dd.cantidad_aceptada, dd.cantidad_rechazada,
                  vd.precio_unitario, vd.subtotal AS subtotal_original, dd.monto_aprobado,
                  dd.observacion, dd.inventario_repuesto
           FROM devolucion_detalle dd
           JOIN venta_detalle vd ON vd.id = dd.venta_detalle_id
           JOIN producto_variante pv ON pv.id = vd.producto_variante_id
           JOIN producto p ON p.id = pv.producto_id
           JOIN talla t ON t.id = pv.talla_id
           JOIN color co ON co.id = pv.color_id
           WHERE dd.devolucion_id = %s ORDER BY dd.id;""",
        (devolucion_id,),
    )
    data["detalles"] = [dict(item) for item in cursor.fetchall()]
    data.pop("cliente_usuario_id", None)
    return data


def _cantidad_comprometida_cursor(cursor, venta_detalle_id: int) -> int:
    cursor.execute(
        """SELECT COALESCE(SUM(CASE
                   WHEN d.estado IN ('SOLICITADA', 'EN_REVISION', 'APROBADA') THEN dd.cantidad_solicitada
                   WHEN d.estado IN ('REEMBOLSO_PENDIENTE', 'ERROR_REEMBOLSO', 'REEMBOLSADA') THEN dd.cantidad_aceptada
                   ELSE 0 END), 0) AS cantidad
           FROM devolucion_detalle dd JOIN devolucion d ON d.id = dd.devolucion_id
           WHERE dd.venta_detalle_id = %s AND d.activo = TRUE;""",
        (venta_detalle_id,),
    )
    return int(cursor.fetchone()["cantidad"])


def _fecha_limite_cursor(cursor, dias_plazo: int):
    cursor.execute("SELECT CURRENT_TIMESTAMP - (%s * INTERVAL '1 day') AS fecha;", (dias_plazo,))
    return cursor.fetchone()["fecha"]


def _calcular_parcial(subtotal: Decimal, cantidad_total: int, cantidad: int) -> Decimal:
    if cantidad_total <= 0 or cantidad <= 0:
        return Decimal("0.00")
    return (subtotal * Decimal(cantidad) / Decimal(cantidad_total)).quantize(CENTAVO, rounding=ROUND_HALF_UP)
