from psycopg2.extras import RealDictCursor

from app.database.connection import get_connection


def _leer(sql, params):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('SET TRANSACTION READ ONLY')
            cur.execute("SET LOCAL statement_timeout='5000ms'")
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def validar_contexto(contexto, empresa_id):
    """Los IDs recibidos no acreditan existencia ni acceso en otra empresa."""
    from fastapi import HTTPException
    if contexto is None:
        return
    if contexto.empresa_id not in (None, empresa_id):
        raise HTTPException(403, 'El contexto no corresponde a la empresa actual.')
    for tabla, identificador in (('producto',contexto.producto_id),('sucursal',contexto.sucursal_id),('producto_variante',contexto.variante_id)):
        if identificador is None:
            continue
        if not _leer(f'SELECT id FROM {tabla} WHERE id=%s AND empresa_id=%s AND activo', (identificador,empresa_id)):
            raise HTTPException(404, 'El contexto seleccionado no está disponible.')
    if contexto.variante_id is not None and contexto.producto_id is not None:
        if not _leer('SELECT id FROM producto_variante WHERE id=%s AND producto_id=%s AND empresa_id=%s',
                     (contexto.variante_id,contexto.producto_id,empresa_id)):
            raise HTTPException(422, 'La variante no corresponde al producto seleccionado.')
    if contexto.variante_id is not None and contexto.producto_id is None:
        variante = _leer('SELECT producto_id FROM producto_variante WHERE id=%s AND empresa_id=%s', (contexto.variante_id,empresa_id))[0]
        contexto = contexto.model_copy(update={'producto_id':variante['producto_id']})
    return contexto


def consultar_operaciones_cliente(empresa_id, usuario_id, tipo, recurso_id=None, codigo=None, orden_id=None, venta_id=None):
    """Proyecciones acotadas de solo lectura; nunca disparan vencimientos o pagos."""
    consultas = {
        'RESERVA': """SELECT r.id,r.codigo,r.estado,r.fecha_reserva AS fecha,r.fecha_cita,r.fecha_expiracion,
            r.total::text AS importe,'BOB' AS moneda,s.nombre AS sucursal FROM reserva r
            JOIN sucursal s ON s.id=r.sucursal_id AND s.empresa_id=r.empresa_id
            WHERE r.activo AND r.empresa_id=%s AND r.cliente_id IN (SELECT id FROM cliente WHERE usuario_id=%s AND empresa_id=%s AND activo)
            AND (%s::bigint IS NULL OR r.id=%s) AND (%s::text IS NULL OR lower(r.codigo)=lower(%s)) ORDER BY r.id DESC LIMIT 6""",
        'VENTA': """SELECT r.id,r.codigo,r.estado,r.fecha_venta AS fecha,r.total::text AS importe,'BOB' AS moneda,
            s.nombre AS sucursal FROM venta r JOIN sucursal s ON s.id=r.sucursal_id AND s.empresa_id=r.empresa_id
            WHERE r.activo AND r.empresa_id=%s AND r.cliente_id IN (SELECT id FROM cliente WHERE usuario_id=%s AND empresa_id=%s AND activo)
            AND (%s::bigint IS NULL OR r.id=%s) AND (%s::text IS NULL OR lower(r.codigo)=lower(%s)) ORDER BY r.id DESC LIMIT 6""",
        'ORDEN_PAGO': """SELECT r.id,v.codigo,r.estado,r.fecha_creacion AS fecha,r.fecha_pago,
            r.monto_total::text AS importe,r.moneda,r.concepto FROM orden_pago r
            LEFT JOIN venta v ON v.id=r.venta_id AND v.empresa_id=r.empresa_id
            WHERE r.activo AND r.empresa_id=%s AND r.cliente_id IN (SELECT id FROM cliente WHERE usuario_id=%s AND empresa_id=%s AND activo)
            AND (%s::bigint IS NULL OR r.id=%s) AND (%s::text IS NULL OR lower(v.codigo)=lower(%s)) ORDER BY r.id DESC LIMIT 6""",
        'DELIVERY': """SELECT r.id,v.codigo,r.estado,r.fecha_creacion AS fecha,r.fecha_entrega,r.tiempo_estimado_min,
            r.costo_delivery::text AS importe,'BOB' AS moneda,s.nombre AS sucursal FROM delivery r
            JOIN venta v ON v.id=r.venta_id AND v.empresa_id=r.empresa_id
            JOIN sucursal s ON s.id=r.sucursal_id AND s.empresa_id=r.empresa_id
            WHERE r.activo AND r.empresa_id=%s AND r.cliente_id IN (SELECT id FROM cliente WHERE usuario_id=%s AND empresa_id=%s AND activo)
            AND (%s::bigint IS NULL OR r.id=%s) AND (%s::text IS NULL OR lower(v.codigo)=lower(%s)) ORDER BY r.id DESC LIMIT 6""",
        'DEVOLUCION': """SELECT r.id,r.codigo,r.estado,r.fecha_solicitud AS fecha,r.fecha_reembolso,
            coalesce(r.importe_reintegro,r.monto_aprobado)::text AS importe,r.moneda,r.politica_snapshot,
            r.tipo_operacion FROM devolucion r
            WHERE r.activo AND r.empresa_id=%s AND r.cliente_id IN (SELECT id FROM cliente WHERE usuario_id=%s AND empresa_id=%s AND activo)
            AND (%s::bigint IS NULL OR r.id=%s) AND (%s::text IS NULL OR lower(r.codigo)=lower(%s)) ORDER BY r.id DESC LIMIT 6""",
        'CAMBIO': """SELECT r.id,r.codigo,c.estado,r.fecha_solicitud AS fecha,r.fecha_reembolso,
            coalesce(r.importe_reintegro,0)::text AS importe,r.moneda,r.politica_snapshot,
            c.diferencia::text AS diferencia,c.aceptado_en,c.cotizacion_vence FROM devolucion r JOIN cambio_prenda c ON c.id=r.id
            WHERE r.activo AND r.empresa_id=%s AND r.cliente_id IN (SELECT id FROM cliente WHERE usuario_id=%s AND empresa_id=%s AND activo)
            AND (%s::bigint IS NULL OR r.id=%s) AND (%s::text IS NULL OR lower(r.codigo)=lower(%s)) ORDER BY r.id DESC LIMIT 6""",
        'REEMBOLSO_PAGO': """SELECT r.id,v.codigo,r.estado,r.actualizado_en AS fecha,r.monto::text AS importe,r.moneda
            FROM reembolso_pago r JOIN orden_pago op ON op.id=r.orden_id AND op.empresa_id=r.empresa_id
            LEFT JOIN venta v ON v.id=op.venta_id AND v.empresa_id=op.empresa_id
            WHERE r.empresa_id=%s AND op.cliente_id IN (SELECT id FROM cliente WHERE usuario_id=%s AND empresa_id=%s AND activo)
            AND (%s::bigint IS NULL OR r.id=%s) AND (%s::text IS NULL OR lower(v.codigo)=lower(%s)) ORDER BY r.id DESC LIMIT 6""",
    }
    sql = consultas[tipo]
    parametros = [empresa_id,usuario_id,empresa_id,recurso_id,recurso_id,codigo,codigo]
    if tipo=='REEMBOLSO_PAGO':
        if orden_id is not None:
            sql = sql.replace('ORDER BY r.id DESC', 'AND r.orden_id=%s ORDER BY r.id DESC')
            parametros.append(orden_id)
        if venta_id is not None:
            sql = sql.replace('ORDER BY r.id DESC', 'AND v.id=%s ORDER BY r.id DESC')
            parametros.append(venta_id)
    filas = _leer(sql,parametros)
    # Publicar solo condiciones de la política, nunca el snapshot completo ni sus metadatos internos.
    for r in filas:
        r['recurso_tipo'] = tipo
        snapshot = r.pop('politica_snapshot', None)
        if isinstance(snapshot, dict):
            r['politica_aplicada'] = {k:v for k,v in snapshot.items() if k in {
                'plazo_cambios','plazo_devoluciones','condiciones_cambios','condiciones_devoluciones',
                'cambios_habilitados','devoluciones_habilitadas','plazo','condiciones'}}
    return filas


