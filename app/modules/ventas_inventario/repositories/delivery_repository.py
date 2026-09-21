from decimal import Decimal

from psycopg2.extras import RealDictCursor

from app.database.connection import get_connection


def usuario_tiene_permiso(usuario_id: int, accion: str) -> bool:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT 1
                FROM usuario_rol ur
                JOIN rol_permiso rp ON rp.rol_id = ur.rol_id AND rp.activo = TRUE
                JOIN permiso p ON p.id = rp.permiso_id AND p.activo = TRUE
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


def obtener_sucursal(sucursal_id: int) -> dict | None:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            return obtener_sucursal_cursor(cursor, sucursal_id)
    finally:
        connection.close()


def obtener_sucursal_cursor(cursor, sucursal_id: int) -> dict | None:
    cursor.execute(
        """
        SELECT
            s.id,
            s.nombre,
            s.direccion,
            s.latitud,
            s.longitud,
            c.nombre AS ciudad
        FROM sucursal s
        LEFT JOIN ciudad c ON c.id = s.ciudad_id
        WHERE s.id = %s
          AND s.activo = TRUE
        LIMIT 1;
        """,
        (sucursal_id,),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def crear_delivery_para_venta(
    cursor,
    *,
    venta_id: int,
    cliente_id: int,
    sucursal_id: int,
    direccion_entrega: str,
    referencia: str | None,
    latitud_entrega: Decimal,
    longitud_entrega: Decimal,
    distancia_km: Decimal,
    tiempo_estimado_min: int,
    costo_delivery: Decimal,
) -> dict:
    cursor.execute(
        """
        INSERT INTO delivery (
            venta_id,
            cliente_id,
            sucursal_id,
            direccion_entrega,
            referencia,
            latitud_entrega,
            longitud_entrega,
            distancia_km,
            tiempo_estimado_min,
            costo_delivery,
            estado
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'PENDIENTE')
        RETURNING *;
        """,
        (
            venta_id,
            cliente_id,
            sucursal_id,
            direccion_entrega,
            referencia,
            latitud_entrega,
            longitud_entrega,
            distancia_km,
            tiempo_estimado_min,
            costo_delivery,
        ),
    )
    return dict(cursor.fetchone())


def crear_delivery_independiente(data: dict) -> dict:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT cliente_id, sucursal_id
                FROM venta
                WHERE id = %s
                  AND activo = TRUE
                LIMIT 1;
                """,
                (data["venta_id"],),
            )
            venta = cursor.fetchone()
            if venta is None:
                raise ValueError("Venta no encontrada.")

            delivery = crear_delivery_para_venta(
                cursor,
                venta_id=int(data["venta_id"]),
                cliente_id=int(venta["cliente_id"]) if venta["cliente_id"] is not None else data["cliente_id"],
                sucursal_id=int(data.get("sucursal_id") or venta["sucursal_id"]),
                direccion_entrega=str(data["direccion_entrega"]),
                referencia=data.get("referencia"),
                latitud_entrega=data["latitud_entrega"],
                longitud_entrega=data["longitud_entrega"],
                distancia_km=data["distancia_km"],
                tiempo_estimado_min=int(data["tiempo_estimado_min"]),
                costo_delivery=data["costo_delivery"],
            )
            cursor.execute(
                """
                UPDATE venta
                SET tipo_entrega = 'DELIVERY',
                    costo_delivery = %s,
                    total = subtotal - descuento + %s
                WHERE id = %s;
                """,
                (data["costo_delivery"], data["costo_delivery"], data["venta_id"]),
            )
        connection.commit()
        return delivery
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def listar_deliveries(
    *,
    cliente_id: int | None = None,
    sucursal_id: int | None = None,
    estado: str | None = None,
    cliente: str | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
) -> list[dict]:
    where = ["d.activo = TRUE"]
    params: list[object] = []

    if cliente_id is not None:
        where.append("d.cliente_id = %s")
        params.append(cliente_id)
    if sucursal_id is not None:
        where.append("d.sucursal_id = %s")
        params.append(sucursal_id)
    if estado:
        where.append("d.estado = %s")
        params.append(estado.strip().upper())
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
        where.append("d.fecha_creacion::date >= %s")
        params.append(fecha_desde)
    if fecha_hasta:
        where.append("d.fecha_creacion::date <= %s")
        params.append(fecha_hasta)

    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                f"""
                SELECT
                    d.*,
                    v.codigo AS venta_codigo,
                    v.total AS total_venta,
                    s.nombre AS sucursal_nombre,
                    s.direccion AS sucursal_direccion,
                    s.latitud AS sucursal_latitud,
                    s.longitud AS sucursal_longitud,
                    cii.nombre AS sucursal_ciudad,
                    u.correo AS cliente_correo,
                    TRIM(CONCAT(COALESCE(u.nombre, ''), ' ', COALESCE(u.apellido, ''))) AS cliente_nombre
                FROM delivery d
                JOIN venta v ON v.id = d.venta_id
                LEFT JOIN sucursal s ON s.id = d.sucursal_id
                LEFT JOIN ciudad cii ON cii.id = s.ciudad_id
                LEFT JOIN cliente c ON c.id = d.cliente_id
                LEFT JOIN usuario u ON u.id = c.usuario_id
                WHERE {' AND '.join(where)}
                ORDER BY d.fecha_creacion DESC, d.id DESC;
                """,
                params,
            )
            return [dict(row) for row in cursor.fetchall()]
    finally:
        connection.close()


def obtener_delivery(delivery_id: int) -> dict | None:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT
                    d.*,
                    v.codigo AS venta_codigo,
                    v.total AS total_venta,
                    s.nombre AS sucursal_nombre,
                    s.direccion AS sucursal_direccion,
                    s.latitud AS sucursal_latitud,
                    s.longitud AS sucursal_longitud,
                    cii.nombre AS sucursal_ciudad,
                    u.correo AS cliente_correo,
                    TRIM(CONCAT(COALESCE(u.nombre, ''), ' ', COALESCE(u.apellido, ''))) AS cliente_nombre
                FROM delivery d
                JOIN venta v ON v.id = d.venta_id
                LEFT JOIN sucursal s ON s.id = d.sucursal_id
                LEFT JOIN ciudad cii ON cii.id = s.ciudad_id
                LEFT JOIN cliente c ON c.id = d.cliente_id
                LEFT JOIN usuario u ON u.id = c.usuario_id
                WHERE d.id = %s
                  AND d.activo = TRUE
                LIMIT 1;
                """,
                (delivery_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    finally:
        connection.close()


def actualizar_estado(delivery_id: int, estado: str, observacion: str | None) -> dict:
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                UPDATE delivery
                SET estado = %s,
                    observacion = COALESCE(%s, observacion),
                    fecha_entrega = CASE WHEN %s = 'ENTREGADO' THEN CURRENT_TIMESTAMP ELSE fecha_entrega END,
                    fecha_actualizacion = CURRENT_TIMESTAMP
                WHERE id = %s
                  AND activo = TRUE
                RETURNING id;
                """,
                (estado, observacion, estado, delivery_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise ValueError("Delivery no encontrado.")
        connection.commit()
        delivery = obtener_delivery(delivery_id)
        if delivery is None:
            raise ValueError("Delivery no encontrado.")
        return delivery
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
