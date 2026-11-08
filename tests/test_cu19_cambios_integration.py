from decimal import Decimal
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
import pytest
from test_multitenant_integration import actor,empresas,consulta,mercaderia
from test_cu16_bloque1_integration import api,preparar,checkout,evento
from test_cuenta_integration import login

BASE='/api/v1/posventa/cambios'

@pytest.fixture
def compra(api,empresas):
 a,b,_,_=empresas;ha,h,sid,vid,uid=preparar(api,a,10)
 o,_=checkout(api,h,sid);assert api.post(f'/api/v1/pagos/qr/confirmar/{o["orden_id"]}',headers=h).status_code==200
 p={'version':0,'cambios_habilitados':True,'plazo_cambios':15,'condiciones_cambios':'Inspección en sucursal antes de entregar reemplazo'}
 assert api.put('/api/v1/posventa/politica',headers=ha,json=p).status_code==200
 vd=consulta('SELECT id FROM venta_detalle WHERE venta_id=%s',(o['venta_id'],),True)['id']
 from test_multitenant_integration import variantes
 from datetime import date
 v=consulta('SELECT pv.*,p.categoria_id FROM producto_variante pv JOIN producto p ON p.id=pv.producto_id WHERE pv.id=%s',(vid,),True)
 pid=consulta("INSERT INTO producto(empresa_id,categoria_id,nombre) VALUES(%s,%s,'Reemplazo') RETURNING id",(a['id'],v['categoria_id']),True)['id']
 rv=variantes.crear_variante(a['id'],pid,v['talla_id'],v['color_id'],'REEMPLAZO')
 variantes.asignar_precio(rv,a['id'],Decimal('50'),date(2020,1,1),None)
 consulta('INSERT INTO inventario_sucursal(empresa_id,sucursal_id,producto_variante_id,stock_disponible) VALUES(%s,%s,%s,5)',(a['id'],sid,rv))
 return dict(a=a,b=b,ha=ha,h=h,sid=sid,vid=vid,rv=rv,venta=o['venta_id'],vd=vd)

def solicitud(api,c):
 body={'clave_operacion':str(uuid4()),'venta_id':c['venta'],'venta_detalle_id':c['vd'],'cantidad':1,'motivo':'Necesito otra talla'}
 r=api.post(BASE,headers=c['h'],json=body);assert r.status_code==201,r.text
 return r.json(),body

def aprobado(api,c,no_vendibles=0):
 x,_=solicitud(api,c)
 r=api.patch(f'{BASE}/{x["id"]}/revision',headers=c['ha'],json={'version':x['version'],'aceptar':True,'recepcion_confirmada':True,'no_vendibles':no_vendibles,'condicion':'Revisión física de costura y etiquetas'});assert r.status_code==200,r.text
 return r.json()

def aceptado(api,c,precio=50,no_vendibles=0):
 x=aprobado(api,c,no_vendibles)
 consulta('UPDATE precio_producto SET precio=%s WHERE producto_variante_id=%s',(precio,c['rv']))
 r=api.post(f'{BASE}/{x["id"]}/cotizar',headers=c['h'],json={'version':x['version'],'reemplazo_id':c['rv']});assert r.status_code==200,r.text;x=r.json()
 r=api.post(f'{BASE}/{x["id"]}/aceptar',headers=c['h'],json={'version':x['version'],'diferencia':x['diferencia']});assert r.status_code==200,r.text
 return r.json()

def stock(c,variante):return consulta('SELECT stock_disponible,stock_reservado FROM inventario_sucursal WHERE sucursal_id=%s AND producto_variante_id=%s',(c['sid'],variante),True)

