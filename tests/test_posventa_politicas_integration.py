from uuid import uuid4
from decimal import Decimal
import pytest
from test_multitenant_integration import actor,empresas,consulta
from test_cu16_bloque1_integration import api,preparar,checkout
from test_cuenta_integration import login

@pytest.fixture
def compra(api,empresas):
 a,b,_,_=empresas;ha,h,sid,vid,uid=preparar(api,a,10)
 o,_=checkout(api,h,sid);assert api.post(f'/api/v1/pagos/qr/confirmar/{o["orden_id"]}',headers=h).status_code==200
 p={'devoluciones_habilitadas':True,'plazo_devoluciones':15,'condiciones_devoluciones':'Con revisión de estado de las prendas','version':0}
 r=api.put('/api/v1/posventa/politica',headers=ha,json=p);assert r.status_code==200,r.text
 vd=consulta('SELECT id FROM venta_detalle WHERE venta_id=%s',(o['venta_id'],),True)['id']
 return a,b,ha,h,sid,vid,o,vd

def solicitar(api,c,clave=None):
 body={'clave_operacion':clave or str(uuid4()),'motivo':'La prenda no se adapta','items':[{'venta_detalle_id':c[7],'cantidad':1}]}
 r=api.post(f'/api/v1/devoluciones/ventas/{c[6]["venta_id"]}',headers=c[3],json=body);assert r.status_code==201,r.text
 return r.json(),body

def inspeccionar(api,c,no_vendible=0):
 d,body=solicitar(api,c);did=d['id']
 r=api.patch(f'/api/v1/devoluciones/{did}/revision',headers=c[2],json={'aprobar':True});assert r.status_code==200,r.text
 r=api.patch(f'/api/v1/devoluciones/{did}/recepcion',headers=c[2],json={'items':[{'detalle_id':d['detalles'][0]['id'],'cantidad_aceptada':1,'cantidad_no_vendible':no_vendible,'observacion':'Costura dañada'}]});assert r.status_code==200,r.text
 return r.json()

@pytest.mark.parametrize('no_vendible',[0,1])
def test_inspeccion_aceptacion_stock_y_reembolso_original(api,compra,no_vendible):
 c=compra;d=inspeccionar(api,c,no_vendible);assert d['estado']=='ESPERA_ACEPTACION'
 stock=lambda:consulta('SELECT stock_disponible FROM inventario_sucursal WHERE producto_variante_id=%s',(c[5],),True)['stock_disponible']
 assert stock()==9
 assert api.post(f'/api/v1/devoluciones/{d["id"]}/reembolso',headers=c[2],json={}).status_code==409
 url=f'/api/v1/posventa/devoluciones/{d["id"]}/aceptar'
 assert api.post(url,headers=c[3],json={'monto':49}).status_code==409
 for _ in range(2):
  r=api.post(url,headers=c[3],json={'monto':50});assert r.status_code==200 and r.json()['comprobante'],r.text
 assert stock()==10-no_vendible
 for _ in range(2):
  r=api.post(f'/api/v1/devoluciones/{d["id"]}/reembolso',headers=c[2],json={});assert r.status_code==200 and r.json()['estado']=='REEMBOLSADA',r.text
 assert stock()==10-no_vendible
 assert r.json()['metodo_reembolso']=='QR'

def test_politica_independiente_version_permiso_y_plazo(api,compra):
 c=compra;ha,h=c[2:4];hb=login(api,c[1],c[1]['codigo'])
 assert not api.get('/api/v1/posventa/politica',headers=hb).json()['devoluciones_habilitadas']
 assert api.put('/api/v1/posventa/politica',headers=h,json={}).status_code==403
 assert api.put('/api/v1/posventa/politica',headers=ha,json={'version':0}).status_code==409
 assert api.put('/api/v1/posventa/politica',headers=ha,json={'version':1,'devoluciones_habilitadas':True}).status_code==422
 consulta("UPDATE venta SET fecha_venta=CURRENT_TIMESTAMP-INTERVAL '16 days' WHERE id=%s",(c[6]['venta_id'],))
 r=api.post(f'/api/v1/devoluciones/ventas/{c[6]["venta_id"]}',headers=h,json={'clave_operacion':str(uuid4()),'motivo':'Prenda de otra temporada','items':[{'venta_detalle_id':c[7],'cantidad':1}]});assert r.status_code==400