def buscar_productos_para_asistente(
    terminos: list[str],
    color_patrones: list[str] | None = None,
    talla_patrones: list[str] | None = None,
    sucursal_patrones: list[str] | None = None,
    precio_max: float | None = None,
    producto_id: int | None = None,
    sucursal_id: int | None = None,
    limite: int = 8,
    empresa_id: int | None = None,
    solo_promociones: bool = False,
    variante_id: int | None = None,
) -> list[dict[str, object]]:
    if empresa_id is None:
        raise ValueError("Se requiere empresa_id para consultar el asistente.")
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute("SET LOCAL statement_timeout='5000ms'")
        condiciones = [
            "p.activo = TRUE",
            "c.activo = TRUE",
            "t.activo = TRUE",
            "co.activo = TRUE",
            "pv.activo = TRUE",
            "inv.activo = TRUE",
            "(inv.stock_disponible - inv.stock_reservado) > 0",
            "inv.empresa_id = %s",
            "s.empresa_id = inv.empresa_id",
            "pv.empresa_id = inv.empresa_id",
            "p.empresa_id = inv.empresa_id",
            "c.empresa_id = inv.empresa_id",
            "t.empresa_id = inv.empresa_id",
            "co.empresa_id = inv.empresa_id",
        ]
        filtros_params: list[object] = [empresa_id]

        if producto_id is not None:
            condiciones.append("p.id = %s")
            filtros_params.append(producto_id)

        if sucursal_id is not None:
            condiciones.append("s.id = %s")
            filtros_params.append(sucursal_id)

        for patron in color_patrones or []:
            condiciones.append("translate(lower(co.nombre),'áéíóúüñ','aeiouun') ILIKE %s")
            filtros_params.append(f"%{patron}%")

        if talla_patrones:
            condiciones.append("lower(t.nombre) = ANY(%s)")
            filtros_params.append([t.lower() for t in talla_patrones])

        for patron in sucursal_patrones or []:
            condiciones.append("(translate(lower(s.nombre),'áéíóúüñ','aeiouun') ILIKE %s OR translate(lower(ci.nombre),'áéíóúüñ','aeiouun') ILIKE %s)")
            filtros_params.extend([f"%{patron}%", f"%{patron}%"])

        if precio_max is not None:
            condiciones.append("precio_catalogo(pv.id, inv.empresa_id, s.id) <= %s")
            filtros_params.append(precio_max)

        if variante_id is not None:
            condiciones.append("pv.id = %s")
            filtros_params.append(variante_id)
        if solo_promociones:
            condiciones.append("precio_catalogo(pv.id, inv.empresa_id, s.id) < pp.precio")

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
                        translate(lower(p.nombre),'áéíóúüñ','aeiouun') ILIKE %s OR translate(lower(COALESCE(p.descripcion, '')),'áéíóúüñ','aeiouun') ILIKE %s
                        OR translate(lower(c.nombre),'áéíóúüñ','aeiouun') ILIKE %s OR translate(lower(COALESCE(m.nombre, '')),'áéíóúüñ','aeiouun') ILIKE %s
                        OR translate(lower(COALESCE(p.material, '')),'áéíóúüñ','aeiouun') ILIKE %s OR translate(lower(t.nombre),'áéíóúüñ','aeiouun') ILIKE %s
                        OR translate(lower(co.nombre),'áéíóúüñ','aeiouun') ILIKE %s OR translate(lower(s.nombre),'áéíóúüñ','aeiouun') ILIKE %s OR translate(lower(ci.nombre),'áéíóúüñ','aeiouun') ILIKE %s
                    )
                    """
                )
                busqueda_params.extend([like] * 9)
                scores.append(
                    """
                    CASE WHEN (
                        translate(lower(p.nombre),'áéíóúüñ','aeiouun') ILIKE %s OR translate(lower(COALESCE(p.descripcion, '')),'áéíóúüñ','aeiouun') ILIKE %s
                        OR translate(lower(c.nombre),'áéíóúüñ','aeiouun') ILIKE %s OR translate(lower(COALESCE(m.nombre, '')),'áéíóúüñ','aeiouun') ILIKE %s
                        OR translate(lower(COALESCE(p.material, '')),'áéíóúüñ','aeiouun') ILIKE %s OR translate(lower(t.nombre),'áéíóúüñ','aeiouun') ILIKE %s
                        OR translate(lower(co.nombre),'áéíóúüñ','aeiouun') ILIKE %s OR translate(lower(s.nombre),'áéíóúüñ','aeiouun') ILIKE %s OR translate(lower(ci.nombre),'áéíóúüñ','aeiouun') ILIKE %s
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
                p.nombre, p.descripcion, p.material, pv.id AS variante_id, s.id AS sucursal_id,
                c.nombre AS categoria,
                m.nombre AS marca,
                t.nombre AS talla,
                co.nombre AS color,
                s.nombre AS sucursal,
                ci.nombre AS ciudad,
                inv.stock_disponible::INT,
                inv.stock_reservado::INT,
                (inv.stock_disponible - inv.stock_reservado)::INT AS stock_real,
                pp.precio AS precio_vigente, precio_catalogo(pv.id, inv.empresa_id, s.id) AS precio_final,
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
            LEFT JOIN LATERAL (SELECT precio FROM precio_producto precio
                WHERE precio.producto_variante_id=pv.id AND precio.empresa_id=inv.empresa_id AND precio.activo
                AND CURRENT_DATE BETWEEN precio.fecha_inicio AND coalesce(precio.fecha_fin,CURRENT_DATE)
                ORDER BY precio.fecha_inicio DESC,precio.id DESC LIMIT 1) pp ON TRUE
            WHERE {' AND '.join(condiciones)}
              AND {busqueda_sql}
            ORDER BY relevancia DESC, p.nombre ASC, s.nombre ASC, t.nombre ASC, co.nombre ASC, p.id,s.id,pv.id
            LIMIT %s;
            """,
            [*score_params, *filtros_params, *busqueda_params, limite],
        )
        resultado = [dict(row) for row in cursor.fetchall()]
        from app.modules.catalogo.repositories.catalogo_publico_repository import _obtener_promocion
        for row in resultado:
            row['promocion'] = _obtener_promocion(cursor,row['producto_id'],empresa_id,row['sucursal_id'])
        return resultado
    finally:
        cursor.close()
        connection.close()


def listar_sucursales_para_asistente(empresa_id: int, limite: int = 10) -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute("SET LOCAL statement_timeout='5000ms'")
        cursor.execute(
            """
            SELECT s.id, s.nombre, ci.nombre AS ciudad, s.direccion, s.telefono
            FROM sucursal s
            JOIN ciudad ci ON ci.id = s.ciudad_id
            WHERE s.activo = TRUE AND ci.activo = TRUE AND s.empresa_id = %s
            ORDER BY ci.nombre ASC, s.nombre ASC
            LIMIT %s;
            """,
            (empresa_id, limite),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()
