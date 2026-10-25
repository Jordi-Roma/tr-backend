"""CU07/CU08, PostgreSQL local explícito y desechable."""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from test_multitenant_integration import actor, empresas, cliente, consulta, mercaderia
from test_cuenta_integration import login
from app.main import app


@pytest.fixture
def api():
    with TestClient(app) as c:
        yield c


def admin(api, empresa):
    return login(api, empresa, empresa['codigo'])


def datos_empleado(sucursal, nombre=None, rol='CAJERO'):
    nombre = nombre or 'cu07'+uuid4().hex[:12]
    return dict(nombre='Empleado',apellido='Prueba',username=nombre,correo=nombre+'@example.invalid',
                password='Prueba-aislada-123',sucursal_id=sucursal,codigo_empleado='E'+nombre,cargo='Ventas',rol=rol)


def nuevo_empleado(api, h, sucursal, rol='CAJERO'):
    datos=datos_empleado(sucursal,rol=rol)
    r=api.post('/api/v1/empleados/crear-usuario',headers=h,json=datos)
    assert r.status_code==200,r.text
    return r.json(),datos


def proveedor(api,h,nit='123456'):
    r=api.post('/api/v1/proveedores',headers=h,json={'nombre':'Proveedor prueba','nit':nit})
    assert r.status_code==200,r.text
    return r.json()['id']


def cuenta_proveedor(api,h,pid):
    nombre='cu08'+uuid4().hex[:12]
    datos=dict(nombre='Proveedor',apellido='Prueba',username=nombre,correo=nombre+'@example.invalid',password='Prueba-aislada-123')
    r=api.post(f'/api/v1/proveedores/{pid}/crear-usuario',headers=h,json=datos)
    assert r.status_code==200,r.text
    return r.json()['usuarios_ids'][0],nombre


def test_empleado_codigo_por_empresa_e_identidad_global(api,empresas):
    a,b,_,_=empresas
    sa,_,_=mercaderia(a);sb,_,_=mercaderia(b)
    datos=datos_empleado(sa)
    for e,s in ((a,sa),(b,sb)):
        r=api.post('/api/v1/empleados/crear-usuario',headers=admin(api,e),json={**datos,'sucursal_id':s,'username':datos['username']+e['codigo'].replace('-',''),'correo':e['codigo']+datos['correo']})
        assert r.status_code==200,r.text
    assert api.post('/api/v1/empleados/crear-usuario',headers=admin(api,a),json={**datos,'username':datos['username']+'otro','correo':'otro'+datos['correo']}).status_code==409


def test_encargado_consulta_solo_su_sucursal_y_no_escribe(api,empresas):
    a,b,_,_=empresas
    sa,_,_=mercaderia(a);sb,_,_=mercaderia(b)
    ciudad=consulta('SELECT id FROM ciudad WHERE empresa_id=%s',(a['id'],),True)['id']
    otra=consulta("INSERT INTO sucursal(empresa_id,ciudad_id,nombre,direccion) VALUES(%s,%s,'Otra','Prueba') RETURNING id",(a['id'],ciudad),True)['id']
    ha=admin(api,a)
    encargado,datos=nuevo_empleado(api,ha,sa,'ENCARGADO_SUCURSAL')
    propio,_=nuevo_empleado(api,ha,sa)
    ajeno,_=nuevo_empleado(api,ha,otra)
    extranjero,_=nuevo_empleado(api,admin(api,b),sb)
    h=login(api,a,datos['username'])
    pid=proveedor(api,ha)
    opciones=api.get('/api/v1/inventario/proveedores-opciones',headers=h)
    assert opciones.status_code==200 and opciones.json()==[{'id':pid,'nombre':'Proveedor prueba','activo':True}]
    assert api.get('/api/v1/proveedores',headers=h).status_code==403
    lista=api.get('/api/v1/empleados?incluir_inactivos=true',headers=h)
    assert lista.status_code==200,lista.text
    assert {e['empleado_id'] for e in lista.json()}=={encargado['empleado_id'],propio['empleado_id']}
    for e in (ajeno,extranjero):
        assert api.get(f"/api/v1/empleados/{e['empleado_id']}",headers=h).status_code in (403,404)
    eid=propio['empleado_id']
    for metodo,ruta,body in [('post','/crear-usuario',datos_empleado(sa)),('post','/asignar-usuario',{'usuario_id':propio['usuario_id'],**datos_empleado(sa)}),
                             ('put',f'/{eid}',{k:datos[k] for k in ('sucursal_id','codigo_empleado','cargo','rol')}),
                             ('patch',f'/{eid}/desactivar',{}),('patch',f'/{eid}/activar',{'rol':'CAJERO'})]:
        assert getattr(api,metodo)('/api/v1/empleados'+ruta,headers=h,json=body).status_code==403