@pytest.mark.parametrize('no_vendibles',[0,1])
def test_igual_precio_reserva_y_entrega_unica_con_inspeccion(api,compra,no_vendibles):
 c=compra;x=aceptado(api,c,no_vendibles=no_vendibles);assert x['estado']=='LISTO'
 assert stock(c,c['rv'])==dict(stock_disponible=5,stock_reservado=1)
 assert stock(c,c['vid'])['stock_disponible']==9
 url=f'{BASE}/{x["id"]}/completar';body={'version':x['version'],'entrega_confirmada':True}
 assert api.post(url,headers=c['h'],json=body).status_code==403
 assert api.post(url,headers=c['ha'],json={**body,'entrega_confirmada':False}).status_code==409
 for _ in range(2):
  r=api.post(url,headers=c['ha'],json=body);assert r.status_code==200 and r.json()['comprobante'],r.text
 assert stock(c,c['rv'])==dict(stock_disponible=4,stock_reservado=0)
 assert stock(c,c['vid'])['stock_disponible']==10-no_vendibles
 if no_vendibles:
  mov=consulta("""SELECT cantidad,stock_anterior,stock_nuevo FROM movimiento_inventario
                  WHERE referencia_tipo='CAMBIO' AND referencia_id=%s AND tipo='DEVOLUCION_NO_VENDIBLE'""",
               (x['id'],),True)
  assert mov==dict(cantidad=1,stock_anterior=9,stock_nuevo=9)
 assert api.get(BASE+'/elegibles',headers=c['h']).json()==[]
 assert api.get('/api/v1/devoluciones/ventas-elegibles',headers=c['h']).json()==[]

@pytest.mark.parametrize('medio',['QR_BCP','STRIPE'])
def test_diferencia_mayor_pago_idempotente_antes_de_entregar(api,compra,medio):
 c=compra;x=aceptado(api,c,70);assert x['estado']=='ESPERA_PAGO'
 assert api.post(f'{BASE}/{x["id"]}/completar',headers=c['ha'],json={'version':x['version'],'entrega_confirmada':True}).status_code==409
 url=f'{BASE}/{x["id"]}/pago';body={'version':x['version'],'medio':medio}
 with ThreadPoolExecutor(2) as pool:rs=list(pool.map(lambda _:api.post(url,headers=c['h'],json=body),range(2)))
 assert all(r.status_code==200 for r in rs),[r.text for r in rs]
 ids={r.json()['pago']['id'] for r in rs};assert len(ids)==1;oid=ids.pop()
 ruta='qr/confirmar' if medio=='QR_BCP' else 'stripe/confirmar-prueba'
 for _ in range(2):assert api.post(f'/api/v1/pagos/{ruta}/{oid}',headers=c['h'],json={'aprobar':True}).status_code==200
 x=api.get(BASE,headers=c['h']).json()[0];assert x['estado']=='LISTO'
 assert Decimal(x['pago']['monto_total'])==20
 assert stock(c,c['rv'])['stock_disponible']==5
 assert api.post(f'{BASE}/{x["id"]}/completar',headers=c['ha'],json={'version':x['version'],'entrega_confirmada':True}).status_code==200
 assert stock(c,c['rv'])['stock_disponible']==4

def test_menor_precio_reintegra_solo_excedente_por_medio_original(api,compra):
 c=compra;x=aceptado(api,c,30);assert x['estado']=='ESPERA_REINTEGRO'
 assert Decimal(x['original']['importe_reintegro'])==20
 assert api.post(f'/api/v1/devoluciones/{x["id"]}/reembolso',headers=c['ha'],json={}).status_code==409
 r=api.post(f'{BASE}/{x["id"]}/reintegro',headers=c['ha']);assert r.status_code==200,r.text;x=r.json();assert x['estado']=='LISTO'
 assert api.post(f'{BASE}/{x["id"]}/completar',headers=c['ha'],json={'version':x['version'],'entrega_confirmada':True}).status_code==200

