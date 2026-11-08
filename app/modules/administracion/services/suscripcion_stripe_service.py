"""Facturación mensual en Stripe de prueba para el plan asignado a la empresa."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException
import stripe

from app.modules.autenticacion.repositories.perfil_repository import _transaccion


EVENTOS = {
    'checkout.session.completed', 'checkout.session.expired',
    'invoice.paid', 'customer.subscription.deleted',
}
ZONA_EMPRESA = ZoneInfo('America/La_Paz')
MONEDAS_SIN_DECIMALES = {
    'bif', 'clp', 'djf', 'gnf', 'jpy', 'kmf', 'krw', 'mga',
    'pyg', 'rwf', 'vnd', 'vuv', 'xaf', 'xof', 'xpf',
}


def _clave():
    clave = os.getenv('STRIPE_SECRET_KEY', '').strip()
    return clave if clave.startswith('sk_test_') and not clave.startswith('sk_test_placeholder') else ''


def _stripe_configurado():
    return bool(_clave() and os.getenv('STRIPE_WEBHOOK_SECRET', '').strip())


def _frontend():
    return os.getenv('FRONTEND_URL', 'http://localhost:4200').rstrip('/') + '/mi-plan'


def _plan_actual(cur, empresa):
    cur.execute("""SELECT s.id AS suscripcion_id, s.estado, s.fecha_inicio,
                          p.activo, p.stripe_price_id, p.precio, p.moneda, e.estado AS empresa_estado
                   FROM suscripcion s JOIN plan p ON p.id=s.plan_id
                   JOIN empresa e ON e.id=s.empresa_id
                   WHERE s.empresa_id=%s ORDER BY s.fecha_creacion DESC,s.id DESC LIMIT 1""", (empresa,))
    return cur.fetchone()


def _abierta(cur, empresa):
    cur.execute("""SELECT * FROM suscripcion_stripe
                   WHERE empresa_id=%s AND estado IN ('PENDIENTE','ACTIVA')""", (empresa,))
    return cur.fetchone()


def _puede_iniciar(plan):
    return bool(plan and plan['stripe_price_id'] and plan['activo']
                and plan['empresa_estado'] == 'ACTIVA' and plan['estado'] in ('ACTIVA', 'VENCIDA')
                and plan['fecha_inicio'] <= datetime.now(ZONA_EMPRESA).date())


def estado(empresa):
    with _transaccion() as cur:
        plan = _plan_actual(cur, empresa)
        abierta = _abierta(cur, empresa)
    precio = abierta['importe'] if abierta else plan['precio'] if plan else None
    moneda = abierta['moneda'] if abierta else plan['moneda'] if plan else None
    return {
        'estado': abierta['estado'] if abierta else None,
        'importe': str(precio) if precio is not None else None,
        'moneda': moneda,
        'puede_pagar': _stripe_configurado() and _puede_iniciar(plan)
                       and (not abierta or abierta['estado'] == 'PENDIENTE'),
        'puede_gestionar': bool(_clave() and abierta and abierta['stripe_cliente_id']),
    }


def checkout(empresa):
    if not _stripe_configurado():
        raise HTTPException(503, 'Configura Stripe de prueba y su webhook para cobrar la suscripción.')
    clave = _clave()
    ahora = datetime.now(timezone.utc)
    with _transaccion() as cur:
        cur.execute('SELECT id FROM empresa WHERE id=%s FOR UPDATE', (empresa,))
        plan = _plan_actual(cur, empresa)
        intento = _abierta(cur, empresa)
        if intento and intento['estado'] == 'ACTIVA':
            raise HTTPException(409, 'Esta empresa ya tiene una suscripción mensual en Stripe.')
        if intento and intento['checkout_expira'] and intento['checkout_expira'] <= ahora:
            # Sólo el webhook de expiración puede cerrar un intento que Stripe pudo cobrar.
            raise HTTPException(409, 'Stripe todavía está confirmando el cierre de la sesión anterior.')
        if not _puede_iniciar(plan):
            raise HTTPException(409, 'El plan asignado no está habilitado para cobro mensual.')
        if not intento:
            cur.execute("""INSERT INTO suscripcion_stripe
                           (id,empresa_id,suscripcion_id,stripe_price_id,importe,moneda)
                           VALUES (%s,%s,%s,%s,%s,%s) RETURNING *""",
                        (str(uuid4()), empresa, plan['suscripcion_id'], plan['stripe_price_id'],
                         plan['precio'], plan['moneda']))
            intento = cur.fetchone()
    if intento['checkout_url']:
        return {'url': intento['checkout_url']}
    if ahora - intento['creado_en'] > timedelta(hours=23):
        raise HTTPException(409, 'Revisa el intento de cobro pendiente en Stripe antes de volver a pagar.')
    metadata = {'stylear_suscripcion': str(intento['id']), 'empresa_id': str(empresa)}
    try:
        precio = stripe.Price.retrieve(intento['stripe_price_id'], api_key=clave)
        moneda = str(precio.get('currency', '')).lower()
        multiplicador = 1 if moneda in MONEDAS_SIN_DECIMALES else 100
        recurrente = precio.get('recurring') or {}
        if (not precio.get('active') or precio.get('livemode') is not False
                or recurrente.get('interval') != 'month' or recurrente.get('interval_count') != 1
                or recurrente.get('usage_type') != 'licensed'
                or moneda != intento['moneda'].lower()
                or precio.get('unit_amount') != Decimal(intento['importe']) * multiplicador):
            raise HTTPException(422, 'El precio Stripe debe ser mensual y coincidir con el importe y la moneda del plan.')
        sesion = stripe.checkout.Session.create(
            api_key=clave, idempotency_key=f'stylear-plan-{intento["id"]}',
            mode='subscription', payment_method_types=['card'],
            line_items=[{'price': intento['stripe_price_id'], 'quantity': 1}],
            metadata=metadata, subscription_data={'metadata': metadata},
            success_url=_frontend() + '?stripe=pendiente',
            cancel_url=_frontend(),
        )
    except (HTTPException, stripe.InvalidRequestError) as error:
        with _transaccion() as cur:
            cur.execute("""UPDATE suscripcion_stripe SET estado='CERRADA'
                           WHERE id=%s AND checkout_id IS NULL AND stripe_suscripcion_id IS NULL""", (intento['id'],))
        if isinstance(error, HTTPException):
            raise
        raise HTTPException(422, 'Stripe no pudo usar el precio configurado para este plan.') from error
    except stripe.StripeError as error:
        raise HTTPException(503, 'Stripe no respondió. Puedes reintentar la misma operación.') from error
    with _transaccion() as cur:
        cur.execute("""UPDATE suscripcion_stripe SET checkout_id=%s,checkout_url=%s,
                       checkout_expira=to_timestamp(%s)
                       WHERE id=%s AND estado='PENDIENTE' RETURNING id""",
                    (sesion.id, sesion.url, sesion.expires_at, intento['id']))
        if not cur.fetchone():
            raise HTTPException(409, 'La sesión cambió de estado. Actualiza Mi plan.')
    return {'url': sesion.url}


def portal(empresa):
    with _transaccion() as cur:
        intento = _abierta(cur, empresa)
    clave = _clave()
    if not clave or not intento or not intento['stripe_cliente_id']:
        raise HTTPException(409, 'Esta empresa todavía no tiene una suscripción para gestionar.')
    try:
        sesion = stripe.billing_portal.Session.create(
            api_key=clave, customer=intento['stripe_cliente_id'], return_url=_frontend(),
        )
    except stripe.StripeError as error:
        raise HTTPException(503, 'No se pudo abrir el portal. Revisa su configuración en Stripe de prueba.') from error
    return {'url': sesion.url}


def procesar_evento(tipo, objeto):
    """Devuelve None si el evento no pertenece a la facturación SaaS."""
    if tipo not in EVENTOS:
        return None
    meta = objeto.get('metadata') or {}
    if tipo == 'invoice.paid':
        detalles = (objeto.get('parent') or {}).get('subscription_details') or objeto.get('subscription_details') or {}
        meta = detalles.get('metadata') or {}
        suscripcion = detalles.get('subscription') or objeto.get('subscription')
    elif tipo == 'customer.subscription.deleted':
        suscripcion = objeto.get('id')
    else:
        if objeto.get('mode') != 'subscription':
            return None
        suscripcion = objeto.get('subscription')
    referencia = meta.get('stylear_suscripcion')
    if not referencia:
        return None
    try:
        intento_id = str(UUID(referencia))
        empresa = int(meta['empresa_id'])
    except (TypeError, ValueError, KeyError) as error:
        raise HTTPException(409, 'Referencia de suscripción Stripe inválida.') from error
    with _transaccion() as cur:
        cur.execute('SELECT id FROM empresa WHERE id=%s FOR UPDATE', (empresa,))
        cur.execute('SELECT * FROM suscripcion_stripe WHERE id=%s AND empresa_id=%s FOR UPDATE', (intento_id, empresa))
        intento = cur.fetchone()
        if not intento:
            return {'status': 'ignorado'}
        if suscripcion and intento['stripe_suscripcion_id'] not in (None, suscripcion):
            raise HTTPException(409, 'La suscripción Stripe no coincide con el intento guardado.')
        if tipo.startswith('checkout.session.'):
            if intento['checkout_id'] not in (None, objeto.get('id')):
                raise HTTPException(409, 'La sesión Stripe no coincide con el intento guardado.')
            if tipo == 'checkout.session.expired':
                cur.execute("""UPDATE suscripcion_stripe SET estado='CERRADA'
                               WHERE id=%s AND estado='PENDIENTE' AND stripe_suscripcion_id IS NULL""", (intento_id,))
            elif suscripcion and intento['estado'] != 'CERRADA':
                cur.execute("""UPDATE suscripcion_stripe SET checkout_id=%s,
                               stripe_suscripcion_id=%s,stripe_cliente_id=COALESCE(%s,stripe_cliente_id) WHERE id=%s""",
                            (objeto['id'], suscripcion, objeto.get('customer'), intento_id))
        elif tipo == 'customer.subscription.deleted':
            cur.execute("""UPDATE suscripcion_stripe SET estado='CERRADA',stripe_suscripcion_id=%s
                           WHERE id=%s""", (suscripcion, intento_id))
        elif suscripcion and objeto.get('status') == 'paid':
            _aplicar_periodo(cur, intento, suscripcion, objeto)
    return {'status': 'ok'}


def _aplicar_periodo(cur, intento, suscripcion, factura):
    lineas = (factura.get('lines') or {}).get('data', [])
    finales = []
    for linea in lineas:
        precio = (linea.get('price') or {}).get('id')
        precio = precio or ((linea.get('pricing') or {}).get('price_details') or {}).get('price')
        detalles = (linea.get('parent') or {}).get('subscription_item_details') or {}
        fin = (linea.get('period') or {}).get('end')
        if (precio == intento['stripe_price_id'] and not linea.get('proration')
                and not detalles.get('proration') and isinstance(fin, int)):
            finales.append(fin)
    if not finales:
        raise HTTPException(409, 'La factura no incluye el periodo del precio contratado.')
    hasta = datetime.fromtimestamp(max(finales), timezone.utc)
    anterior = intento['pagado_hasta']
    if anterior and hasta <= anterior:
        return
    if intento['estado'] == 'CERRADA' and not intento['stripe_suscripcion_id']:
        return
    cur.execute("""SELECT id FROM suscripcion_stripe WHERE empresa_id=%s
                   ORDER BY creado_en DESC,id DESC LIMIT 1""", (intento['empresa_id'],))
    if cur.fetchone()['id'] != intento['id']:
        return
    vigencia = (hasta - timedelta(microseconds=1)).astimezone(ZONA_EMPRESA).date()
    cur.execute("""UPDATE suscripcion SET estado='ACTIVA', fecha_vencimiento=%s
                   WHERE id=%s AND empresa_id=%s AND estado IN ('ACTIVA','VENCIDA')
                     AND fecha_inicio<=%s""",
                (vigencia, intento['suscripcion_id'], intento['empresa_id'], vigencia))
    if not cur.rowcount:
        raise HTTPException(409, 'El periodo pagado no corresponde a la suscripción asignada.')
    cur.execute("""UPDATE suscripcion_stripe SET stripe_suscripcion_id=%s,stripe_cliente_id=COALESCE(%s,stripe_cliente_id),
                   pagado_hasta=%s,estado=CASE WHEN estado='CERRADA' THEN estado ELSE 'ACTIVA' END
                   WHERE id=%s""", (suscripcion, factura.get('customer'), hasta, intento['id']))
