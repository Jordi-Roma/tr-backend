from psycopg2.extras import RealDictCursor

from app.database.connection import get_connection
from app.modules.inteligencia.schemas.reportes.reporte_request import ReporteRequest


def _rows(sql: str, params: tuple[object, ...]) -> list[dict[str, object]]:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SET LOCAL statement_timeout = '15000ms'")
            cursor.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
    finally:
        connection.close()


def listar_sucursales() -> list[dict[str, object]]:
    return _rows("SELECT s.id, s.nombre, c.nombre AS ciudad FROM sucursal s JOIN ciudad c ON c.id = s.ciudad_id WHERE s.activo = TRUE ORDER BY c.nombre, s.nombre", ())


def consultar_reporte(request: ReporteRequest) -> list[dict[str, object]]:
    desde = request.fecha_desde
    hasta = request.fecha_hasta
    sucursal = request.sucursal_id
    if request.tipo == "VENTAS":
        estado = request.estado.strip().upper() if request.estado else None
        metodo_pago = request.metodo_pago.strip().upper() if request.metodo_pago else None
        tipo_entrega = request.tipo_entrega
        return _rows("""
            SELECT v.id, v.codigo, v.fecha_venta AS fecha, s.nombre AS sucursal,
                   v.tipo, v.estado, v.tipo_entrega, v.subtotal, v.descuento, v.total,
                   v.metodo_pago, v.costo_delivery,
                   COALESCE((SELECT SUM(d.cantidad) FROM venta_detalle d WHERE d.venta_id = v.id), 0) AS unidades
            FROM venta v JOIN sucursal s ON s.id = v.sucursal_id
            WHERE v.activo = TRUE
              AND (v.fecha_venta AT TIME ZONE 'America/La_Paz')::date BETWEEN %s AND %s
              AND (%s::bigint IS NULL OR v.sucursal_id = %s)
              AND (%s::text IS NULL OR v.estado = %s)
              AND (%s::text IS NULL OR v.metodo_pago = %s)
              AND (%s::text IS NULL OR v.tipo_entrega = %s)
            ORDER BY v.fecha_venta DESC LIMIT 5000
        """, (desde, hasta, sucursal, sucursal, estado, estado, metodo_pago, metodo_pago, tipo_entrega, tipo_entrega))
    if request.tipo == "PRODUCTOS_MAS_VENDIDOS":
        tipo_entrega = request.tipo_entrega
        return _rows("""
            SELECT p.nombre AS producto, pv.sku, v.tipo_entrega, SUM(d.cantidad) AS unidades,
                   SUM(d.subtotal) AS importe
            FROM venta v JOIN venta_detalle d ON d.venta_id = v.id
            JOIN producto_variante pv ON pv.id = d.producto_variante_id
            JOIN producto p ON p.id = pv.producto_id
            WHERE v.estado = 'COMPLETADA' AND v.activo = TRUE
              AND (v.fecha_venta AT TIME ZONE 'America/La_Paz')::date BETWEEN %s AND %s
              AND (%s::bigint IS NULL OR v.sucursal_id = %s)
              AND (%s::text IS NULL OR v.tipo_entrega = %s)
            GROUP BY p.nombre, pv.sku, v.tipo_entrega ORDER BY unidades DESC, producto LIMIT 5000
        """, (desde, hasta, sucursal, sucursal, tipo_entrega, tipo_entrega))
    if request.tipo == "INVENTARIO":
        return _rows("""
            SELECT s.nombre AS sucursal, p.nombre AS producto, pv.sku,
                   i.stock_disponible AS disponible, i.stock_reservado AS reservado,
                   i.stock_disponible - i.stock_reservado AS real, i.stock_minimo AS minimo,
                   CASE WHEN i.stock_disponible - i.stock_reservado <= i.stock_minimo THEN 'BAJO STOCK' ELSE 'OK' END AS estado
            FROM inventario_sucursal i JOIN sucursal s ON s.id = i.sucursal_id
            JOIN producto_variante pv ON pv.id = i.producto_variante_id
            JOIN producto p ON p.id = pv.producto_id
            WHERE i.activo = TRUE AND (%s::bigint IS NULL OR i.sucursal_id = %s)
              AND (%s::boolean = FALSE OR i.stock_disponible - i.stock_reservado <= i.stock_minimo)
            ORDER BY s.nombre, p.nombre, pv.sku LIMIT 5000
        """, (sucursal, sucursal, request.solo_bajo_stock))
    if request.tipo == "RESERVAS":
        estado = request.estado.strip().upper() if request.estado else None
        return _rows("""
            SELECT r.codigo, r.fecha_reserva AS fecha, s.nombre AS sucursal, r.estado, r.total,
                   COALESCE((SELECT SUM(d.cantidad) FROM reserva_detalle d WHERE d.reserva_id = r.id AND d.activo = TRUE), 0) AS unidades
            FROM reserva r JOIN sucursal s ON s.id = r.sucursal_id
            WHERE r.activo = TRUE AND (r.fecha_reserva AT TIME ZONE 'America/La_Paz')::date BETWEEN %s AND %s
              AND (%s::bigint IS NULL OR r.sucursal_id = %s)
              AND (%s::text IS NULL OR r.estado = %s)
            ORDER BY r.fecha_reserva DESC LIMIT 5000
        """, (desde, hasta, sucursal, sucursal, estado, estado))
    if request.tipo == "MOVIMIENTOS":
        estado = request.estado.strip().upper() if request.estado else None
        return _rows("""
            SELECT m.fecha_movimiento AS fecha, s.nombre AS sucursal, p.nombre AS producto,
                   pv.sku, m.tipo, m.cantidad, m.stock_anterior, m.stock_nuevo, m.motivo
            FROM movimiento_inventario m JOIN sucursal s ON s.id = m.sucursal_id
            JOIN producto_variante pv ON pv.id = m.producto_variante_id
            JOIN producto p ON p.id = pv.producto_id
            WHERE m.activo = TRUE AND (m.fecha_movimiento AT TIME ZONE 'America/La_Paz')::date BETWEEN %s AND %s
              AND (%s::bigint IS NULL OR m.sucursal_id = %s)
              AND (%s::text IS NULL OR m.tipo = %s)
            ORDER BY m.fecha_movimiento DESC LIMIT 5000
        """, (desde, hasta, sucursal, sucursal, estado, estado))
    if request.tipo == "TRANSFERENCIAS":
        estado = request.estado.strip().upper() if request.estado else None
        return _rows("""
        SELECT t.fecha_transferencia AS fecha, so.nombre AS origen, sd.nombre AS destino,
               t.estado, t.observacion,
               COALESCE((SELECT SUM(d.cantidad) FROM transferencia_stock_detalle d WHERE d.transferencia_id = t.id), 0) AS unidades
        FROM transferencia_stock t JOIN sucursal so ON so.id = t.sucursal_origen_id
        JOIN sucursal sd ON sd.id = t.sucursal_destino_id
        WHERE t.activo = TRUE AND (t.fecha_transferencia AT TIME ZONE 'America/La_Paz')::date BETWEEN %s AND %s
          AND (%s::bigint IS NULL OR t.sucursal_origen_id = %s OR t.sucursal_destino_id = %s)
          AND (%s::text IS NULL OR t.estado = %s)
        ORDER BY t.fecha_transferencia DESC LIMIT 5000
    """, (desde, hasta, sucursal, sucursal, sucursal, estado, estado))
    if request.tipo == "PAGOS":
        estado = request.estado.strip().upper() if request.estado else None
        metodo_pago = request.metodo_pago.strip().upper() if request.metodo_pago else None
        proveedor = request.proveedor_pago.strip().upper() if request.proveedor_pago else None
        tipo_entrega = request.tipo_entrega
        return _rows("""
            SELECT op.id AS orden_id, op.fecha_creacion AS fecha, op.estado, op.proveedor,
                   op.metodo, op.monto_total, op.moneda, op.fecha_pago,
                   v.codigo AS venta_codigo, v.tipo_entrega, s.nombre AS sucursal,
                   TRIM(CONCAT(COALESCE(u.nombre, ''), ' ', COALESCE(u.apellido, ''))) AS cliente,
                   u.correo AS cliente_correo
            FROM orden_pago op
            JOIN venta v ON v.id = op.venta_id
            LEFT JOIN sucursal s ON s.id = v.sucursal_id
            LEFT JOIN cliente c ON c.id = op.cliente_id
            LEFT JOIN usuario u ON u.id = c.usuario_id
            WHERE op.activo = TRUE
              AND (op.fecha_creacion AT TIME ZONE 'America/La_Paz')::date BETWEEN %s AND %s
              AND (%s::bigint IS NULL OR v.sucursal_id = %s)
              AND (%s::text IS NULL OR op.estado = %s)
              AND (%s::text IS NULL OR op.metodo = %s)
              AND (%s::text IS NULL OR op.proveedor = %s)
              AND (%s::text IS NULL OR v.tipo_entrega = %s)
            ORDER BY op.fecha_creacion DESC LIMIT 5000
        """, (desde, hasta, sucursal, sucursal, estado, estado, metodo_pago, metodo_pago, proveedor, proveedor, tipo_entrega, tipo_entrega))
    if request.tipo == "DELIVERIES":
        estado = request.estado.strip().upper() if request.estado else None
        return _rows("""
            SELECT d.id, d.fecha_creacion AS fecha, d.estado, s.nombre AS sucursal,
                   d.direccion_entrega, d.distancia_km, d.tiempo_estimado_min,
                   d.costo_delivery, v.codigo AS venta_codigo, v.total,
                   TRIM(CONCAT(COALESCE(u.nombre, ''), ' ', COALESCE(u.apellido, ''))) AS cliente,
                   u.correo AS cliente_correo
            FROM delivery d
            JOIN venta v ON v.id = d.venta_id
            JOIN sucursal s ON s.id = d.sucursal_id
            LEFT JOIN cliente c ON c.id = d.cliente_id
            LEFT JOIN usuario u ON u.id = c.usuario_id
            WHERE d.activo = TRUE
              AND (d.fecha_creacion AT TIME ZONE 'America/La_Paz')::date BETWEEN %s AND %s
              AND (%s::bigint IS NULL OR d.sucursal_id = %s)
              AND (%s::text IS NULL OR d.estado = %s)
            ORDER BY d.fecha_creacion DESC LIMIT 5000
        """, (desde, hasta, sucursal, sucursal, estado, estado))
    rol = request.rol.strip().upper() if request.rol else None
    activo = request.activo
    return _rows("""
        SELECT u.id, u.fecha_creacion AS fecha, u.nombre, u.apellido, u.username,
               u.correo, u.activo, COALESCE(STRING_AGG(r.nombre, ', ' ORDER BY r.nombre), 'Sin rol') AS roles
        FROM usuario u
        LEFT JOIN usuario_rol ur ON ur.usuario_id = u.id AND ur.activo = TRUE
        LEFT JOIN rol r ON r.id = ur.rol_id AND r.activo = TRUE
        WHERE (u.fecha_creacion AT TIME ZONE 'America/La_Paz')::date BETWEEN %s AND %s
          AND (%s::boolean IS NULL OR u.activo = %s)
          AND (%s::text IS NULL OR EXISTS (
              SELECT 1
              FROM usuario_rol ur2
              JOIN rol r2 ON r2.id = ur2.rol_id
              WHERE ur2.usuario_id = u.id AND ur2.activo = TRUE AND r2.nombre = %s
          ))
        GROUP BY u.id, u.fecha_creacion, u.nombre, u.apellido, u.username, u.correo, u.activo
        ORDER BY u.fecha_creacion DESC LIMIT 5000
    """, (desde, hasta, activo, activo, rol, rol))