def test_empleado_inactivo_conserva_rol_y_revoca_sesion(api,empresas):
    a,_,_,_=empresas;h=admin(api,a);s,_,_=mercaderia(a)
    e,datos=nuevo_empleado(api,h,s)
    anterior=login(api,a,datos['username'])
    assert api.patch(f"/api/v1/empleados/{e['empleado_id']}/desactivar",headers=h).status_code==200
    assert api.get('/api/v1/perfil',headers=anterior).status_code==401
    listado=api.get('/api/v1/empleados?incluir_inactivos=true',headers=h).json()
    inactivo=next(r for r in listado if r['empleado_id']==e['empleado_id'])
    assert not inactivo['activo'] and inactivo['rol_laboral']=='CAJERO'
    r=api.patch(f"/api/v1/empleados/{e['empleado_id']}/activar",headers=h,json={'rol':'CAJERO'})
    assert r.status_code==200,r.text
    assert r.json()['roles']==['CAJERO']
    login(api,a,datos['username'])


@pytest.mark.parametrize('rol',['ADMINISTRADOR','ADMIN_SAAS','PROVEEDOR','CLIENTE'])
def test_no_elevar_privilegios_desde_empleados(api,empresas,rol):
    a,_,_,_=empresas;s,_,_=mercaderia(a)
    r=api.post('/api/v1/empleados/crear-usuario',headers=admin(api,a),json=datos_empleado(s,rol=rol))
    assert r.status_code==400,r.text


def test_asignar_usuario_existente_y_cambiar_asignacion(api,empresas):
    a,b,_,_=empresas;h=admin(api,a);s,_,_=mercaderia(a);sb,_,_=mercaderia(b)
    uid,_,nombre=cliente(a);hb=login(api,a,nombre)
    datos={k:v for k,v in datos_empleado(s).items() if k in ('sucursal_id','codigo_empleado','cargo','rol')}
    r=api.post('/api/v1/empleados/asignar-usuario',headers=h,json={'usuario_id':uid,**datos})
    assert r.status_code==200,r.text
    assert api.get('/api/v1/perfil',headers=hb).status_code==401
    eid=r.json()['empleado_id']
    assert api.put(f'/api/v1/empleados/{eid}',headers=h,json={**datos,'sucursal_id':sb}).status_code==404
    assert api.put(f'/api/v1/empleados/{eid}',headers=h,json={**datos,'rol':'PERSONAL_VENTAS','cargo':'Asesor'}).status_code==200
    assert api.get(f'/api/v1/empleados/{eid}',headers=h).json()['rol_laboral']=='PERSONAL_VENTAS'


def test_cupo_empleados_concurrente_es_atomico(api,empresas):
    a,_,plan,_=empresas;h=admin(api,a);s,_,_=mercaderia(a)
    consulta('UPDATE plan SET limites=\'{"usuarios":50,"empleados":1}\'::jsonb WHERE id=%s',(plan['id'],))
    with ThreadPoolExecutor(max_workers=2) as pool:
        respuestas=list(pool.map(lambda _:api.post('/api/v1/empleados/crear-usuario',headers=h,json=datos_empleado(s)),range(2)))
    assert sorted(r.status_code for r in respuestas)==[200,403]
    assert consulta('SELECT count(*) n FROM empleado WHERE empresa_id=%s',(a['id'],),True)['n']==1
    assert consulta('SELECT count(*) n FROM usuario WHERE empresa_id=%s',(a['id'],),True)['n']==2


def test_proveedor_cuenta_productos_stock_y_acceso_solo_consulta(api,empresas):
    a,b,_,_=empresas;ha,hb=admin(api,a),admin(api,b)
    sa,pa,va=mercaderia(a);_,pb,_=mercaderia(b)
    pid=proveedor(api,ha);otro=proveedor(api,hb)
    uid,nombre=cuenta_proveedor(api,ha,pid)
    hp=login(api,a,nombre)
    assert api.get('/api/v1/proveedor-panel/productos',headers=hp).json()==[]
    assert api.post(f'/api/v1/proveedores/{pid}/productos',headers=ha,json={'producto_id':pb}).status_code==404
    r=api.post(f'/api/v1/proveedores/{pid}/productos',headers=ha,json={'producto_id':pa})
    assert r.status_code==200,r.text
    assert {p['producto_id'] for p in api.get('/api/v1/proveedor-panel/productos',headers=hp).json()}=={pa}
    assert {v['producto_variante_id'] for v in api.get('/api/v1/proveedor-panel/stock',headers=hp).json()}=={va}
    assert api.get('/api/v1/proveedor-panel/entregas',headers=hp).json()==[]
    entrega=api.post('/api/v1/movimientos-inventario',headers=ha,json={'sucursal_id':sa,'producto_variante_id':va,'tipo':'ENTRADA','cantidad':3,'proveedor_id':pid,'motivo':'Entrega de prueba'})
    assert entrega.status_code==200,entrega.text
    entregas=api.get('/api/v1/proveedor-panel/entregas',headers=hp).json()
    assert len(entregas)==1 and entregas[0]['cantidad']==3 and entregas[0]['producto_id']==pa
    assert api.get(f'/api/v1/proveedores/{otro}',headers=ha).status_code==404
    assert api.post('/api/v1/proveedores',headers=hp,json={'nombre':'Intruso'}).status_code==403
    assert api.put(f'/api/v1/proveedores/{pid}',headers=hp,json={'nombre':'Intruso'}).status_code==403
    assert api.post(f'/api/v1/proveedores/{pid}/productos',headers=hp,json={'producto_id':pa}).status_code==403
    assert api.post('/api/v1/productos',headers=hp,json={}).status_code==403
    assert api.delete(f'/api/v1/proveedores/{pid}/productos/{pa}',headers=ha).status_code==200
    assert api.get('/api/v1/proveedor-panel/productos',headers=hp).json()==[]
    assert consulta('SELECT activo FROM producto_proveedor WHERE producto_id=%s AND proveedor_id=%s',(pa,pid),True)['activo'] is False


