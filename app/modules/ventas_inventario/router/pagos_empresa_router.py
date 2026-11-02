from decimal import Decimal
from uuid import UUID
import hashlib,hmac,time
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel
from app.modules.autenticacion.dependencies.admin_required import requerir_admin
from app.modules.autenticacion.dependencies.usuario_actual import obtener_usuario_actual
from app.core.contexto_empresa import exigir_empresa_id
from app.modules.ventas_inventario.services import pagos_empresa_service as pagos
from app.modules.ventas_inventario.services import notificaciones_service as notas
from app.modules.ventas_inventario.services.pago_service import _orden_response

router=APIRouter(prefix='/api/v1/pagos-empresa',tags=['Pagos por empresa · pruebas'])
notificaciones=APIRouter(prefix='/api/v1/notificaciones',tags=['Notificaciones propias'])

@router.get('/configuracion')
def consultar_configuracion(actor=Depends(requerir_admin)):
    return pagos.configuracion_publica(exigir_empresa_id(actor))

@router.put('/configuracion')
def configurar(datos:pagos.ConfiguracionPago,actor=Depends(requerir_admin)):
    return pagos.guardar_configuracion(actor,datos)

@router.get('/medios')
def medios(actor=Depends(obtener_usuario_actual)):
    cfg=pagos.configuracion_publica(exigir_empresa_id(actor))
    return {k:cfg[k] for k in ('modo','stripe_habilitado','qr_habilitado','titular','confirmacion_prueba','stripe_conexion','qr_conexion')}

@router.get('/pendiente')
def pendiente(actor=Depends(obtener_usuario_actual)):
    from app.modules.autenticacion.repositories.perfil_repository import _transaccion
    with _transaccion() as cur:
        cur.execute("""SELECT o.* FROM orden_pago o JOIN cliente c ON c.id=o.cliente_id AND c.empresa_id=o.empresa_id
            WHERE o.empresa_id=%s AND c.usuario_id=%s AND o.estado='PENDIENTE' AND o.modo_pago='PRUEBA'
            ORDER BY o.id DESC LIMIT 1""",(exigir_empresa_id(actor),actor['id']))
        o=cur.fetchone()
    return _orden_response(dict(o)) if o else None

@router.post('/ordenes/{oid}/cancelar')
def cancelar(oid:int,actor=Depends(obtener_usuario_actual)):
    return _orden_response(pagos.cancelar(actor,oid))

@router.get('/reembolsos')
def reembolsos(actor=Depends(obtener_usuario_actual)):
    return pagos.reembolsos(actor)

class Resultado(BaseModel):
    aprobar:bool=True

@router.post('/reembolsos/{rid}/simular')
def simular(rid:int,datos:Resultado,actor=Depends(requerir_admin)):
    return pagos.simular_reembolso(actor,rid,datos.aprobar)

@router.post('/eventos-prueba/{empresa}')
async def evento_prueba(empresa:int,request:Request):
    # Contrato interno de simulación, no representa una API publicada por BCP.
    secret=pagos.secreto(empresa,'EVENTOS_PRUEBA_SECRET')
    if not pagos.habilitado_pruebas() or len(secret)<32:
        raise HTTPException(503,'No se configuraron los eventos firmados del entorno de pruebas.')
    raw=await request.body()
    timestamp=request.headers.get('x-stylear-timestamp','')
    try:
        if abs(time.time()-int(timestamp))>300:raise ValueError()
    except ValueError:raise HTTPException(400,'Marca de tiempo inválida o vencida.')
    esperado=hmac.new(secret.encode(),timestamp.encode()+b'.'+raw,hashlib.sha256).hexdigest()
    if not hmac.compare_digest(esperado,request.headers.get('x-stylear-signature','')):
        raise HTTPException(400,'Firma inválida.')
    try:datos=pagos.EventoPrueba.model_validate_json(raw)
    except ValueError:raise HTTPException(422,'Evento de prueba inválido.')
    if datos.empresa_id!=empresa:raise HTTPException(409,'Empresa incompatible con el endpoint firmado.')
    orden=pagos.repo.obtener_orden_pago(datos.orden_id,empresa)
    if not orden or not str(orden['proveedor_session_id']).startswith(('cs_simulada_','qr_prueba_')):
        raise HTTPException(409,'Este endpoint sólo procesa sesiones simuladas.')
    return _orden_response(pagos.procesar_evento(datos))

