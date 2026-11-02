from decimal import Decimal
from datetime import date
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
import pytest
from test_multitenant_integration import actor,empresas,consulta,mercaderia,cliente,catalogo,variantes
from test_cuenta_integration import login
from test_cu16_bloque1_integration import api

@pytest.fixture
def modelo(api,empresas):
    a,b,_,_=empresas;sid,pid,v=mercaderia(a,20);ha=login(api,a,a['codigo'])
    _,_,nombre=cliente(a);h=login(api,a,nombre)
    vids=[v]
    for talla,color in [('S','Negro'),('L','Rojo'),('XL','Blanco'),('XS','Verde')]:
        t=catalogo.crear_talla(talla,None,empresa_id=a['id']);c=catalogo.crear_color(color,None,empresa_id=a['id'])
        vid=variantes.crear_variante(a['id'],pid,t['id'],c['id'],'MAY-'+uuid4().hex)
        variantes.asignar_precio(vid,a['id'],Decimal('50'),date(2020,1,1),None)
        consulta('INSERT INTO inventario_sucursal(empresa_id,sucursal_id,producto_variante_id,stock_disponible) VALUES(%s,%s,%s,20)',(a['id'],sid,vid));vids.append(vid)
    for tipo in ('CUARTA','MEDIA','DOCENA'):
        r=api.put(f'/api/v1/mayorista/productos/{pid}/configuracion',headers=ha,json={'tipo':tipo,'descuento':10,'habilitado':True,'version':0});assert r.status_code==200,r.text
    return a,b,ha,h,sid,pid,vids

def paquete(api,m,tipo='CUARTA',cantidades=None,clave=None):
    a,b,ha,h,sid,pid,vs=m
    cantidades=cantidades or [1,2]
    body={'producto_id':pid,'sucursal_id':sid,'tipo':tipo,'clave_operacion':clave or str(uuid4()),'seleccion':[{'producto_variante_id':vs[i],'cantidad':n} for i,n in enumerate(cantidades) if n]}
    return api.post('/api/v1/mayorista/paquetes',headers=h,json=body),body

def test_unidades_y_paquetes_no_se_fusionan_y_precio_por_porcentaje(api,modelo):
    a,b,ha,h,sid,pid,vs=modelo
    r,_=paquete(api,modelo);assert r.status_code==200,r.text
    r=api.post('/api/v1/carrito/items',headers=h,json={'producto_variante_id':vs[0],'sucursal_id':sid,'cantidad':2});assert r.status_code==200,r.text
    items=r.json()['items'];assert len(items)==3 and Decimal(r.json()['total'])==235
    assert sorted((i['cantidad'],Decimal(i['precio_unitario'])) for i in items)==[(1,Decimal(45)),(2,Decimal(45)),(2,Decimal(50))]
    unit=next(i for i in items if not i['paquete_id']);assert unit['tipo_compra']=='UNIDAD'
    assert api.put(f'/api/v1/carrito/items/{unit["id"]}',headers=h,json={'cantidad':3}).status_code==200

@pytest.mark.parametrize('tipo,cantidades',[('CUARTA',[3]),('CUARTA',[1,1]),('MEDIA',[3,3]),('MEDIA',[1,2,2]),('DOCENA',[6,6]),('DOCENA',[3,3,3,3])])
def test_reglas_de_composicion_sin_excepciones(api,modelo,tipo,cantidades):
    r,_=paquete(api,modelo,tipo,cantidades);assert r.status_code==409,r.text

@pytest.mark.parametrize('tipo,cantidades',[('CUARTA',[1,2]),('MEDIA',[1,2,3]),('DOCENA',[2,2,2,3,3])])
def test_paquetes_validos(api,modelo,tipo,cantidades):
    r,_=paquete(api,modelo,tipo,cantidades);assert r.status_code==200,r.text
    assert sum(i['cantidad'] for i in r.json()['items'])==sum(cantidades)

def test_reintento_y_concurrencia_no_duplican_paquete(api,modelo):
    r,body=paquete(api,modelo);assert r.status_code==200
    def repetir(_):return api.post('/api/v1/mayorista/paquetes',headers=modelo[3],json=body)
    with ThreadPoolExecutor(2) as pool:rs=list(pool.map(repetir,range(2)))
    assert all(r.status_code==200 and len(r.json()['items'])==2 for r in rs)
    body['seleccion'][0]['cantidad']=2
    assert repetir(None).status_code==409

