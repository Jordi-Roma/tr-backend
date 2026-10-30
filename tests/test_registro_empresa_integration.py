"""Registro público sin SMTP; solo PostgreSQL local desechable explícito."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from test_multitenant_integration import actor, empresas, consulta
from test_cuenta_integration import login
from app.main import app
from app.core.security import verificar_password
from app.modules.administracion.services import registro_empresa_service as servicio

BASE = '/api/v1/empresas/registro'
PASSWORD = 'Empresa-prueba-123'


@pytest.fixture
def api():
    return TestClient(app)


@pytest.fixture
def publicada(empresas):
    a,b,plan,actor_id = empresas
    consulta('UPDATE plan SET publico=TRUE WHERE id=%s',(plan['id'],))
    return a,b,plan,actor_id


def datos(plan, **cambios):
    sufijo = uuid4().hex[:12]
    return {
        'clave_solicitud':str(uuid4()), 'empresa_codigo':'tienda-'+sufijo,
        'empresa_nombre':'Mi nueva empresa', 'plan_id':plan['id'],
        'nombre':'Ana', 'apellido':'Prueba', 'username':'admin_'+sufijo,
        'correo':sufijo+'@example.invalid', 'password':PASSWORD,
        'confirmar_password':PASSWORD, **cambios,
    }


def solicitar(api, cuerpo):
    r = api.post(BASE,json=cuerpo)
    assert r.status_code == 201,r.text
    return r.json()['empresa']


def test_solo_planes_publicos_y_activos(api,publicada):
    a,_,plan,_=publicada
    r=api.get(BASE+'/planes')
    assert r.status_code==200
    p=next(p for p in r.json() if p['id']==plan['id'])
    assert set(p)=={'id','nombre','limites','funciones'}
    privado=consulta("INSERT INTO plan(codigo,nombre) VALUES(%s,'Interno') RETURNING id",('I_'+uuid4().hex,),True)['id']
    assert privado not in {p['id'] for p in api.get(BASE+'/planes').json()}
    consulta('UPDATE plan SET activo=FALSE WHERE id=%s',(plan['id'],))
    assert plan['id'] not in {p['id'] for p in api.get(BASE+'/planes').json()}
    assert api.post(BASE,json=datos(plan)).status_code==400


def test_alta_pendiente_sin_correo_sin_sesion_y_sin_privilegios_saas(api,publicada,monkeypatch):
    from app.core import email
    def prohibido(*_):
        raise AssertionError('El registro de empresas no debe enviar correos.')
    monkeypatch.setattr(email,'enviar_correo',prohibido)
    a,_,plan,_=publicada
    cuerpo=datos(plan); empresa=solicitar(api,cuerpo)
    assert empresa['estado']=='PENDIENTE'
    u=consulta('SELECT id,password_hash FROM usuario WHERE empresa_id=%s',(empresa['id'],),True)
    assert verificar_password(PASSWORD,u['password_hash'])
    roles=consulta('SELECT r.nombre FROM usuario_rol ur JOIN rol r ON r.id=ur.rol_id WHERE ur.usuario_id=%s',(u['id'],))
    assert roles==[{'nombre':'ADMINISTRADOR'}]
    assert consulta('SELECT estado FROM suscripcion WHERE empresa_id=%s',(empresa['id'],),True)['estado']=='PENDIENTE'
    assert empresa['id'] not in {e['id'] for e in api.get('/api/v1/empresas/publicas').json()}
    assert api.get('/api/v1/empresas/publica/'+empresa['codigo']).status_code==404
    for codigo in (empresa['codigo'],None,a['codigo']):
        assert api.post('/api/v1/autenticacion/login',json={'identificador':cuerpo['username'],'password':PASSWORD,'empresa_codigo':codigo}).status_code==401
    assert api.get('/api/v1/catalogo/prendas',headers={'X-Empresa-Codigo':empresa['codigo']}).status_code==404
    assert not consulta('SELECT id FROM sesion WHERE usuario_id=%s',(u['id'],))
    assert PASSWORD not in str(consulta('SELECT * FROM solicitud_registro_empresa WHERE empresa_id=%s',(empresa['id'],),True))


def test_reintento_concurrente_crea_una_sola_empresa(publicada):
    _,_,plan,_=publicada; cuerpo=datos(plan)
    with TestClient(app) as cliente:
        with ThreadPoolExecutor(max_workers=2) as pool:
            respuestas=list(pool.map(lambda _: cliente.post(BASE,json=cuerpo),range(2)))
    assert [r.status_code for r in respuestas]==[201,201]
    assert respuestas[0].json()['empresa']['id']==respuestas[1].json()['empresa']['id']
    with TestClient(app) as cliente:
        assert cliente.post(BASE,json={**cuerpo,'empresa_nombre':'Otra empresa'}).status_code==400
    assert consulta('SELECT count(*) AS n FROM empresa WHERE codigo=%s',(cuerpo['empresa_codigo'],),True)['n']==1


def test_codigo_duplicado_revierte_alta(api,publicada):
    a,_,plan,_=publicada; cuerpo=datos(plan,empresa_codigo=a['codigo'])
    assert api.post(BASE,json=cuerpo).status_code==409
    assert not consulta('SELECT id FROM solicitud_registro_empresa WHERE id=%s',(cuerpo['clave_solicitud'],))
    assert not consulta('SELECT id FROM usuario WHERE correo=%s',(cuerpo['correo'],))


def test_fallo_final_revierte_empresa_suscripcion_y_usuario(api,publicada,monkeypatch):
    from app.modules.administracion.repositories import registro_empresa_repository as repo
    _,_,plan,_=publicada; cuerpo=datos(plan)
    def fallar(*_):raise ValueError('Fallo final simulado')
    monkeypatch.setattr(repo,'auditar',fallar)
    assert api.post(BASE,json=cuerpo).status_code==400
    assert not consulta('SELECT id FROM empresa WHERE codigo=%s',(cuerpo['empresa_codigo'],))
    assert not consulta('SELECT id FROM usuario WHERE correo=%s',(cuerpo['correo'],))
    assert not consulta('SELECT id FROM solicitud_registro_empresa WHERE id=%s',(cuerpo['clave_solicitud'],))


@pytest.mark.parametrize('cambio',[
    {'roles':['ADMIN_SAAS']}, {'estado':'ACTIVA'}, {'empresa_id':1},
    {'fecha_vencimiento':'2099-01-01'}, {'password':'Debil','confirmar_password':'Debil'},
    {'correo':'sin-arroba'}, {'confirmar_password':'Otra-password-123'}, {'nombre':'   '},
])
def test_campos_invalidos_o_privilegios_no_son_admitidos(api,publicada,cambio):
    _,_,plan,_=publicada
    assert api.post(BASE,json=datos(plan,**cambio)).status_code==422


def test_solo_as_aprueba_y_activa_plan_y_empresa_juntos(api,publicada):
    a,b,plan,actor_id=publicada; cuerpo=datos(plan); e=solicitar(api,cuerpo)
    ha=login(api,a,a['codigo'])
    as_usuario=consulta('SELECT username FROM usuario WHERE id=%s',(actor_id,),True)['username']
    hs=login(api,None,as_usuario,'Prueba-AS-local-123')
    url=f'/api/v1/saas/empresas/{e["id"]}'
    alta={'plan_id':plan['id'],'fecha_inicio':str(date.today()),'fecha_vencimiento':str(date.today()+timedelta(days=30))}
    assert api.post(url+'/suscripcion',headers=ha,json=alta).status_code==403
    assert api.patch(url+'/estado',headers=hs,json={'estado':'ACTIVA'}).status_code==400
    listado=api.get('/api/v1/saas/empresas',headers=hs).json()
    fila=next(x for x in listado if x['id']==e['id'])
    assert fila['correo_contacto']==cuerpo['correo']
    assert api.post(url+'/suscripcion',headers=hs,json=alta).status_code==200
    assert consulta('SELECT estado FROM empresa WHERE id=%s',(e['id'],),True)['estado']=='ACTIVA'
    assert consulta("SELECT count(*) AS n FROM suscripcion WHERE empresa_id=%s AND estado='ACTIVA'",(e['id'],),True)['n']==1
    assert consulta("SELECT count(*) AS n FROM suscripcion WHERE empresa_id=%s AND estado='PENDIENTE'",(e['id'],),True)['n']==0
    he=login(api,e,cuerpo['username'],PASSWORD)
    assert api.get('/api/v1/mi-empresa/plan',headers=he).json()['operaciones_habilitadas'] is True
    assert api.get('/api/v1/saas/empresas',headers=he).status_code==403
    assert api.get('/api/v1/empresas/publica/'+e['codigo']).status_code==200
    reintento=api.post(BASE,json=cuerpo).json()
    assert reintento['empresa']['estado']=='ACTIVA'
    assert 'ya fue aprobada' in reintento['mensaje']
    assert consulta("SELECT id FROM evento_plataforma WHERE actor_id=%s AND empresa_id=%s AND accion='APROBAR_REGISTRO_EMPRESA'",(actor_id,e['id']))
    assert consulta('SELECT estado FROM empresa WHERE id=%s',(b['id'],),True)['estado']=='ACTIVA'


def test_rechazar_no_borra_historial_ni_reintento_reabre_empresa(api,publicada):
    _,_,plan,actor_id=publicada; cuerpo=datos(plan); e=solicitar(api,cuerpo)
    nombre=consulta('SELECT username FROM usuario WHERE id=%s',(actor_id,),True)['username']
    hs=login(api,None,nombre,'Prueba-AS-local-123')
    assert api.patch(f'/api/v1/saas/empresas/{e["id"]}/estado',headers=hs,json={'estado':'CANCELADA'}).status_code==200
    assert solicitar(api,cuerpo)['estado']=='CANCELADA'
    assert 'cancelada' in api.post(BASE,json=cuerpo).json()['mensaje']
    assert consulta('SELECT id FROM solicitud_registro_empresa WHERE empresa_id=%s',(e['id'],))


def test_identidad_global_duplicada_y_plan_privado(api,publicada):
    _,_,plan,_=publicada; cuerpo=datos(plan)
    solicitar(api,cuerpo)
    assert api.post(BASE,json=datos(plan,correo=cuerpo['correo'])).status_code==409
    assert api.post(BASE,json=datos(plan,username=cuerpo['username'])).status_code==409
    consulta('UPDATE plan SET publico=FALSE WHERE id=%s',(plan['id'],))
    assert api.post(BASE,json=datos(plan)).status_code==400


def test_limite_de_altas_por_origen(publicada):
    _,_,plan,_=publicada; origen='prueba-'+uuid4().hex
    for _ in range(20):
        codigo=uuid4().hex
        eid=consulta("INSERT INTO empresa(nombre,codigo,estado) VALUES('Pendiente',%s,'PENDIENTE') RETURNING id",(codigo,),True)['id']
        consulta("""INSERT INTO solicitud_registro_empresa(id,empresa_id,correo_contacto,responsable,origen_hash,huella_alta)
            VALUES(%s,%s,%s,'Prueba',%s,%s)""",(str(uuid4()),eid,codigo+'@example.invalid',servicio._hash('origen:'+origen),'0'*64))
    with TestClient(app,client=(origen,5000)) as cliente:
        r=cliente.post(BASE,json=datos(plan))
    assert r.status_code==429
    assert r.headers['Retry-After']=='3600'


def test_as_publica_planes_y_rechaza_publicar_legado_o_cupo_cero(api,publicada):
    a,_,plan,actor_id=publicada; nombre=consulta('SELECT username FROM usuario WHERE id=%s',(actor_id,),True)['username']
    hs=login(api,None,nombre,'Prueba-AS-local-123'); ha=login(api,a,a['codigo'])
    cuerpo={'codigo':'P_'+uuid4().hex,'nombre':'Plan público','limites':{'usuarios':10},'funciones':{},'publico':True}
    assert api.post('/api/v1/saas/planes',headers=ha,json=cuerpo).status_code==403
    r=api.post('/api/v1/saas/planes',headers=hs,json=cuerpo)
    assert r.status_code==201 and r.json()['publico'] is True
    for cambios in ({'codigo':'STYLEAR_LEGADO'},{'limites':{'usuarios':0}}):
        assert api.post('/api/v1/saas/planes',headers=hs,json={**cuerpo,**cambios}).status_code==422
