"""CU09: catálogo real sobre PostgreSQL local desechable."""
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from test_multitenant_integration import actor, empresas, consulta, cliente, mercaderia
from test_cuenta_integration import login
from app.main import app


@pytest.fixture
def api():
    with TestClient(app) as c:
        yield c


def admin(api, empresa):
    return login(api, empresa, empresa['codigo'])


def crear(api, h, ruta, datos):
    r = api.post('/api/v1/'+ruta, headers=h, json=datos)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize('ruta,datos', [
    ('categorias', {'nombre':'Clasificación'}),
    ('tallas', {'nombre':'Especial','tipo_prenda':'INFERIOR','ancho_cm':25.5}),
    ('colores', {'nombre':'Esmeralda','codigo_hex':'#008844'}),
    ('marcas', {'nombre':'Marca'}),
    ('temporadas', {'nombre':'Verano','anio':2026}),
    ('colecciones', {'nombre':'Colección'}),
])
def test_crud_aislamiento_historico_auditoria(api, empresas, ruta, datos):
    a,b,_,_=empresas
    ha,hb=admin(api,a),admin(api,b)
    cuerpos=[dict(datos),dict(datos)]
    if ruta=='colecciones':
        for h,c in zip((ha,hb),cuerpos):
            c['temporada_id']=crear(api,h,'temporadas',{'nombre':'Verano','anio':2026})['id']
    x=crear(api,ha,ruta,cuerpos[0]); y=crear(api,hb,ruta,cuerpos[1])
    assert api.get(f'/api/v1/{ruta}/{y["id"]}',headers=ha).status_code==404
    assert api.put(f'/api/v1/{ruta}/{y["id"]}',headers=ha,json=cuerpos[0]).status_code==404
    assert api.patch(f'/api/v1/{ruta}/{y["id"]}/desactivar',headers=ha).status_code==404
    assert {r['id'] for r in api.get('/api/v1/'+ruta,headers=ha).json()}=={x['id']}
    cambio={**cuerpos[0],'nombre':'Editada'}
    assert api.put(f'/api/v1/{ruta}/{x["id"]}',headers=ha,json=cambio).status_code==200
    assert api.patch(f'/api/v1/{ruta}/{x["id"]}/desactivar',headers=ha).status_code==200
    assert api.get(f'/api/v1/{ruta}/{x["id"]}',headers=ha).json()['activo'] is False
    assert api.post('/api/v1/'+ruta,headers=ha,json={**cambio,'nombre':' editada '}).status_code==409
    assert api.patch(f'/api/v1/{ruta}/{x["id"]}/activar',headers=ha).status_code==200
    assert consulta("SELECT count(*) n FROM bitacora WHERE empresa_id=%s AND modulo='CATALOGO'",(a['id'],),True)['n']>=4
    _,_,usuario=cliente(a)
    hc=login(api,a,usuario)
    assert api.get('/api/v1/'+ruta,headers=hc).status_code==403
    assert api.post('/api/v1/'+ruta,headers=hc,json=cambio).status_code==403


def test_jerarquia_no_ciclos_padres_ajenos_o_inactivos(api,empresas):
    a,b,_,_=empresas;ha,hb=admin(api,a),admin(api,b)
    raiz=crear(api,ha,'categorias',{'nombre':'Raíz'})['id']
    hijo=crear(api,ha,'categorias',{'nombre':'Hijo','categoria_padre_id':raiz})['id']
    ajena=crear(api,hb,'categorias',{'nombre':'Otra'})['id']
    for padre in (raiz,hijo,ajena):
        r=api.put(f'/api/v1/categorias/{raiz}',headers=ha,json={'nombre':'Raíz','categoria_padre_id':padre})
        assert r.status_code==409,r.text
    assert api.patch(f'/api/v1/categorias/{raiz}/desactivar',headers=ha).status_code==409
    assert api.patch(f'/api/v1/categorias/{hijo}/desactivar',headers=ha).status_code==200
    assert api.patch(f'/api/v1/categorias/{raiz}/desactivar',headers=ha).status_code==200
    assert api.patch(f'/api/v1/categorias/{hijo}/activar',headers=ha).status_code==409
    assert api.post('/api/v1/categorias',headers=ha,json={'nombre':'Nuevo','categoria_padre_id':raiz}).status_code==409


def test_temporadas_colecciones_productos_preservan_vinculos(api,empresas):
    a,b,_,_=empresas;h=admin(api,a)
    _,producto,_=mercaderia(a)
    temporada=crear(api,h,'temporadas',{'nombre':'Verano','anio':2026})['id']
    coleccion=crear(api,h,'colecciones',{'nombre':'Línea','temporada_id':temporada})['id']
    assert api.patch(f'/api/v1/temporadas/{temporada}/desactivar',headers=h).status_code==409
    consulta('INSERT INTO producto_coleccion(producto_id,coleccion_id,empresa_id) VALUES(%s,%s,%s)',(producto,coleccion,a['id']))
    assert api.patch(f'/api/v1/colecciones/{coleccion}/desactivar',headers=h).status_code==409
    consulta('UPDATE producto SET activo=FALSE WHERE id=%s',(producto,))
    assert api.patch(f'/api/v1/colecciones/{coleccion}/desactivar',headers=h).status_code==200
    assert api.patch(f'/api/v1/temporadas/{temporada}/desactivar',headers=h).status_code==200
    assert api.patch(f'/api/v1/colecciones/{coleccion}/activar',headers=h).status_code==409
    assert consulta('SELECT 1 FROM producto_coleccion WHERE producto_id=%s AND coleccion_id=%s',(producto,coleccion),True)
    assert api.patch(f'/api/v1/temporadas/{temporada}/activar',headers=h).status_code==200
    assert api.patch(f'/api/v1/colecciones/{coleccion}/activar',headers=h).status_code==200
    ajena=crear(api,admin(api,b),'temporadas',{'nombre':'Ajena','anio':2026})['id']
    assert api.put(f'/api/v1/colecciones/{coleccion}',headers=h,json={'nombre':'Línea','temporada_id':ajena}).status_code==409


