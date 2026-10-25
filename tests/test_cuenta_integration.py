"""CU02/CU03: PostgreSQL local desechable, nunca la base configurada en .env."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
import re

import pytest
from fastapi.testclient import TestClient

# Esta importación valida el destino antes de cargar la aplicación y permite
# omitir toda la suite si no se indicó una base de pruebas explícitamente.
from test_multitenant_integration import actor, empresas, cliente, consulta, mercaderia
from app.main import app
from app.modules.autenticacion.services import password_reset_service as reset
from app.modules.autenticacion.repositories import password_reset_repository as tokens
from app.core.security import hashear_password

PASSWORD = 'Prueba-aislada-123'
NUEVA = 'Cuenta-nueva-segura-456'


@pytest.fixture
def api():
    return TestClient(app)


def login(api, empresa, nombre, password=PASSWORD):
    r = api.post('/api/v1/autenticacion/login', json={
        'identificador': nombre, 'password': password,
        'empresa_codigo': empresa['codigo'] if empresa else None})
    assert r.status_code == 200, r.text
    h = {'Authorization': 'Bearer '+r.json()['access_token']}
    if empresa:
        h['X-Empresa-Codigo'] = empresa['codigo']
    return h


def perfil(api, h):
    r = api.get('/api/v1/perfil', headers=h)
    assert r.status_code == 200, r.text
    p = r.json()
    return {k: p[k] for k in ('nombre', 'apellido', 'telefono', 'username', 'correo')}


def solicitud(api, empresa, nombre):
    return api.post('/api/v1/autenticacion/password-reset/solicitar', json={
        'identificador': nombre, 'empresa_codigo': empresa['codigo'] if empresa else None})


def confirmar(api, empresa, nombre, codigo):
    return api.post('/api/v1/autenticacion/password-reset/confirmar', json={
        'identificador': nombre, 'empresa_codigo': empresa['codigo'] if empresa else None,
        'codigo': codigo, 'password_nuevo': NUEVA, 'confirmar_password_nuevo': NUEVA})


@pytest.fixture
def correos(monkeypatch):
    enviados = []
    monkeypatch.setattr(reset, 'enviar_correo', lambda destino, asunto, cuerpo: enviados.append(
        {'destino': destino, 'codigo': re.search(r'Codigo: (\d{6})', cuerpo)[1]}))
    return enviados


def test_perfil_personal_empresa_inmutable_y_sin_secretos(api, empresas):
    a, b, _, _ = empresas
    uid, _, nombre = cliente(a)
    h = login(api, a, nombre)
    p = perfil(api, h)
    p.update(nombre='Nuevo nombre', telefono='70012345')
    r = api.put('/api/v1/perfil', headers=h, json=p)
    assert r.status_code == 200, r.text
    assert r.json()['sesion_revocada'] is False
    assert r.json()['empresa_id'] == a['id']
    assert not {'password_hash', 'intentos_fallidos', 'bloqueado_hasta'} & r.json().keys()
    assert api.get('/api/v1/perfil', headers=h).json()['nombre'] == 'Nuevo nombre'
    assert api.put('/api/v1/perfil', headers=h, json={**p, 'empresa_id': b['id']}).status_code == 422
    assert api.put('/api/v1/perfil', headers=h, json={**p, 'roles': ['ADMIN']}).status_code == 422
    assert api.get('/api/v1/perfil', headers={**h, 'X-Empresa-Codigo': b['codigo']}).status_code == 403
    assert consulta('SELECT empresa_id FROM usuario WHERE id=%s', (uid,), True)['empresa_id'] == a['id']


def test_cambiar_identidad_exige_password_y_revoca_todas_las_sesiones(api, empresas, correos):
    a, _, _, _ = empresas
    uid, _, nombre = cliente(a)
    h, otro = login(api, a, nombre), login(api, a, nombre)
    p = perfil(api, h)
    solicitud(api, a, nombre)
    p.update(username=nombre+'x', correo=nombre+'x@example.invalid')
    assert api.put('/api/v1/perfil', headers=h, json=p).status_code == 400
    assert api.put('/api/v1/perfil', headers=h, json={**p, 'password_actual': 'mal'}).status_code == 400
    r = api.put('/api/v1/perfil', headers=h, json={**p, 'password_actual': PASSWORD})
    assert r.status_code == 200, r.text
    assert r.json()['sesion_revocada'] is True
    for headers in (h, otro):
        assert api.get('/api/v1/perfil', headers=headers).status_code == 401
    assert consulta('SELECT count(*) n FROM password_reset_token WHERE usuario_id=%s AND NOT usado', (uid,), True)['n'] == 0
    login(api, a, p['correo'])


def test_identidad_duplicada_revierte_perfil_completo(api, empresas):
    a, _, _, _ = empresas
    _, _, nombre = cliente(a)
    _, _, otro = cliente(a)
    h = login(api, a, nombre)
    antes = perfil(api, h)
    r = api.put('/api/v1/perfil', headers=h, json={**antes, 'nombre': 'No guardar', 'username': otro, 'password_actual': PASSWORD})
    assert r.status_code == 409, r.text
    assert perfil(api, h) == antes


def test_password_revoca_todas_sesiones_y_tokens(api, empresas, correos):
    a, _, _, _ = empresas
    _, _, nombre = cliente(a)
    h, otro = login(api, a, nombre), login(api, a, nombre)
    solicitud(api, a, nombre)
    body = {'password_actual': PASSWORD, 'password_nuevo': NUEVA, 'confirmar_password_nuevo': NUEVA}
    assert api.put('/api/v1/perfil/password', headers=h, json={**body, 'password_actual': 'mala'}).status_code == 400
    assert api.put('/api/v1/perfil/password', headers=h, json=body).status_code == 200
    assert api.get('/api/v1/perfil', headers=otro).status_code == 401
    assert confirmar(api, a, nombre, correos[-1]['codigo']).status_code == 400
    login(api, a, nombre, NUEVA)


def test_direcciones_solo_propias_y_principal_atomica(api, empresas):
    a, b, _, _ = empresas
    _, _, nombre = cliente(a)
    _, _, vecino = cliente(a)
    _, _, ajeno = cliente(b)
    h = login(api, a, nombre)
    hv, hb = login(api, a, vecino), login(api, b, ajeno)
    ciudad = consulta('SELECT id FROM ciudad WHERE activo AND empresa_id=%s LIMIT 1', (a['id'],), True)['id']
    body = {'ciudad_id': ciudad, 'direccion': 'Calle propia 123', 'es_principal': True}
    d = api.post('/api/v1/perfil/direcciones', headers=h, json=body).json()
    for headers in (hv, hb):
        assert api.put('/api/v1/perfil/direcciones/'+str(d['id']), headers=headers, json=body).status_code == 404
        assert api.delete('/api/v1/perfil/direcciones/'+str(d['id']), headers=headers).status_code == 404
        assert api.get('/api/v1/perfil/direcciones', headers=headers).json()['direcciones'] == []
    # Un ID inexistente o ciudad inválida no elimina la dirección principal.
    assert api.put('/api/v1/perfil/direcciones/99999999', headers=h, json=body).status_code == 404
    assert api.post('/api/v1/perfil/direcciones', headers=h, json={**body, 'ciudad_id': 99999999}).status_code == 400
    assert api.get('/api/v1/perfil/direcciones', headers=h).json()['direcciones'][0]['es_principal'] is True
    with ThreadPoolExecutor(max_workers=2) as pool:
        respuestas = list(pool.map(lambda n: api.post('/api/v1/perfil/direcciones', headers=h, json={**body, 'direccion': 'Calle '+str(n)}), range(2)))
    assert all(r.status_code == 200 for r in respuestas)
    assert sum(d['es_principal'] for d in api.get('/api/v1/perfil/direcciones', headers=h).json()['direcciones']) == 1
    assert api.delete('/api/v1/perfil/direcciones/'+str(d['id']), headers=h).status_code == 200
    assert consulta('SELECT activo FROM direccion_cliente WHERE id=%s', (d['id'],), True)['activo'] is False


def test_desactivacion_conserva_reserva_direcciones_y_otra_cuenta(api, empresas, correos):
    from app.modules.reservas.repositories.carrito_repository import agregar_item_carrito
    from app.modules.reservas.repositories.reserva_repository import crear_reserva_desde_carrito
    a, _, _, _ = empresas
    uid, cid, nombre = cliente(a)
    _, _, vecino = cliente(a)
    suc, _, variante = mercaderia(a)
    agregar_item_carrito(cid, variante, suc, 1)
    crear_reserva_desde_carrito(uid, a['id'], suc, date.today()+timedelta(days=1), None)
    antes = consulta('SELECT * FROM reserva WHERE cliente_id=%s', (cid,))
    h, otro = login(api, a, nombre), login(api, a, nombre)
    ciudad = consulta('SELECT id FROM ciudad WHERE activo AND empresa_id=%s LIMIT 1', (a['id'],), True)['id']
    assert api.post('/api/v1/perfil/direcciones', headers=h, json={'ciudad_id': ciudad, 'direccion': 'Dirección conservada', 'es_principal': True}).status_code == 200
    direcciones_antes = consulta('SELECT * FROM direccion_cliente WHERE cliente_id=%s', (cid,))
    hv = login(api, a, vecino)
    solicitud(api, a, nombre)
    body = {'password_actual': PASSWORD, 'confirmacion': 'DESACTIVAR MI CUENTA'}
    assert api.post('/api/v1/perfil/desactivar', headers=h, json={**body, 'confirmacion': 'NO'}).status_code == 400
    assert api.post('/api/v1/perfil/desactivar', headers=h, json={**body, 'password_actual': 'incorrecta'}).status_code == 400
    assert api.post('/api/v1/perfil/desactivar', headers=h, json=body).status_code == 200
    assert consulta('SELECT * FROM reserva WHERE cliente_id=%s', (cid,)) == antes
    assert consulta('SELECT * FROM direccion_cliente WHERE cliente_id=%s', (cid,)) == direcciones_antes
    assert consulta('SELECT activo FROM cliente WHERE id=%s', (cid,), True)['activo'] is True
    assert consulta('SELECT activo FROM usuario WHERE id=%s', (uid,), True)['activo'] is False
    assert api.get('/api/v1/perfil', headers=otro).status_code == 401
    assert api.get('/api/v1/perfil', headers=hv).status_code == 200
    assert confirmar(api, a, nombre, correos[-1]['codigo']).status_code == 400
    assert api.post('/api/v1/autenticacion/login', json={'identificador': nombre, 'password': PASSWORD, 'empresa_codigo': a['codigo']}).status_code == 403


def test_personal_y_saas_tienen_perfil_pero_no_autodesactivacion(api, empresas):
    a, _, _, as_id = empresas
    as_nombre = consulta('SELECT username FROM usuario WHERE id=%s', (as_id,), True)['username']
    for empresa, nombre, password in ((a, a['codigo'], PASSWORD), (None, as_nombre, 'Prueba-AS-local-123')):
        h = login(api, empresa, nombre, password)
        assert api.get('/api/v1/perfil', headers=h).status_code == 200
        assert api.put('/api/v1/perfil', headers=h, json=perfil(api, h)).status_code == 200
        assert api.post('/api/v1/perfil/desactivar', headers=h, json={'password_actual': password, 'confirmacion': 'DESACTIVAR MI CUENTA'}).status_code == 403


def test_recuperacion_correo_propio_empresa_y_respuesta_generica(api, empresas, correos):
    a, b, _, _ = empresas
    uid, _, nombre = cliente(a)
    correcta = solicitud(api, a, nombre)
    assert correcta.status_code == 200
    assert correos == [{'destino': nombre+'@example.invalid', 'codigo': correos[0]['codigo']}]
    assert len(correos[0]['codigo']) == 6
    for empresa, cuenta in ((b, nombre), (None, nombre), (a, 'no-existe'), ({'codigo': 'no-existe'}, nombre)):
        assert solicitud(api, empresa, cuenta).json() == correcta.json()
    assert solicitud(api, a, nombre).json() == correcta.json()
    assert len(correos) == 1  # cooldown sin revelar existencia
    assert confirmar(api, b, nombre, correos[0]['codigo']).status_code == 400
    assert consulta('SELECT count(*) n FROM password_reset_token WHERE usuario_id=%s AND NOT usado', (uid,), True)['n'] == 1


def test_codigo_unico_reestablece_y_cierra_sesiones(api, empresas, correos):
    a, _, _, _ = empresas
    _, _, nombre = cliente(a)
    h = login(api, a, nombre)
    solicitud(api, a, nombre)
    codigo = correos[0]['codigo']
    assert confirmar(api, a, nombre, codigo).status_code == 200
    assert confirmar(api, a, nombre, codigo).status_code == 400
    assert api.get('/api/v1/perfil', headers=h).status_code == 401
    login(api, a, nombre, NUEVA)


def test_cinco_codigos_erroneos_bloquean_el_codigo(api, empresas, correos):
    a, _, _, _ = empresas
    uid, _, nombre = cliente(a)
    solicitud(api, a, nombre)
    codigo = correos[0]['codigo']
    incorrecto = '000001' if codigo == '000000' else '000000'
    for _ in range(5):
        assert confirmar(api, a, nombre, incorrecto).status_code == 400
    fila = consulta('SELECT usado,intentos FROM password_reset_token WHERE usuario_id=%s ORDER BY id DESC LIMIT 1', (uid,), True)
    assert fila == {'usado': True, 'intentos': 5}
    assert confirmar(api, a, nombre, codigo).status_code == 400
    login(api, a, nombre)


def test_codigo_expirado_y_cuenta_inactiva_no_se_recuperan(api, empresas, correos):
    a, _, _, _ = empresas
    uid, _, nombre = cliente(a)
    respuesta = solicitud(api, a, nombre).json()
    consulta("UPDATE password_reset_token SET fecha_expiracion=CURRENT_TIMESTAMP-INTERVAL '1 minute' WHERE usuario_id=%s", (uid,))
    assert confirmar(api, a, nombre, correos[0]['codigo']).status_code == 400
    consulta('UPDATE usuario SET activo=FALSE WHERE id=%s', (uid,))
    assert solicitud(api, a, nombre).json() == respuesta
    assert len(correos) == 1


def test_consumo_concurrente_solo_una_confirmacion(empresas):
    a, _, _, _ = empresas
    uid, _, _ = cliente(a)
    codigo_hash = reset._hashear_codigo('123456')
    assert tokens.guardar_token_reset(uid, codigo_hash, 10, a['id'])
    nuevo_hash = hashear_password(NUEVA)
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(lambda _: tokens.consumir_token_reset(uid, codigo_hash, nuevo_hash, a['id']), range(2)))
    assert sorted(resultados) == [False, True]


def test_admin_saas_recuperacion_separada(api, empresas, correos):
    a, _, _, uid = empresas
    nombre = consulta('SELECT username FROM usuario WHERE id=%s', (uid,), True)['username']
    # El actor compartido puede tener un código usado por otra prueba.
    consulta('DELETE FROM password_reset_token WHERE usuario_id=%s', (uid,))
    solicitud(api, a, nombre)
    assert correos == []
    solicitud(api, None, nombre)
    assert len(correos) == 1
    assert confirmar(api, None, nombre, correos[0]['codigo']).status_code == 200
    login(api, None, nombre, NUEVA)
    # Restaurar sólo la cuenta sintética compartida para las demás fixtures.
    consulta('UPDATE usuario SET password_hash=%s WHERE id=%s', (hashear_password('Prueba-AS-local-123'), uid))


@pytest.mark.parametrize('cambio', ['password', 'identidad', 'desactivar'])
def test_login_en_curso_no_abre_sesion_despues_de_cambiar_cuenta(api, empresas, monkeypatch, cambio):
    from app.modules.autenticacion.services import sesion_service
    from app.modules.autenticacion.repositories import perfil_repository as perfiles
    a, _, _, _ = empresas
    uid, _, nombre = cliente(a)
    crear = sesion_service.crear_sesion
    def cambiar_antes_de_abrir(*args, **kwargs):
        if cambio == 'password':
            anterior = perfiles.obtener_password_hash(uid, a['id'])
            perfiles.actualizar_password_hash(uid, hashear_password(NUEVA), a['id'], anterior)
        elif cambio == 'identidad':
            perfiles.actualizar_perfil_cliente(uid, 'Cliente', 'Prueba', None, a['id'], nombre+'x', None, PASSWORD)
        else:
            perfiles.desactivar_cuenta_cliente(uid, a['id'], PASSWORD)
        return crear(*args, **kwargs)
    monkeypatch.setattr(sesion_service, 'crear_sesion', cambiar_antes_de_abrir)
    r = api.post('/api/v1/autenticacion/login', json={'identificador': nombre, 'password': PASSWORD, 'empresa_codigo': a['codigo']})
    assert r.status_code == 401, r.text
    assert consulta('SELECT count(*) n FROM sesion WHERE usuario_id=%s AND activa', (uid,), True)['n'] == 0


@pytest.mark.parametrize('campo', ['username', 'correo'])
def test_solicitud_en_curso_no_emite_codigo_para_identidad_anterior(api, empresas, monkeypatch, correos, campo):
    from app.modules.autenticacion.repositories import perfil_repository as perfiles
    a, _, _, _ = empresas
    uid, _, nombre = cliente(a)
    guardar = reset.guardar_token_reset
    def cambiar_antes_de_emitir(*args, **kwargs):
        perfiles.actualizar_perfil_cliente(uid, 'Cliente', 'Prueba', None, a['id'],
            nombre+'x' if campo == 'username' else nombre,
            nombre+'x@example.invalid' if campo == 'correo' else nombre+'@example.invalid', PASSWORD)
        return guardar(*args, **kwargs)
    monkeypatch.setattr(reset, 'guardar_token_reset', cambiar_antes_de_emitir)
    r = solicitud(api, a, nombre)
    assert r.status_code == 200, r.text
    assert r.json()['mensaje'] == reset.MENSAJE_SOLICITUD
    assert correos == []
    assert consulta('SELECT count(*) n FROM password_reset_token WHERE usuario_id=%s AND NOT usado', (uid,), True)['n'] == 0