def test_vinculo_existente_asigna_rol_y_desvinculacion_revoca_acceso(api,empresas):
    a,b,_,_=empresas;h=admin(api,a);pid=proveedor(api,h);otro=proveedor(api,h,'9876')
    uid,_,nombre=cliente(a);ajeno,_,_=cliente(b)
    assert api.post(f'/api/v1/proveedores/{pid}/usuarios',headers=h,json={'usuario_id':ajeno}).status_code==404
    r=api.post(f'/api/v1/proveedores/{pid}/usuarios',headers=h,json={'usuario_id':uid})
    assert r.status_code==200,r.text
    hp=login(api,a,nombre)
    assert api.get('/api/v1/proveedor-panel/perfil',headers=hp).status_code==200
    assert api.post(f'/api/v1/proveedores/{otro}/usuarios',headers=h,json={'usuario_id':uid}).status_code==409
    assert api.delete(f'/api/v1/proveedores/{pid}/usuarios/{uid}',headers=h).status_code==200
    assert api.get('/api/v1/proveedor-panel/perfil',headers=hp).status_code==401
    hp=login(api,a,nombre)
    assert api.get('/api/v1/proveedor-panel/perfil',headers=hp).status_code==403


def test_proveedor_desactivar_reactivar_y_nit_por_empresa(api,empresas):
    a,b,_,_=empresas;h=admin(api,a);pid=proveedor(api,h);proveedor(api,admin(api,b))
    assert api.post('/api/v1/proveedores',headers=h,json={'nombre':'Duplicado','nit':'123456'}).status_code==409
    uid,nombre=cuenta_proveedor(api,h,pid);hp=login(api,a,nombre)
    assert api.patch(f'/api/v1/proveedores/{pid}/desactivar',headers=h).status_code==200
    assert api.get('/api/v1/proveedor-panel/perfil',headers=hp).status_code==401
    assert consulta('SELECT activo FROM proveedor_usuario WHERE usuario_id=%s',(uid,),True)['activo'] is True
    assert api.patch(f'/api/v1/proveedores/{pid}/activar',headers=h).status_code==200
    hp=login(api,a,nombre)
    assert api.get('/api/v1/proveedor-panel/perfil',headers=hp).status_code==200


def test_cupo_cuentas_proveedor_no_deja_vinculos_parciales(api,empresas):
    a,_,plan,_=empresas;h=admin(api,a);pid=proveedor(api,h)
    consulta('UPDATE plan SET limites=\'{"usuarios":1}\'::jsonb WHERE id=%s',(plan['id'],))
    datos=dict(nombre='Sin',apellido='Cupo',username='sincupo',correo='sincupo@example.invalid',password='Prueba-aislada-123')
    assert api.post(f'/api/v1/proveedores/{pid}/crear-usuario',headers=h,json=datos).status_code==409
    assert consulta('SELECT count(*) n FROM proveedor_usuario WHERE proveedor_id=%s',(pid,),True)['n']==0


def test_panel_sin_vinculo_y_empresa_suspendida(api,empresas):
    a,_,_,_=empresas;h=admin(api,a);pid=proveedor(api,h);_,nombre=cuenta_proveedor(api,h,pid);hp=login(api,a,nombre)
    assert api.get('/api/v1/proveedor-panel/perfil',headers=h).status_code==403
    consulta("UPDATE empresa SET estado='SUSPENDIDA' WHERE id=%s",(a['id'],))
    assert api.get('/api/v1/proveedor-panel/perfil',headers=hp).status_code==200
    assert api.post('/api/v1/proveedores',headers=h,json={'nombre':'No permitido'}).status_code==403