def test_dependencias_variantes_categoria_marca(api,empresas):
    a,_,_,_=empresas;h=admin(api,a);_,producto,variante=mercaderia(a)
    marca=crear(api,h,'marcas',{'nombre':'Origen'})['id']
    consulta('UPDATE producto SET marca_id=%s WHERE id=%s',(marca,producto))
    p=consulta('SELECT categoria_id FROM producto WHERE id=%s',(producto,),True)
    v=consulta('SELECT talla_id,color_id FROM producto_variante WHERE id=%s',(variante,),True)
    for ruta,rid in [('categorias',p['categoria_id']),('marcas',marca),('tallas',v['talla_id']),('colores',v['color_id'])]:
        assert api.patch(f'/api/v1/{ruta}/{rid}/desactivar',headers=h).status_code==409


@pytest.mark.parametrize('ruta,datos',[
    ('tallas',{'nombre':'X','tipo_prenda':'OTRO'}),
    ('tallas',{'nombre':'X','ancho_cm':0}),
    ('tallas',{'nombre':'X','ancho_cm':0.001}),
    ('tallas',{'nombre':'X','largo_cm':-1}),
    ('tallas',{'nombre':'X','ancho_cm':10000}),
    ('categorias',{'nombre':'X'*121}),
    ('colores',{'nombre':'X','codigo_hex':'rojo'}),
    ('temporadas',{'nombre':'X','anio':1999}),
    ('marcas',{'nombre':'  '}),
])
def test_validacion_sin_cambios(api,empresas,ruta,datos):
    a,_,_,_=empresas;h=admin(api,a)
    assert api.post('/api/v1/'+ruta,headers=h,json=datos).status_code==422
    assert api.get('/api/v1/'+ruta,headers=h).json()==[]


def test_duplicados_concurrentes_y_plan(api,empresas):
    a,_,_,_=empresas;h=admin(api,a)
    temporada=crear(api,h,'temporadas',{'nombre':'Verano','anio':2026})['id']
    def insertar(nombre):
        return api.post('/api/v1/colecciones',headers=h,json={'nombre':nombre,'temporada_id':temporada}).status_code
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(insertar,['Única',' única ']))==[200,409]
    consulta("UPDATE empresa SET estado='SUSPENDIDA' WHERE id=%s",(a['id'],))
    assert api.post('/api/v1/marcas',headers=h,json={'nombre':'Bloqueada'}).status_code in (403,409)


def test_transaccion_revierte_datos_y_auditoria(api,empresas,monkeypatch):
    from contextlib import contextmanager
    from app.modules.administracion.repositories import clasificacion_repository as repo
    a,_,_,_=empresas;h=admin(api,a)
    original=repo._transaccion
    @contextmanager
    def interrumpida():
        with original() as cur:
            yield cur
            raise RuntimeError('Fallo antes del commit')
    monkeypatch.setattr(repo,'_transaccion',interrumpida)
    with pytest.raises(RuntimeError,match='antes del commit'):
        api.post('/api/v1/marcas',headers=h,json={'nombre':'Sin guardar'})
    assert consulta('SELECT id FROM marca WHERE empresa_id=%s',(a['id'],))==[]
    assert consulta("SELECT id FROM bitacora WHERE empresa_id=%s AND modulo='CATALOGO'",(a['id'],))==[]


def test_identidad_talla_tipo_y_temporada_anio(api,empresas):
    a,_,_,_=empresas;h=admin(api,a)
    for tipo in ('SUPERIOR','INFERIOR','VESTIDO'):
        crear(api,h,'tallas',{'nombre':'M','tipo_prenda':tipo})
    for anio in (2026,2027):
        crear(api,h,'temporadas',{'nombre':'Verano','anio':anio})
    assert api.post('/api/v1/tallas',headers=h,json={'nombre':'m','tipo_prenda':'SUPERIOR'}).status_code==409


def test_jerarquia_concurrente_no_crea_ciclo(api,empresas):
    a,_,_,_=empresas;h=admin(api,a)
    x=crear(api,h,'categorias',{'nombre':'A'})['id']
    y=crear(api,h,'categorias',{'nombre':'B'})['id']
    def vincular(par):
        rid,padre,nombre=par
        return api.put(f'/api/v1/categorias/{rid}',headers=h,json={'nombre':nombre,'categoria_padre_id':padre}).status_code
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(vincular,[(x,y,'A'),(y,x,'B')]))==[200,409]