def test_stock_precio_version_y_cotizacion_vencida(api,compra):
 c=compra;x=aprobado(api,c);url=f'{BASE}/{x["id"]}'
 r=api.post(url+'/cotizar',headers=c['h'],json={'version':x['version'],'reemplazo_id':c['rv']});x=r.json();body={'version':x['version'],'diferencia':x['diferencia']}
 assert api.post(url+'/aceptar',headers=c['h'],json={**body,'diferencia':999}).status_code==409
 consulta('UPDATE precio_producto SET precio=70 WHERE producto_variante_id=%s',(c['rv'],))
 assert api.post(url+'/aceptar',headers=c['h'],json=body).status_code==409
 consulta('UPDATE precio_producto SET precio=50 WHERE producto_variante_id=%s',(c['rv'],))
 consulta("UPDATE cambio_prenda SET cotizacion_vence=CURRENT_TIMESTAMP-INTERVAL '1 second' WHERE id=%s",(x['id'],))
 assert api.post(url+'/aceptar',headers=c['h'],json=body).status_code==409
 consulta('UPDATE inventario_sucursal SET stock_disponible=0 WHERE sucursal_id=%s AND producto_variante_id=%s',(c['sid'],c['rv']))
 assert api.post(url+'/cotizar',headers=c['h'],json={'version':x['version'],'reemplazo_id':c['rv']}).status_code==409
 assert stock(c,c['rv'])['stock_reservado']==0

def test_conversion_de_cambio_a_devolucion_con_aceptacion(api,compra):
 c=compra;x=aprobado(api,c);url=f'{BASE}/{x["id"]}'
 assert api.post(url+'/devolucion',headers=c['h'],json={'version':x['version']}).status_code==200
 r=api.post(f'/api/v1/posventa/devoluciones/{x["id"]}/aceptar',headers=c['h'],json={'monto':50});assert r.status_code==200,r.text
 assert api.post(f'/api/v1/devoluciones/{x["id"]}/reembolso',headers=c['ha'],json={}).status_code==200
 assert len(api.get('/api/v1/devoluciones/mis-devoluciones',headers=c['h']).json())==1

def test_cancelacion_libera_reserva_y_pago_tardio_va_a_reembolso(api,compra):
 c=compra;x=aceptado(api,c,70);url=f'{BASE}/{x["id"]}'
 x=api.post(url+'/pago',headers=c['h'],json={'version':x['version'],'medio':'QR_BCP'}).json();oid=x['pago']['id']
 assert api.post(url+'/cancelar',headers=c['h'],json={'version':x['version']}).status_code==200
 assert stock(c,c['rv'])['stock_reservado']==0
 r=api.post(f'/api/v1/pagos/qr/confirmar/{oid}',headers=c['h']);assert r.status_code==200 and r.json()['estado']=='REEMBOLSO_PENDIENTE',r.text
 assert stock(c,c['rv'])['stock_disponible']==5

def test_propiedad_aislamiento_reintento_y_cantidades_compartidas(api,compra):
 c=compra;x,body=solicitud(api,c);hb=login(api,c['b'],c['b']['codigo'])
 assert api.post(BASE,headers=c['h'],json=body).json()['id']==x['id']
 assert api.get(f'{BASE}/{x["id"]}/opciones',headers=hb).status_code==404
 assert api.patch(f'{BASE}/{x["id"]}/revision',headers=c['h'],json={'version':1,'aceptar':True,'recepcion_confirmada':True,'condicion':'Prenda en buen estado'}).status_code==403
 assert api.patch(f'/api/v1/devoluciones/mis-devoluciones/{x["id"]}/cancelar',headers=c['h'],json={}).status_code==409
 assert api.get(BASE+'/elegibles',headers=c['h']).json()==[]
 assert api.post('/api/v1/devoluciones/ventas/'+str(c['venta']),headers=c['h'],json={'clave_operacion':str(uuid4()),'motivo':'No puede duplicar cantidad','items':[{'venta_detalle_id':c['vd'],'cantidad':1}]}).status_code==400