def test_editar_cantidad_rechazado_eliminar_quita_todo_paquete(api,modelo):
    r,_=paquete(api,modelo);item=r.json()['items'][0];h=modelo[3]
    assert api.put(f'/api/v1/carrito/items/{item["id"]}',headers=h,json={'cantidad':2}).status_code==400
    r=api.delete(f'/api/v1/carrito/items/{item["id"]}',headers=h);assert r.status_code==200 and r.json()['items']==[]

def test_stock_combinado_y_sin_variedad_inhabilita(api,modelo):
    a,b,ha,h,sid,pid,vs=modelo
    consulta('UPDATE inventario_sucursal SET stock_disponible=2 WHERE producto_variante_id=%s',(vs[0],))
    assert paquete(api,modelo)[0].status_code==200
    r=api.post('/api/v1/carrito/items',headers=h,json={'producto_variante_id':vs[0],'sucursal_id':sid,'cantidad':2});assert r.status_code==400
    consulta('UPDATE inventario_sucursal SET stock_disponible=0 WHERE empresa_id=%s AND producto_variante_id<>%s',(a['id'],vs[0]))
    opts=api.get(f'/api/v1/mayorista/productos/{pid}?sucursal_id={sid}',headers=h).json();assert not any(p['disponible'] for p in opts['paquetes'])
    assert any(not i['disponible_para_compra'] for i in api.get('/api/v1/carrito',headers=h).json()['items'])

def test_permiso_empresa_version_y_porcentaje_invalido(api,modelo):
    a,b,ha,h,sid,pid,vs=modelo;url=f'/api/v1/mayorista/productos/{pid}/configuracion'
    assert api.put(url,headers=h,json={'tipo':'CUARTA','descuento':10}).status_code==403
    hb=login(api,b,b['codigo']);assert api.get(url,headers=hb).status_code==404
    assert api.put(url,headers=ha,json={'tipo':'CUARTA','descuento':20,'version':0}).status_code==409
    for pct in [0,100,-5,101]:assert api.put(url,headers=ha,json={'tipo':'CUARTA','descuento':pct,'version':1}).status_code==422

def test_pago_mixto_congela_precio_y_retiro_exacto_de_lineas(api,modelo):
    a,b,ha,h,sid,pid,vs=modelo
    assert api.put('/api/v1/pagos-empresa/configuracion',headers=ha,json={'version':0,'qr_habilitado':True}).status_code==200
    assert paquete(api,modelo)[0].status_code==200
    api.post('/api/v1/carrito/items',headers=h,json={'producto_variante_id':vs[0],'sucursal_id':sid,'cantidad':2})
    r=api.post('/api/v1/pagos/qr/checkout',headers=h,json={'clave_operacion':str(uuid4()),'sucursal_id':sid,'total_esperado':'235.00'});assert r.status_code==200,r.text
    oid=r.json()['orden_id']
    api.post('/api/v1/carrito/items',headers=h,json={'producto_variante_id':vs[0],'sucursal_id':sid,'cantidad':1})
    assert paquete(api,modelo)[0].status_code==200
    api.put(f'/api/v1/mayorista/productos/{pid}/configuracion',headers=ha,json={'tipo':'CUARTA','descuento':20,'habilitado':True,'version':1})
    for _ in range(2):
        r=api.post(f'/api/v1/pagos/qr/confirmar/{oid}',headers=h);assert r.status_code==200 and r.json()['estado']=='PAGADO',r.text
    items=api.get('/api/v1/carrito',headers=h).json()['items'];assert sum(i['cantidad'] for i in items)==4
    assert sum(i['cantidad'] for i in items if i['tipo_compra']=='UNIDAD')==1
    assert consulta('SELECT stock_disponible FROM inventario_sucursal WHERE producto_variante_id=%s',(vs[0],),True)['stock_disponible']==17
    assert consulta('SELECT monto_total FROM orden_pago WHERE id=%s',(oid,),True)['monto_total']==235
    detalle=api.get(f'/api/v1/pagos/mis-pagos/{oid}',headers=h).json()['productos']
    assert sum(p['tipo_compra']=='CUARTA' for p in detalle)==2
    assert {Decimal(p['descuento_mayorista']) for p in detalle if p['tipo_compra']=='CUARTA'}=={Decimal(10)}