def listar_reportes_programados() -> list[dict[str, object]]:
    return _rows("""
        SELECT rp.id, rp.titulo, rp.tipo, rp.frecuencia, rp.hora, rp.dia,
               rp.formato, rp.destinatario_email, rp.sucursal_id, s.nombre AS sucursal_nombre,
               rp.solo_bajo_stock, rp.activo, rp.ultima_ejecucion, rp.proxima_ejecucion, rp.creado_en
        FROM reporte_programado rp
        LEFT JOIN sucursal s ON s.id = rp.sucursal_id
        ORDER BY rp.creado_en DESC
    """, ())


def crear_reporte_programado(data: dict[str, object], usuario_id: int | None = None) -> dict[str, object]:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                INSERT INTO reporte_programado (
                    titulo, tipo, frecuencia, hora, dia, formato,
                    destinatario_email, sucursal_id, solo_bajo_stock, activo, creado_por
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, titulo, tipo, frecuencia, hora, dia, formato,
                          destinatario_email, sucursal_id, solo_bajo_stock, activo,
                          ultima_ejecucion, proxima_ejecucion, creado_en
            """, (
                data["titulo"], data["tipo"], data["frecuencia"], data.get("hora", "08:00"),
                data.get("dia"), data.get("formato", "PDF"), data["destinatario_email"],
                data.get("sucursal_id"), data.get("solo_bajo_stock", False), data.get("activo", True),
                usuario_id
            ))
            row = cursor.fetchone()
            connection.commit()
            return dict(row)
    finally:
        connection.close()


def actualizar_estado_reporte_programado(programado_id: int, activo: bool) -> dict[str, object] | None:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                UPDATE reporte_programado
                SET activo = %s
                WHERE id = %s
                RETURNING id, titulo, tipo, frecuencia, hora, dia, formato,
                          destinatario_email, sucursal_id, solo_bajo_stock, activo,
                          ultima_ejecucion, proxima_ejecucion, creado_en
            """, (activo, programado_id))
            row = cursor.fetchone()
            connection.commit()
            return dict(row) if row else None
    finally:
        connection.close()


def eliminar_reporte_programado(programado_id: int) -> bool:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM reporte_programado WHERE id = %s", (programado_id,))
            connection.commit()
            return cursor.rowcount > 0
    finally:
        connection.close()


def marcar_ejecucion_reporte_programado(programado_id: int) -> dict[str, object] | None:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                UPDATE reporte_programado
                SET ultima_ejecucion = NOW()
                WHERE id = %s
                RETURNING id, titulo, tipo, frecuencia, hora, dia, formato,
                          destinatario_email, sucursal_id, solo_bajo_stock, activo,
                          ultima_ejecucion, proxima_ejecucion, creado_en
            """, (programado_id,))
            row = cursor.fetchone()
            connection.commit()
            return dict(row) if row else None
    finally:
        connection.close()