@router.post('/bcp/webhook/{empresa}')
async def bcp_pendiente(empresa:int):
    raise HTTPException(503,'Conexión BCP pendiente de contrato, documentación y credenciales. No se confirman pagos reales.')

@router.post('/stripe/webhook/{empresa}')
async def stripe_webhook(empresa:int,request:Request):
    secret=pagos.secreto(empresa,'STRIPE_WEBHOOK_SECRET')
    if not secret:raise HTTPException(503,'La empresa no tiene configurada su firma Stripe de pruebas.')
    import stripe
    try:evento=stripe.Webhook.construct_event(await request.body(),request.headers.get('stripe-signature',''),secret)
    except Exception:raise HTTPException(400,'Firma Stripe inválida.')
    if evento.get('livemode') is not False:raise HTTPException(403,'Este bloque sólo admite Stripe de prueba.')
    tipo=evento.get('type');obj=evento.get('data',{}).get('object',{})
    if tipo in ('refund.created','refund.updated','refund.failed'):
        if (obj.get('metadata') or {}).get('devolucion_id'):
            from app.modules.ventas_inventario.services.posventa_service import conciliar
            return conciliar(empresa,obj)
        return confirmar_refund(empresa,obj)
    if tipo not in ('checkout.session.completed','checkout.session.async_payment_succeeded','checkout.session.async_payment_failed','checkout.session.expired'):
        return {'estado':'IGNORADO'}
    meta=obj.get('metadata') or {}
    try:
        oid=int(meta['orden_id']);eid=int(meta['empresa_id'])
        amount=obj['amount_total']
        if eid!=empresa or not isinstance(amount,int) or isinstance(amount,bool):raise ValueError()
    except (ValueError,TypeError,KeyError):raise HTTPException(409,'Empresa, orden o importe de Stripe inválidos.')
    if tipo in ('checkout.session.completed','checkout.session.async_payment_succeeded') and obj.get('payment_status')!='paid':
        return {'estado':'PENDIENTE'}
    orden=pagos.repo.obtener_orden_pago(oid,empresa)
    if not orden or str(orden.get('proveedor_session_id','')).startswith('cs_simulada_'):
        raise HTTPException(409,'La sesión no corresponde a un checkout Stripe conectado.')
    try:
        datos=pagos.EventoPrueba(evento_id=evento['id'],orden_id=oid,empresa_id=empresa,proveedor='STRIPE',
        session_id=obj.get('id',''),pago_id=obj.get('payment_intent') or orden.get('proveedor_pago_id') or f"sin-pago-{oid}",
        monto_centavos=amount,moneda=str(obj.get('currency','')).upper(),
            tipo='PAGADO' if obj.get('payment_status')=='paid' else 'RECHAZADO')
    except ValueError:raise HTTPException(409,'Datos de confirmación Stripe inválidos.')
    resultado=pagos.procesar_evento(datos)
    if resultado['estado']=='REEMBOLSO_PENDIENTE':solicitar_refund_stripe(empresa,oid)
    return {'estado':resultado['estado']}


def solicitar_refund_stripe(empresa,oid):
    """Reintentos Stripe usan siempre la misma clave; un timeout queda pendiente."""
    from app.modules.autenticacion.repositories.perfil_repository import _transaccion
    key=pagos.secreto(empresa,'STRIPE_SECRET_KEY')
    if not key.startswith('sk_test_'):return
    with _transaccion() as cur:
        cur.execute('''SELECT r.*,o.proveedor_pago_id FROM reembolso_pago r JOIN orden_pago o ON o.id=r.orden_id AND o.empresa_id=r.empresa_id
            WHERE r.orden_id=%s AND r.empresa_id=%s''',(oid,empresa))
        fila=cur.fetchone()
    if not fila or fila['estado']=='CONFIRMADO':return
    import stripe
    try:
        resultado=stripe.Refund.create(api_key=key,idempotency_key=f"reembolso-{empresa}-{fila['id']}",
            payment_intent=fila['proveedor_pago_id'],amount=int(Decimal(fila['monto'])*100),
            metadata={'empresa_id':str(empresa),'orden_id':str(oid),'reembolso_pago_id':str(fila['id'])})
        confirmar_refund(empresa,dict(resultado))
    except Exception:
        # No afirmar fracaso ni devolver dinero de nuevo ante un resultado incierto.
        return