def test_clave_duplicada_no_duplica_y_otra_cuenta_no_acepta(api,compra):
 c=compra;d,body=solicitar(api,c)
 r=api.post(f'/api/v1/devoluciones/ventas/{c[6]["venta_id"]}',headers=c[3],json=body);assert r.status_code==201 and r.json()['id']==d['id']
 hb=login(api,c[1],c[1]['codigo']);assert api.post(f'/api/v1/posventa/devoluciones/{d["id"]}/aceptar',headers=hb,json={'monto':50}).status_code==404
 assert len(consulta('SELECT id FROM devolucion WHERE empresa_id=%s',(c[0]['id'],)))==1

def test_espera_aceptacion_impide_devolver_dos_veces_la_misma_unidad(api,compra):
 c=compra;d=inspeccionar(api,c)
 assert d['estado']=='ESPERA_ACEPTACION'
 assert api.get('/api/v1/devoluciones/ventas-elegibles',headers=c[3]).json()==[]
 r=api.post(f'/api/v1/devoluciones/ventas/{c[6]["venta_id"]}',headers=c[3],json={'clave_operacion':str(uuid4()),'motivo':'Segundo intento de devolución','items':[{'venta_detalle_id':c[7],'cantidad':1}]})
 assert r.status_code==400

def test_cajero_gestiona_su_sucursal_y_no_otra(api,compra):
 from test_multitenant_integration import crear_usuario_con_rol,hashear_password
 c=compra;d,_=solicitar(api,c);a=c[0]
 nombre='staff'+uuid4().hex[:9];rid=consulta("SELECT id FROM rol WHERE nombre='CAJERO'",(),True)['id']
 u=crear_usuario_con_rol('Personal','Prueba',nombre,nombre+'@example.invalid',hashear_password('Prueba-aislada-123'),rid,'CAJERO',None,a['admin_usuario_id'],a['id'])
 consulta("INSERT INTO empleado(usuario_id,sucursal_id,codigo_empleado,cargo,empresa_id) VALUES(%s,%s,%s,'Prueba',%s)",(u['id'],c[4],nombre,a['id']))
 h=login(api,a,nombre)
 assert api.patch(f'/api/v1/devoluciones/{d["id"]}/revision',headers=h,json={'aprobar':True}).status_code==200
 ciudad=consulta('SELECT ciudad_id FROM sucursal WHERE id=%s',(c[4],),True)['ciudad_id']
 otro=consulta("INSERT INTO sucursal(empresa_id,ciudad_id,nombre,direccion) VALUES(%s,%s,'Otra','Lejos') RETURNING id",(a['id'],ciudad),True)['id']
 consulta('UPDATE empleado SET sucursal_id=%s WHERE usuario_id=%s',(otro,u['id']))
 h=login(api,a,nombre)
 r=api.patch(f'/api/v1/devoluciones/{d["id"]}/recepcion',headers=h,json={'items':[{'detalle_id':d['detalles'][0]['id'],'cantidad_aceptada':1}]})
 assert r.status_code==404,r.text

def test_efectivo_requiere_aceptacion_y_recibo_y_no_se_repite(api,compra):
 c=compra
 from test_cu11_cu15_integration import venta
 c=list(c)
 cid=consulta('SELECT cliente_id FROM venta WHERE id=%s',(c[6]['venta_id'],),True)['cliente_id']
 r=venta(api,c[2],c[4],c[5],cliente_id=cid);assert r.status_code==200,r.text
 c[6]={'venta_id':r.json()['id']}
 c[7]=consulta('SELECT id FROM venta_detalle WHERE venta_id=%s',(c[6]['venta_id'],),True)['id']
 d=inspeccionar(api,c);url=f'/api/v1/devoluciones/{d["id"]}/reembolso/manual';body={'metodo':'EFECTIVO','referencia':'RECIBO-CAJA-123'}
 assert api.post(url,headers=c[2],json=body).status_code==409
 assert api.post(f'/api/v1/posventa/devoluciones/{d["id"]}/aceptar',headers=c[3],json={'monto':50}).status_code==200
 r=api.post(url,headers=c[2],json=body);assert r.status_code==200 and r.json()['estado']=='REEMBOLSADA',r.text
 assert api.post(url,headers=c[2],json=body).status_code==409