def test_credito_pagado_con_descuento_y_centavos_en_tres_cambios_efectivo(api,compra):
 from test_cu11_cu15_integration import venta
 c=compra.copy();cid=consulta('SELECT cliente_id FROM venta WHERE id=%s',(c['venta'],),True)['cliente_id']
 r=venta(api,c['ha'],c['sid'],c['vid'],cliente_id=cid,items=[{'producto_variante_id':c['vid'],'cantidad':3,'descuento':50}]);assert r.status_code==200,r.text
 c['venta']=r.json()['id'];c['vd']=r.json()['detalles'][0]['id'];xs=[aprobado(api,c) for _ in range(3)]
 assert sum(Decimal(x['credito']) for x in xs)==100
 consulta('UPDATE precio_producto SET precio=30 WHERE producto_variante_id=%s',(c['rv'],))
 reintegros=[]
 for x in xs:
  url=f'{BASE}/{x["id"]}'
  x=api.post(url+'/cotizar',headers=c['h'],json={'version':x['version'],'reemplazo_id':c['rv']}).json()
  r=api.post(url+'/aceptar',headers=c['h'],json={'version':x['version'],'diferencia':x['diferencia']});assert r.status_code==200,r.text;x=r.json()
  reintegros.append(-Decimal(x['diferencia']))
  for _ in range(2):
   r=api.post(url+'/reintegro-efectivo',headers=c['ha'],json={'referencia':'CAJA-CAMBIO-'+str(x['id'])});assert r.status_code==200,r.text
  x=r.json();assert x['estado']=='LISTO'
  assert api.post(url+'/completar',headers=c['ha'],json={'version':x['version'],'entrega_confirmada':True}).status_code==200
 assert sum(reintegros)==10
 assert stock(c,c['rv'])==dict(stock_disponible=2,stock_reservado=0)

def test_reintegro_stripe_valida_excedente_y_actualiza_cambio_desde_callback(api,compra):
 from app.modules.ventas_inventario.services.posventa_service import conciliar
 from fastapi import HTTPException
 c=compra;x=aceptado(api,c,30)
 consulta("UPDATE orden_pago SET proveedor='STRIPE',proveedor_pago_id='pi_cambio' WHERE venta_id=%s",(c['venta'],))
 obj={'id':'re_cambio_'+uuid4().hex,'amount':2000,'currency':'bob','payment_intent':'pi_cambio','status':'succeeded','livemode':False,'metadata':{'empresa_id':str(c['a']['id']),'devolucion_id':str(x['id'])}}
 with pytest.raises(HTTPException):conciliar(c['a']['id'],{**obj,'amount':5000})
 for _ in range(2):assert conciliar(c['a']['id'],obj)['estado']=='RECIBIDO'
 x=api.get(BASE,headers=c['h']).json()[0];assert x['estado']=='LISTO'
 assert stock(c,c['rv'])['stock_disponible']==5
 assert api.post(f'{BASE}/{x["id"]}/completar',headers=c['ha'],json={'version':x['version'],'entrega_confirmada':True}).status_code==200
 assert conciliar(c['a']['id'],{**obj,'status':'failed'})['estado']=='RECIBIDO'
 assert consulta('SELECT estado FROM devolucion WHERE id=%s',(x['id'],),True)['estado']=='CAMBIO_COMPLETADO'

def test_cajero_de_sucursal_no_puede_inspeccionar_en_otra(api,compra):
 from test_multitenant_integration import crear_usuario_con_rol,hashear_password
 c=compra;x,_=solicitud(api,c);a=c['a'];nombre='ca'+uuid4().hex[:9]
 rid=consulta("SELECT id FROM rol WHERE nombre='CAJERO'",(),True)['id']
 u=crear_usuario_con_rol('Personal','Prueba',nombre,nombre+'@example.invalid',hashear_password('Prueba-aislada-123'),rid,'CAJERO',None,a['admin_usuario_id'],a['id'])
 consulta("INSERT INTO empleado(usuario_id,sucursal_id,codigo_empleado,cargo,empresa_id) VALUES(%s,%s,%s,'Prueba',%s)",(u['id'],c['sid'],nombre,a['id']))
 h=login(api,a,nombre)
 cuerpo={'version':x['version'],'aceptar':True,'recepcion_confirmada':True,'condicion':'Inspección en sucursal'}
 assert api.patch(f'{BASE}/{x["id"]}/revision',headers=h,json=cuerpo).status_code==200
 otra=consulta('SELECT s.id FROM sucursal s WHERE s.empresa_id=%s AND s.id<>%s LIMIT 1',(a['id'],c['sid']),True)
 if not otra:
  ciudad=consulta('SELECT ciudad_id FROM sucursal WHERE id=%s',(c['sid'],),True)['ciudad_id']
  otra=consulta("INSERT INTO sucursal(empresa_id,ciudad_id,nombre,direccion) VALUES(%s,%s,'Otra sucursal','Lejos') RETURNING id",(a['id'],ciudad),True)
 consulta('UPDATE empleado SET sucursal_id=%s WHERE usuario_id=%s',(otra['id'],u['id']))
 assert api.post(f'{BASE}/{x["id"]}/completar',headers=h,json={'version':2,'entrega_confirmada':True}).status_code==404