def confirmar_refund(empresa,obj):
    from app.modules.autenticacion.repositories.perfil_repository import _transaccion
    meta=obj.get('metadata') or {}
    try:
        rid=int(meta['reembolso_pago_id']);oid=int(meta['orden_id'])
        if int(meta['empresa_id'])!=empresa:raise ValueError()
    except (ValueError,TypeError,KeyError):raise HTTPException(409,'Reembolso sin metadatos válidos.')
    with _transaccion() as cur:
        cur.execute('SELECT id FROM empresa WHERE id=%s FOR UPDATE',(empresa,))
        cur.execute('SELECT * FROM orden_pago WHERE id=%s AND empresa_id=%s FOR UPDATE',(oid,empresa))
        orden=cur.fetchone()
        cur.execute('SELECT * FROM reembolso_pago WHERE id=%s AND empresa_id=%s AND orden_id=%s FOR UPDATE',(rid,empresa,oid))
        r=cur.fetchone()
        if not orden or not r or orden['proveedor']!='STRIPE' or orden['modo_pago']!='PRUEBA':raise HTTPException(409,'Reembolso no encontrado en el comercio.')
        if obj.get('livemode') is True or obj.get('payment_intent')!=orden['proveedor_pago_id'] or obj.get('amount')!=int(Decimal(r['monto'])*100) or str(obj.get('currency','')).upper()!=r['moneda']:
            raise HTTPException(409,'El reembolso no coincide con el pago, moneda o importe original.')
        if r['referencia'] and r['referencia']!=obj.get('id'):raise HTTPException(409,'Referencia de reembolso incompatible.')
        if r['estado']!='CONFIRMADO':
            estado={'succeeded':'CONFIRMADO','failed':'FALLIDO','canceled':'FALLIDO'}.get(obj.get('status'),'PENDIENTE')
            cur.execute('UPDATE reembolso_pago SET estado=%s,referencia=%s,actualizado_en=CURRENT_TIMESTAMP WHERE id=%s',(estado,obj['id'],rid))
            if estado=='CONFIRMADO':
                cur.execute("UPDATE orden_pago SET estado='REEMBOLSADO' WHERE id=%s",(oid,))
                pagos.notificar(cur,dict(orden),f'reembolsado:{rid}','Reembolso confirmado','Stripe confirmó el reembolso en el entorno de pruebas.')
    return {'estado':'RECIBIDO'}

@router.post('/reembolsos/{rid}/reintentar')
def reintentar(rid:int,actor=Depends(requerir_admin)):
    filas=pagos.reembolsos(actor)
    r=next((r for r in filas if r['id']==rid),None)
    if not r:raise HTTPException(404,'Reembolso no encontrado.')
    solicitar_refund_stripe(exigir_empresa_id(actor),r['orden_id'])
    return {'mensaje':'Se consultó o reintentó la misma operación. Revise su estado.'}

@notificaciones.get('')
def lista(actor=Depends(obtener_usuario_actual)):return notas.listar(actor)

@notificaciones.get('/estado')
def estado(actor=Depends(obtener_usuario_actual)):
    exigir_empresa_id(actor)
    return notas.estado()

@notificaciones.patch('/{nid}/leer')
def leer(nid:int,actor=Depends(obtener_usuario_actual)):return notas.leer(actor,nid)

@notificaciones.post('/dispositivos')
def registrar(datos:notas.DispositivoRequest,actor=Depends(obtener_usuario_actual)):return notas.registrar(actor,datos)

@notificaciones.delete('/dispositivos/{instalacion}')
def retirar(instalacion:UUID,actor=Depends(obtener_usuario_actual)):return notas.retirar(actor,instalacion)