def test_sin_configuracion_sin_talla_y_sin_colores(api,empresas):
    a,_,_,_=empresas;sid,pid,v=mercaderia(a,20);h=login(api,a,a['codigo']);url=f'/api/v1/mayorista/productos/{pid}?sucursal_id={sid}'
    assert all(not p['disponible'] for p in api.get(url,headers=h).json()['paquetes'])
    api.put(f'/api/v1/mayorista/productos/{pid}/configuracion',headers=h,json={'tipo':'CUARTA','descuento':10,'habilitado':True})
    assert not api.get(url,headers=h).json()['paquetes'][0]['disponible']

def test_colores_y_tallas_faltantes_inhabilitan_sin_excepciones(api,modelo):
    a,b,ha,h,sid,pid,vs=modelo
    color=consulta('SELECT color_id FROM producto_variante WHERE id=%s',(vs[0],),True)['color_id']
    consulta('UPDATE producto_variante SET color_id=%s WHERE producto_id=%s',(color,pid))
    opciones=api.get(f'/api/v1/mayorista/productos/{pid}?sucursal_id={sid}',headers=h).json()['paquetes']
    assert not opciones[0]['disponible'] and not opciones[1]['disponible'] and opciones[2]['disponible']
    assert paquete(api,modelo)[0].status_code==409
    consulta('UPDATE inventario_sucursal SET stock_disponible=0 WHERE producto_variante_id=%s',(vs[4],))
    opciones=api.get(f'/api/v1/mayorista/productos/{pid}?sucursal_id={sid}',headers=h).json()['paquetes']
    assert not opciones[2]['disponible']


def test_porcentajes_independientes_y_sin_acumular_promocion(api,modelo):
    a,b,ha,h,sid,pid,vs=modelo
    promocion=consulta("INSERT INTO promocion(empresa_id,nombre,tipo_descuento,valor,fecha_inicio,fecha_fin) VALUES(%s,'Especial','PORCENTAJE',20,CURRENT_DATE,CURRENT_DATE) RETURNING id",(a['id'],),True)['id']
    consulta('INSERT INTO promocion_producto(empresa_id,promocion_id,producto_id) VALUES(%s,%s,%s)',(a['id'],promocion,pid))
    assert paquete(api,modelo)[0].status_code==200
    r=api.post('/api/v1/carrito/items',headers=h,json={'producto_variante_id':vs[0],'sucursal_id':sid,'cantidad':1});assert r.status_code==200,r.text
    assert {Decimal(i['precio_unitario']) for i in r.json()['items'] if i['paquete_id']}=={Decimal(45)}
    assert {Decimal(i['precio_unitario']) for i in r.json()['items'] if not i['paquete_id']}=={Decimal(40)}
    otro=consulta("INSERT INTO producto(empresa_id,categoria_id,nombre) SELECT empresa_id,categoria_id,'Otro modelo' FROM producto WHERE id=%s RETURNING id",(pid,),True)['id']
    cfg=api.get(f'/api/v1/mayorista/productos/{otro}/configuracion',headers=ha).json();assert all(not c['habilitado'] and c['descuento'] is None for c in cfg)


def test_porcentaje_actualizado_exige_aceptar_total_y_reserva_no_admite_paquete(api,modelo):
    a,b,ha,h,sid,pid,vs=modelo
    assert paquete(api,modelo)[0].status_code==200
    assert api.put('/api/v1/pagos-empresa/configuracion',headers=ha,json={'version':0,'qr_habilitado':True}).status_code==200
    api.put(f'/api/v1/mayorista/productos/{pid}/configuracion',headers=ha,json={'tipo':'CUARTA','descuento':20,'habilitado':True,'version':1})
    r=api.post('/api/v1/pagos/qr/checkout',headers=h,json={'clave_operacion':str(uuid4()),'sucursal_id':sid,'total_esperado':'135.00'});assert r.status_code==409 and 'total cambió' in r.text
    r=api.post('/api/v1/reservas/desde-carrito',headers=h,json={'sucursal_id':sid,'fecha_cita':str(date.today())})
    assert r.status_code==400 and 'paquetes' in r.text.lower(),r.text