def test_reembolso_manual_no_convierte_qr_en_efectivo(api,compra):
 c=compra;d=inspeccionar(api,c)
 api.post(f'/api/v1/posventa/devoluciones/{d["id"]}/aceptar',headers=c[3],json={'monto':50})
 r=api.post(f'/api/v1/devoluciones/{d["id"]}/reembolso/manual',headers=c[2],json={'metodo':'EFECTIVO','referencia':'CAJA-123'});assert r.status_code==409,r.text

def test_politica_guardada_no_cambia_solicitud_en_curso_y_no_excede_cantidades(api,compra):
 c=compra;d,_=solicitar(api,c)
 assert api.put('/api/v1/posventa/politica',headers=c[2],json={'version':1}).status_code==200
 assert api.get('/api/v1/devoluciones/ventas-elegibles',headers=c[3]).json()==[]
 r=api.patch(f'/api/v1/devoluciones/{d["id"]}/revision',headers=c[2],json={'aprobar':True});assert r.status_code==200
 r=api.patch(f'/api/v1/devoluciones/{d["id"]}/recepcion',headers=c[2],json={'items':[{'detalle_id':d['detalles'][0]['id'],'cantidad_aceptada':1}]});assert r.status_code==200 and r.json()['politica_snapshot']['version']==1
 assert api.post(f'/api/v1/posventa/devoluciones/{d["id"]}/aceptar',headers=c[3],json={'monto':50}).status_code==200

def test_descuento_general_se_reparte_sin_superar_pago_y_sin_reembolsar_envio(api,compra):
 c=compra
 consulta('UPDATE venta SET descuento=10,total=40 WHERE id=%s',(c[6]['venta_id'],))
 consulta('UPDATE orden_pago SET monto_total=40 WHERE id=%s',(c[6]['orden_id'],))
 d=inspeccionar(api,c)
 assert Decimal(d['monto_aprobado'])==40
 assert api.post(f'/api/v1/posventa/devoluciones/{d["id"]}/aceptar',headers=c[3],json={'monto':40}).status_code==200

def test_firma_stripe_conciliacion_valida_referencia_importe_y_moneda(api,compra):
 from app.modules.ventas_inventario.services.posventa_service import conciliar
 from fastapi import HTTPException
 c=compra;d=inspeccionar(api,c);api.post(f'/api/v1/posventa/devoluciones/{d["id"]}/aceptar',headers=c[3],json={'monto':50})
 consulta("UPDATE orden_pago SET proveedor='STRIPE',proveedor_pago_id='pi_prueba' WHERE id=%s",(c[6]['orden_id'],))
 obj={'id':'re_'+uuid4().hex,'amount':5000,'currency':'bob','payment_intent':'pi_prueba','status':'succeeded','livemode':False,'metadata':{'empresa_id':str(c[0]['id']),'devolucion_id':str(d['id'])}}
 for campo,valor in [('amount',5001),('currency','usd'),('payment_intent','pi_ajeno'),('livemode',True)]:
  with pytest.raises(HTTPException):conciliar(c[0]['id'],{**obj,campo:valor})
 assert conciliar(c[0]['id'],obj)['estado']=='RECIBIDO'
 assert conciliar(c[0]['id'],obj)['estado']=='RECIBIDO'
 assert api.get(f'/api/v1/devoluciones/mis-devoluciones/{d["id"]}',headers=c[3]).json()['estado']=='REEMBOLSADA'