def test_datos_vacios_no_crean_solicitud_ni_inspeccion_o_recibo(api,compra):
 c=compra
 body={'clave_operacion':str(uuid4()),'venta_id':c['venta'],'venta_detalle_id':c['vd'],'cantidad':1,'motivo':'     '}
 assert api.post(BASE,headers=c['h'],json=body).status_code==422
 x,_=solicitud(api,c)
 assert api.patch(f'{BASE}/{x["id"]}/revision',headers=c['ha'],json={'version':x['version'],'aceptar':True,'recepcion_confirmada':True,'condicion':'     '}).status_code==422
 assert api.post(f'{BASE}/{x["id"]}/reintegro-efectivo',headers=c['ha'],json={'referencia':'   '}).status_code==422
 assert api.get(BASE,headers=c['h']).json()[0]['estado']=='SOLICITADO'


def test_desistir_cotizacion_menor_antes_de_aceptarla_libera_elegibilidad(api,compra):
 c=compra;x=aprobado(api,c);url=f'{BASE}/{x["id"]}'
 consulta('UPDATE precio_producto SET precio=30 WHERE producto_variante_id=%s',(c['rv'],))
 r=api.post(url+'/cotizar',headers=c['h'],json={'version':x['version'],'reemplazo_id':c['rv']});assert r.status_code==200;x=r.json()
 assert Decimal(x['diferencia'])==-20
 r=api.post(url+'/cancelar',headers=c['h'],json={'version':x['version']});assert r.status_code==200 and r.json()['estado']=='CANCELADO',r.text
 assert stock(c,c['rv'])['stock_reservado']==0
 assert len(api.get(BASE+'/elegibles',headers=c['h']).json())==1


def test_prenda_adicional_recalcula_pago_y_mueve_ambas_variantes_una_vez(api, compra):
    c = compra
    x = aprobado(api, c)
    url = f'{BASE}/{x["id"]}'
    consulta('UPDATE precio_producto SET precio=30 WHERE producto_variante_id=%s', (c['rv'],))
    r = api.post(url + '/cotizar', headers=c['h'], json={
        'version': x['version'], 'reemplazo_id': c['rv'], 'adicional_id': c['vid'],
    })
    assert r.status_code == 200, r.text
    x = r.json()
    assert Decimal(str(x['diferencia'])) == 30
    assert x['adicional_id'] == c['vid']
    r = api.post(url + '/aceptar', headers=c['h'], json={
        'version': x['version'], 'diferencia': 30,
    })
    assert r.status_code == 200, r.text
    assert stock(c, c['rv']) == dict(stock_disponible=5, stock_reservado=1)
    assert stock(c, c['vid']) == dict(stock_disponible=9, stock_reservado=1)
    x = api.post(url + '/pago', headers=c['h'], json={
        'version': r.json()['version'], 'medio': 'QR_BCP',
    }).json()
    pago = x['pago']
    assert Decimal(str(pago['monto_total'])) == 30
    assert api.post(f'/api/v1/pagos/qr/confirmar/{pago["id"]}', headers=c['h']).status_code == 200
    x = api.get(BASE, headers=c['h']).json()[0]
    for _ in range(2):
        r = api.post(url + '/completar', headers=c['ha'], json={
            'version': x['version'], 'entrega_confirmada': True,
        })
        assert r.status_code == 200, r.text
        assert r.json()['comprobante']['adicional_id'] == c['vid']
        assert r.json()['comprobante']['nota_venta_numero'] > 0
    assert stock(c, c['rv']) == dict(stock_disponible=4, stock_reservado=0)
    assert stock(c, c['vid']) == dict(stock_disponible=9, stock_reservado=0)
    assert consulta("SELECT count(*) AS n FROM movimiento_inventario WHERE referencia_tipo='CAMBIO' AND referencia_id=%s",
                    (x['id'],), True)['n'] == 3


