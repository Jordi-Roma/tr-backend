"""CU06 sobre una base explícita y desechable; reutiliza la barrera de seguridad."""
from concurrent.futures import ThreadPoolExecutor

import psycopg2
import pytest
from fastapi.testclient import TestClient

from test_multitenant_integration import actor, empresas, cliente, consulta, DSN
from test_cuenta_integration import login
from app.main import app


@pytest.fixture
def api():
    with TestClient(app) as client:
        yield client


def admin(api, empresa):
    return login(api, empresa, empresa['codigo'])


def ciudad(api, headers, nombre='Ciudad nueva'):
    respuesta = api.post('/api/v1/ciudades', headers=headers,
                         json={'nombre': nombre, 'departamento': 'Prueba'})
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()['id']


def sucursal(api, headers, cid, nombre='Sucursal nueva'):
    return api.post('/api/v1/sucursales', headers=headers,
                    json={'ciudad_id': cid, 'nombre': nombre, 'direccion': 'Calle 123',
                          'latitud': -17.78, 'longitud': -63.18})


def test_ciudades_aisladas_duplicados_y_acceso_por_id(api, empresas):
    a, b, _, _ = empresas
    ha, hb = admin(api, a), admin(api, b)
    ca, cb = ciudad(api, ha), ciudad(api, hb)
    assert ca != cb
    assert ca not in [c['id'] for c in api.get('/api/v1/ciudades', headers=hb).json()]
    assert api.get(f'/api/v1/ciudades/{ca}', headers=hb).status_code == 404
    assert api.put(f'/api/v1/ciudades/{ca}', headers=hb, json={'nombre': 'Intrusión'}).status_code == 404
    for accion in ('activar', 'desactivar'):
        assert api.patch(f'/api/v1/ciudades/{ca}/{accion}', headers=hb).status_code == 404
    assert api.post('/api/v1/ciudades', headers=ha,
                    json={'nombre': 'CIUDAD NUEVA', 'departamento': 'prueba'}).status_code == 409
    assert api.put(f'/api/v1/ciudades/{ca}', headers=ha,
                   json={'nombre': 'Ciudad editada', 'departamento': 'Prueba'}).status_code == 200
    # NULL no permite duplicados invisibles al índice.
    assert api.post('/api/v1/ciudades', headers=ha, json={'nombre': 'Sin departamento'}).status_code == 200
    assert api.post('/api/v1/ciudades', headers=ha, json={'nombre': 'SIN DEPARTAMENTO'}).status_code == 409


def test_sucursales_solo_ciudades_propias_y_duplicados(api, empresas):
    a, b, _, _ = empresas
    ha, hb = admin(api, a), admin(api, b)
    ca, cb = ciudad(api, ha), ciudad(api, hb)
    assert sucursal(api, ha, cb).status_code == 400
    respuesta = sucursal(api, ha, ca)
    assert respuesta.status_code == 200, respuesta.text
    sid = respuesta.json()['id']
    assert sucursal(api, ha, ca, 'SUCURSAL NUEVA').status_code == 409
    assert api.get(f'/api/v1/sucursales/{sid}', headers=hb).status_code == 404
    assert api.put(f'/api/v1/sucursales/{sid}', headers=ha,
                   json={'ciudad_id': cb, 'nombre': 'Otra', 'direccion': 'Calle 123'}).status_code == 400
    assert api.put(f'/api/v1/sucursales/{sid}', headers=ha,
                   json={'ciudad_id': ca, 'nombre': 'Editada', 'direccion': 'Calle 456'}).status_code == 200
    assert api.patch(f'/api/v1/sucursales/{sid}/desactivar', headers=hb).status_code == 404


def test_desactivacion_conserva_historial_y_reactivacion(api, empresas):
    a, _, _, _ = empresas
    h = admin(api, a)
    cid = ciudad(api, h)
    r = sucursal(api, h, cid)
    assert r.status_code == 200, r.text
    sid = r.json()['id']
    assert api.patch(f'/api/v1/ciudades/{cid}/desactivar', headers=h).status_code == 400
    assert api.patch(f'/api/v1/sucursales/{sid}/desactivar', headers=h).status_code == 200
    assert api.patch(f'/api/v1/ciudades/{cid}/desactivar', headers=h).status_code == 200
    assert cid not in [c['id'] for c in api.get('/api/v1/ciudades', headers=h).json()]
    assert any(c['id'] == cid and not c['activo'] for c in api.get('/api/v1/ciudades?incluir_inactivos=true', headers=h).json())
    assert any(s['id'] == sid and not s['activo'] for s in api.get('/api/v1/sucursales?incluir_inactivos=true', headers=h).json())
    assert api.patch(f'/api/v1/sucursales/{sid}/activar', headers=h).status_code == 400
    assert api.patch(f'/api/v1/ciudades/{cid}/activar', headers=h).status_code == 200
    assert api.patch(f'/api/v1/sucursales/{sid}/activar', headers=h).status_code == 200
    assert consulta('SELECT ciudad_id FROM sucursal WHERE id=%s', (sid,), True)['ciudad_id'] == cid


