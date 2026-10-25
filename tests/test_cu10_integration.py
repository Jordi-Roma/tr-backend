"""CU10, pruebas reales exclusivamente en PostgreSQL local desechable."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date,timedelta
from contextlib import contextmanager
import pytest
from fastapi.testclient import TestClient
from test_multitenant_integration import actor,empresas,consulta,mercaderia
from test_cuenta_integration import login
from test_cu07_cu08_integration import proveedor,cuenta_proveedor
from app.main import app

@pytest.fixture
def api():
    with TestClient(app) as c:yield c

def admin(api,e):return login(api,e,e['codigo'])

def post(api,h,ruta,datos):
    r=api.post('/api/v1/'+ruta,headers=h,json=datos)
    assert r.status_code==200,r.text
    return r.json()

def catalogo(api,e):
    h=admin(api,e)
    c=post(api,h,'categorias',{'nombre':'Ropa'})['id']
    t=post(api,h,'tallas',{'nombre':'M'})['id']
    co=post(api,h,'colores',{'nombre':'Azul'})['id']
    return h,c,t,co

def promo(pid,valor=10,tipo='PORCENTAJE'):
    return dict(nombre='Oferta',tipo_descuento=tipo,valor=valor,fecha_inicio=str(date.today()),fecha_fin=str(date.today()+timedelta(days=30)),producto_ids=[pid])


def test_registro_completo_atomicidad_historial_sin_stock(api,empresas):
    a,_,_,_=empresas;h,c,t,co=catalogo(api,a)
    datos=dict(categoria_id=c,nombre='Prenda',imagenes=[{'url':'https://example.invalid/a.png'}],variantes=[dict(sku='nuevo',talla_id=t,color_id=co,precio={'monto':'100.00'})])
    p=post(api,h,'productos',datos);pid=p['id'];iid=p['imagenes'][0]['id']
    assert p['imagenes'][0]['es_principal'] is True
    variantes=api.get(f'/api/v1/variantes?producto_id={pid}',headers=h).json()
    assert len(variantes)==1 and variantes[0]['precios'][0]['monto']=='100.00'
    assert consulta('SELECT id FROM inventario_sucursal WHERE empresa_id=%s',(a['id'],))==[]
    for imagenes in ([],datos['imagenes']):
        r=api.put(f'/api/v1/productos/{pid}',headers=h,json={**datos,'imagenes':imagenes})
        assert r.status_code==200,r.text
    assert api.get(f'/api/v1/productos/{pid}',headers=h).json()['imagenes'][0]['id']==iid
    assert len(consulta('SELECT id FROM imagen_producto WHERE producto_id=%s',(pid,)))==1
    assert api.post('/api/v1/productos',headers=h,json={**datos,'nombre':'No guardar','variantes':[{'sku':'otra','talla_id':t,'color_id':co},{'sku':'otra-2','talla_id':t,'color_id':co}]}).status_code==409
    assert len(api.get('/api/v1/productos',headers=h).json())==1


def test_referencias_ajenas_inactivas_y_tipo_talla(api,empresas):
    a,b,_,_=empresas;h,c,t,co=catalogo(api,a);hb,cb,tb,cob=catalogo(api,b)
    for datos in ({'categoria_id':cb},{'categoria_id':c,'marca_id':999999},{'categoria_id':c,'colecciones_ids':[999999]},{'categoria_id':c,'proveedores_ids':[999999]}):
        assert api.post('/api/v1/productos',headers=h,json={'nombre':'Prenda',**datos}).status_code==404
    p=post(api,h,'productos',dict(nombre='Prenda',categoria_id=c))['id']
    assert api.get(f'/api/v1/productos/{p}',headers=hb).status_code==404
    assert api.put(f'/api/v1/productos/{p}',headers=hb,json=dict(nombre='Ajeno',categoria_id=cb)).status_code==404
    for talla,color in ((tb,co),(t,cob)):
        assert api.post('/api/v1/variantes',headers=h,json=dict(producto_id=p,sku='ajeno',talla_id=talla,color_id=color)).status_code==404
    tinf=post(api,h,'tallas',{'nombre':'30','tipo_prenda':'INFERIOR'})['id']
    assert api.post('/api/v1/variantes',headers=h,json=dict(producto_id=p,sku='incompatible',talla_id=tinf,color_id=co)).status_code==409
    post(api,h,'variantes',dict(producto_id=p,sku='compatible',talla_id=t,color_id=co))
    assert api.put(f'/api/v1/productos/{p}',headers=h,json=dict(nombre='Prenda',categoria_id=c,tipo_prenda='INFERIOR')).status_code==409
    assert api.patch(f'/api/v1/colores/{co}/desactivar',headers=h).status_code==409


def test_duplicados_concurrentes_incluyendo_null_y_sku(api,empresas):
    a,b,_,_=empresas;ha,ca,_,_=catalogo(api,a);hb,cb,_,_=catalogo(api,b)
    pa=post(api,ha,'productos',dict(nombre='A',categoria_id=ca))['id']
    pb=post(api,hb,'productos',dict(nombre='B',categoria_id=cb))['id']
    def crear(sku):return api.post('/api/v1/variantes',headers=ha,json=dict(producto_id=pa,sku=sku)).status_code
    with ThreadPoolExecutor(2) as pool:assert sorted(pool.map(crear,['SKU','OTRO']))==[200,409]
    post(api,hb,'variantes',dict(producto_id=pb,sku='SKU'))
    v=api.get(f'/api/v1/variantes?producto_id={pa}',headers=ha).json()[0]
    assert api.patch(f'/api/v1/variantes/{v["id"]}/desactivar',headers=ha).status_code==200
    assert crear('TERCERO')==409


def test_reservas_impiden_desactivar_y_reactivacion_respeta_padres(api,empresas):
    a,_,_,_=empresas;h=admin(api,a);_,pid,vid=mercaderia(a)
    consulta('UPDATE inventario_sucursal SET stock_reservado=1 WHERE producto_variante_id=%s',(vid,))
    for ruta,rid in (('productos',pid),('variantes',vid)):
        assert api.patch(f'/api/v1/{ruta}/{rid}/desactivar',headers=h).status_code==409
    consulta('UPDATE inventario_sucursal SET stock_reservado=0 WHERE producto_variante_id=%s',(vid,))
    assert api.patch(f'/api/v1/productos/{pid}/desactivar',headers=h).status_code==200
    assert api.patch(f'/api/v1/variantes/{vid}/activar',headers=h).status_code==409
    assert api.patch(f'/api/v1/productos/{pid}/activar',headers=h).status_code==200
    assert api.get(f'/api/v1/variantes/{vid}',headers=h).json()['activo'] is False
    assert api.patch(f'/api/v1/variantes/{vid}/activar',headers=h).status_code==200
    assert consulta('SELECT stock_disponible FROM inventario_sucursal WHERE producto_variante_id=%s',(vid,),True)['stock_disponible']==4


def test_precio_futuro_no_borra_precio_actual_y_rangos_invalidos(api,empresas):
    a,_,_,_=empresas;h=admin(api,a);_,_,vid=mercaderia(a);futura=date.today()+timedelta(days=10)
    assert api.post(f'/api/v1/variantes/{vid}/precios',headers=h,json=dict(monto=75,fecha_inicio=str(futura))).status_code==200
    precios=consulta('SELECT precio,fecha_inicio,fecha_fin FROM precio_producto WHERE producto_variante_id=%s AND activo ORDER BY fecha_inicio',(vid,))
    assert [int(p['precio']) for p in precios]==[50,75] and precios[0]['fecha_fin']==futura-timedelta(days=1)
    assert api.post(f'/api/v1/variantes/{vid}/precios',headers=h,json=dict(monto=30,fecha_fin=str(date.today()-timedelta(days=1)))).status_code==422
    assert len(consulta('SELECT id FROM precio_producto WHERE producto_variante_id=%s',(vid,)))==2


def test_promociones_importes_fechas_alcance_e_historial(api,empresas):
    a,b,_,_=empresas;h=admin(api,a);hb=admin(api,b);sid,pid,vid=mercaderia(a);sb,pb,_=mercaderia(b)
    assert api.post('/api/v1/promociones',headers=h,json=promo(pid,60,'MONTO_FIJO')).status_code==409
    pr=post(api,h,'promociones',{**promo(pid,40,'MONTO_FIJO'),'sucursal_ids':[sid]});rid=pr['id']
    assert api.post(f'/api/v1/variantes/{vid}/precios',headers=h,json={'monto':30}).status_code==409
    assert api.get(f'/api/v1/promociones/{rid}',headers=hb).status_code==404
    for datos in ({**promo(pb)}, {**promo(pid),'sucursal_ids':[sb]}):
        assert api.put(f'/api/v1/promociones/{rid}',headers=h,json=datos).status_code==404
    assert api.put(f'/api/v1/promociones/{rid}',headers=h,json={**promo(pid,20,'MONTO_FIJO'),'sucursal_ids':[]}).status_code==200
    assert consulta('SELECT activo FROM promocion_sucursal WHERE promocion_id=%s',(rid,),True)['activo'] is False
    assert api.patch(f'/api/v1/promociones/{rid}/desactivar',headers=h).status_code==200
    assert api.patch(f'/api/v1/promociones/{rid}/activar',headers=h).status_code==200
    consulta('UPDATE promocion SET fecha_inicio=%s,fecha_fin=%s WHERE id=%s',(date.today()-timedelta(days=3),date.today()-timedelta(days=1),rid))
    assert api.patch(f'/api/v1/promociones/{rid}/activar',headers=h).status_code==409


def test_vinculos_retirados_no_aparecen_pero_se_conservan(api,empresas):
    a,_,_,_=empresas;h,c,_,_=catalogo(api,a)
    temporada=post(api,h,'temporadas',{'nombre':'Verano','anio':2026})['id']
    col=post(api,h,'colecciones',{'nombre':'Línea','temporada_id':temporada})['id'];prov=proveedor(api,h)
    datos=dict(nombre='Prenda',categoria_id=c,colecciones_ids=[col],proveedores_ids=[prov])
    p=post(api,h,'productos',datos)['id']
    assert api.put(f'/api/v1/productos/{p}',headers=h,json={**datos,'colecciones_ids':[],'proveedores_ids':[]}).status_code==200
    r=api.get(f'/api/v1/productos/{p}',headers=h).json();assert r['colecciones_ids']==[] and r['proveedores_ids']==[]
    for tabla in ('producto_coleccion','producto_proveedor'):
        assert consulta(f'SELECT activo FROM {tabla} WHERE producto_id=%s',(p,),True)['activo'] is False
    assert api.patch(f'/api/v1/colecciones/{col}/desactivar',headers=h).status_code==200


def test_proveedor_consulta_y_no_escribe_catalogo(api,empresas):
    a,b,_,_=empresas;h=admin(api,a);_,pid,vid=mercaderia(a);_,otro,_=mercaderia(b)
    prov=proveedor(api,h);_,usuario=cuenta_proveedor(api,h,prov)
    assert api.post(f'/api/v1/proveedores/{prov}/productos',headers=h,json={'producto_id':pid}).status_code==200
    hp=login(api,a,usuario)
    lista=api.get('/api/v1/proveedor-panel/productos',headers=hp)
    assert lista.status_code==200 and {p['producto_id'] for p in lista.json()}=={pid},lista.text
    for ruta in ('productos','variantes','promociones'):
        assert api.get('/api/v1/'+ruta,headers=hp).status_code==403
        assert api.post('/api/v1/'+ruta,headers=hp,json={}).status_code==403
    assert api.post(f'/api/v1/variantes/{vid}/precios',headers=hp,json={'monto':10}).status_code==403
    assert api.patch(f'/api/v1/productos/{otro}/desactivar',headers=hp).status_code==403


def test_rollback_catalogo_y_auditoria(api,empresas,monkeypatch):
    from app.modules.administracion.repositories import catalogo_comercial_repository as repo
    a,_,_,_=empresas;h,c,_,_=catalogo(api,a);original=repo._transaccion
    @contextmanager
    def fallo():
        with original() as cur:
            yield cur
            raise RuntimeError('Fallo antes del commit')
    monkeypatch.setattr(repo,'_transaccion',fallo)
    with pytest.raises(RuntimeError):api.post('/api/v1/productos',headers=h,json={'nombre':'No guardar','categoria_id':c})
    assert consulta('SELECT id FROM producto WHERE empresa_id=%s',(a['id'],))==[]
    assert consulta("SELECT id FROM bitacora WHERE empresa_id=%s AND modulo='PRODUCTOS'",(a['id'],))==[]


@pytest.mark.parametrize('ruta,datos',[
    ('productos',{'nombre':'X','categoria_id':1,'ancho_base_cm':-1}),
    ('productos',{'nombre':'X','categoria_id':1,'tipo_prenda':'OTRO'}),
    ('productos',{'nombre':'X'*181,'categoria_id':1}),
    ('productos',{'nombre':'X','categoria_id':1,'imagenes':[{'url':'javascript:alert(1)'}]}),
    ('productos',{'nombre':'X','categoria_id':1,'imagenes':[{'url':'https://x.invalid/a','es_principal':True},{'url':'https://x.invalid/b','es_principal':True}]}),
    ('variantes',{'producto_id':1,'sku':'  '}),
    ('variantes',{'producto_id':1,'sku':'x','ancho_cm':0}),
    ('promociones',{**promo(1),'valor':101}),
    ('promociones',{**promo(1),'fecha_fin':'2000-01-01'}),
])
def test_validacion_sin_escritura(api,empresas,ruta,datos):
    a,_,_,_=empresas
    assert api.post('/api/v1/'+ruta,headers=admin(api,a),json=datos).status_code==422

def test_cupo_producto_concurrente_en_api(api,empresas):
    a,_,plan,_=empresas;h,c,_,_=catalogo(api,a)
    consulta("UPDATE plan SET limites=jsonb_set(limites,'{productos}','1'::jsonb) WHERE id=%s",(plan['id'],))
    def crear(nombre):return api.post('/api/v1/productos',headers=h,json={'nombre':nombre,'categoria_id':c}).status_code
    with ThreadPoolExecutor(2) as pool:assert sorted(pool.map(crear,['Una','Otra']))==[200,409]
    consulta("UPDATE empresa SET estado='SUSPENDIDA' WHERE id=%s",(a['id'],))
    assert crear('Suspendida')==403


def test_precio_temporal_restablece_tramo_posterior(api,empresas):
    a,_,_,_=empresas;h=admin(api,a);_,_,vid=mercaderia(a)
    inicio=date.today()+timedelta(days=5);fin=inicio+timedelta(days=3)
    assert api.post(f'/api/v1/variantes/{vid}/precios',headers=h,json={'monto':70,'fecha_inicio':str(inicio),'fecha_fin':str(fin)}).status_code==200
    precios=consulta('SELECT precio,fecha_inicio,fecha_fin FROM precio_producto WHERE producto_variante_id=%s AND activo ORDER BY fecha_inicio',(vid,))
    assert [int(p['precio']) for p in precios]==[50,70,50]
    assert precios[0]['fecha_fin']==inicio-timedelta(days=1)
    assert precios[2]['fecha_inicio']==fin+timedelta(days=1) and precios[2]['fecha_fin'] is None


def test_promocion_ignora_vinculos_retirados_en_catalogo_y_carrito(api,empresas):
    from app.modules.catalogo.repositories.catalogo_publico_repository import _obtener_promocion
    from app.modules.autenticacion.repositories.perfil_repository import _transaccion
    a,_,_,_=empresas;h=admin(api,a);sid,pid,_=mercaderia(a)
    r=post(api,h,'promociones',{**promo(pid),'sucursal_ids':[sid]});rid=r['id']
    with _transaccion() as cur:assert _obtener_promocion(cur,pid,a['id'],None) is None
    assert api.put(f'/api/v1/promociones/{rid}',headers=h,json=promo(pid)).status_code==200
    with _transaccion() as cur:assert _obtener_promocion(cur,pid,a['id'],None)['valor']==10
    cid=consulta('SELECT categoria_id FROM producto WHERE id=%s',(pid,),True)['categoria_id']
    otro=post(api,h,'productos',{'nombre':'Otra','categoria_id':cid})['id']
    assert api.put(f'/api/v1/promociones/{rid}',headers=h,json=promo(otro)).status_code==200
    with _transaccion() as cur:assert _obtener_promocion(cur,pid,a['id'],sid) is None
    assert consulta('SELECT activo FROM promocion_producto WHERE promocion_id=%s AND producto_id=%s',(rid,pid),True)['activo'] is False


def test_reserva_rechaza_variante_desactivada_sin_alterar_stock(api,empresas):
    from app.modules.reservas.repositories.reserva_repository import _validar_y_reservar_stock_cursor
    from app.modules.autenticacion.repositories.perfil_repository import _transaccion
    a,_,_,_=empresas;h=admin(api,a);sid,_,vid=mercaderia(a)
    assert api.patch(f'/api/v1/variantes/{vid}/desactivar',headers=h).status_code==200
    with pytest.raises(ValueError,match='variante'):
        with _transaccion() as cur:_validar_y_reservar_stock_cursor(cur,vid,sid,1,a['id'])
    assert consulta('SELECT stock_reservado FROM inventario_sucursal WHERE producto_variante_id=%s',(vid,),True)['stock_reservado']==0