def test_misma_variante_adicional_valida_stock_y_pasa_a_devolucion(api, compra):
    c = compra
    x = aprobado(api, c)
    url = f'{BASE}/{x["id"]}'
    consulta('UPDATE precio_producto SET precio=25 WHERE producto_variante_id=%s', (c['rv'],))
    consulta('UPDATE inventario_sucursal SET stock_disponible=1 WHERE sucursal_id=%s AND producto_variante_id=%s',
             (c['sid'], c['rv']))
    body = {'version': x['version'], 'reemplazo_id': c['rv'], 'adicional_id': c['rv']}
    assert api.post(url + '/cotizar', headers=c['h'], json=body).status_code == 409
    consulta('UPDATE inventario_sucursal SET stock_disponible=2 WHERE sucursal_id=%s AND producto_variante_id=%s',
             (c['sid'], c['rv']))
    x = api.post(url + '/cotizar', headers=c['h'], json=body).json()
    assert Decimal(str(x['diferencia'])) == 0
    x = api.post(url + '/aceptar', headers=c['h'], json={'version': x['version'], 'diferencia': 0}).json()
    assert x['estado'] == 'LISTO'
    assert stock(c, c['rv'])['stock_reservado'] == 2
    assert api.post(url + '/sin-reemplazo', headers=c['h'], json={'version': x['version']}).status_code == 403
    r = api.post(url + '/sin-reemplazo', headers=c['ha'], json={'version': x['version']})
    assert r.status_code == 200, r.text
    assert r.json()['estado'] == 'DEVOLUCION'
    assert stock(c, c['rv']) == dict(stock_disponible=2, stock_reservado=0)
    assert api.post(f'/api/v1/posventa/devoluciones/{x["id"]}/aceptar', headers=c['h'],
                    json={'monto': 50}).status_code == 200
    assert stock(c, c['vid'])['stock_disponible'] == 10


def test_plazo_delivery_empieza_con_entrega_confirmada(api, compra):
    c = compra
    consulta("UPDATE venta SET tipo_entrega='DELIVERY', fecha_venta=CURRENT_TIMESTAMP-INTERVAL '30 days' WHERE id=%s",
             (c['venta'],))
    consulta("""INSERT INTO delivery(empresa_id,venta_id,sucursal_id,direccion_entrega,
                 latitud_entrega,longitud_entrega,estado)
                 VALUES(%s,%s,%s,'Entrega de prueba',-17,-63,'EN_CAMINO')""",
             (c['a']['id'], c['venta'], c['sid']))
    assert api.get(BASE + '/elegibles', headers=c['h']).json() == []
    body = {'clave_operacion': str(uuid4()), 'venta_id': c['venta'], 'venta_detalle_id': c['vd'],
            'cantidad': 1, 'motivo': 'Necesito otra talla'}
    assert api.post(BASE, headers=c['h'], json=body).status_code == 409
    consulta("UPDATE delivery SET estado='ENTREGADO', fecha_entrega=CURRENT_TIMESTAMP-INTERVAL '16 days' WHERE venta_id=%s",
             (c['venta'],))
    assert api.post(BASE, headers=c['h'], json=body).status_code == 409
    consulta("UPDATE delivery SET fecha_entrega=CURRENT_TIMESTAMP WHERE venta_id=%s", (c['venta'],))
    assert len(api.get(BASE + '/elegibles', headers=c['h']).json()) == 1
    assert api.post(BASE, headers=c['h'], json=body).status_code == 201