def test_cupo_concurrente_y_reactivacion(api, empresas):
    a, _, plan, _ = empresas
    h = admin(api, a)
    cid = ciudad(api, h)
    consulta('UPDATE plan SET limites=\'{"sucursales":1}\'::jsonb WHERE id=%s', (plan['id'],))
    with ThreadPoolExecutor(max_workers=2) as pool:
        respuestas = list(pool.map(lambda n: sucursal(api, h, cid, f'Sucursal {n}'), range(2)))
    assert sorted(r.status_code for r in respuestas) == [200, 403]
    sid = next(r.json()['id'] for r in respuestas if r.status_code == 200)
    # Activar una sucursal ya activa es idempotente, aun con el cupo lleno.
    assert api.patch(f'/api/v1/sucursales/{sid}/activar', headers=h).status_code == 200
    assert api.patch(f'/api/v1/sucursales/{sid}/desactivar', headers=h).status_code == 200
    assert sucursal(api, h, cid, 'Reemplazo').status_code == 200
    assert api.patch(f'/api/v1/sucursales/{sid}/activar', headers=h).status_code == 403


def test_cliente_sin_escritura_y_direccion_sin_ciudad_ajena(api, empresas):
    a, b, _, _ = empresas
    ha, hb = admin(api, a), admin(api, b)
    ca, cb = ciudad(api, ha), ciudad(api, hb)
    _, _, nombre = cliente(a)
    h = login(api, a, nombre)
    assert api.post('/api/v1/ciudades', headers=h, json={'nombre': 'Prohibida'}).status_code == 403
    assert sucursal(api, h, ca).status_code == 403
    assert api.get('/api/v1/ciudades?incluir_inactivos=true', headers=h).status_code == 403
    assert api.post('/api/v1/perfil/direcciones', headers=h,
                    json={'ciudad_id': cb, 'direccion': 'Ajena'}).status_code == 400
    assert api.post('/api/v1/perfil/direcciones', headers=h,
                    json={'ciudad_id': ca, 'direccion': 'Propia'}).status_code == 200


def test_saas_no_gestiona_ciudades_comerciales(api, empresas):
    _, _, _, actor_id = empresas
    nombre = consulta('SELECT username FROM usuario WHERE id=%s', (actor_id,), True)['username']
    h = login(api, None, nombre, 'Prueba-AS-local-123')
    assert api.get('/api/v1/ciudades', headers=h).status_code == 403
    assert api.post('/api/v1/ciudades', headers=h, json={'nombre': 'Prohibida'}).status_code == 403


def test_suscripcion_suspendida_consulta_y_no_alta(api, empresas):
    a, _, _, _ = empresas
    h = admin(api, a)
    cid = ciudad(api, h)
    consulta("UPDATE empresa SET estado='SUSPENDIDA' WHERE id=%s", (a['id'],))
    assert api.get('/api/v1/ciudades', headers=h).status_code == 200
    assert api.post('/api/v1/ciudades', headers=h, json={'nombre': 'Nueva'}).status_code == 403
    assert api.patch(f'/api/v1/ciudades/{cid}/desactivar', headers=h).status_code == 200
    assert api.patch(f'/api/v1/ciudades/{cid}/activar', headers=h).status_code == 403


def test_integridad_tambien_desde_sql(api, empresas):
    a, b, _, _ = empresas
    ca, cb = ciudad(api, admin(api, a)), ciudad(api, admin(api, b))
    with psycopg2.connect(DSN) as conn:
        with conn.cursor() as cur:
            with pytest.raises(psycopg2.IntegrityError):
                cur.execute("INSERT INTO sucursal(empresa_id,ciudad_id,nombre,direccion) VALUES(%s,%s,'Ajena','Prueba')", (a['id'], cb))
        conn.rollback()
    assert consulta('SELECT empresa_id FROM ciudad WHERE id=%s', (ca,), True)['empresa_id'] == a['id']


def test_validacion_de_datos(api, empresas):
    a, _, _, _ = empresas
    h = admin(api, a)
    for nombre in (' ', 'x', 'x'*121):
        assert api.post('/api/v1/ciudades', headers=h, json={'nombre': nombre}).status_code == 422
    cid = ciudad(api, h)
    assert api.post('/api/v1/sucursales', headers=h,
                    json={'ciudad_id': cid, 'nombre': 'Nombre', 'direccion': 'Calle', 'latitud': 91}).status_code == 422
