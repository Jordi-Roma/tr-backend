"""Ensayo optativo: datos sintéticos locales y objetos R2 creados por esta ejecución."""
import os
from uuid import UUID

import psycopg2
import pytest

if os.getenv('STYLEAR_TEST_R2_REAL') != '1':
    pytest.skip('R2 real requiere activación explícita.', allow_module_level=True)

from test_multitenant_integration import actor, empresas, consulta, mercaderia, cliente
from app.modules.administracion.services import respaldo_service as respaldos
from app.modules.administracion.repositories import empresa_saas_repository as saas


@pytest.fixture
def almacenamiento_real(monkeypatch, tmp_path):
    real, bucket, cifrador, dias = respaldos.configuracion()
    assert bucket == 'stylear-respaldos-local'
    creados = set()

    class ObjetosDelEnsayo:
        def put_object(self, **args):
            # Registrar antes de transmitir permite limpiar incluso una respuesta perdida.
            assert args['Bucket'] == bucket
            creados.add(args['Key'])
            return real.put_object(**args)

        def get_object(self, **args):
            assert args['Bucket'] == bucket and args['Key'] in creados
            return real.get_object(**args)

        def delete_object(self, **args):
            assert args['Bucket'] == bucket and args['Key'] in creados
            return real.delete_object(**args)

    monkeypatch.setattr(respaldos, 'configuracion', lambda: (ObjetosDelEnsayo(), bucket, cifrador, dias))
    static = tmp_path / 'static'
    static.mkdir()
    monkeypatch.setattr(respaldos, 'STATIC', static)
    try:
        yield static
    finally:
        fallidos = []
        for key in creados:
            try:
                real.delete_object(Bucket=bucket, Key=key)
            except Exception:
                fallidos.append(key)
        assert not fallidos, f'Objetos sintéticos pendientes de limpieza: {fallidos}'


def test_empresa_r2_recupera_datos_archivos_y_aislamiento(empresas, almacenamiento_real):
    a, b, _, saas_id = empresas
    mercaderia(a)
    mercaderia(b)
    cliente(a)
    cliente(b)
    foto = almacenamiento_real / 'cu25-ensayo.jpg'
    foto.write_bytes(b'imagen sintetica CU25')
    consulta("INSERT INTO imagen_producto(producto_id,url,empresa_id) SELECT id,'/static/cu25-ensayo.jpg',empresa_id FROM producto WHERE empresa_id=%s", (a['id'],))
    antes_b = consulta('SELECT to_jsonb(p) AS fila FROM producto p WHERE empresa_id=%s ORDER BY id', (b['id'],))
    copia = respaldos.crear_respaldo(a['admin_usuario_id'], a['id'])
    rid = UUID(str(copia['id']))
    previa = respaldos.previsualizar_restauracion(rid, saas_id, a['id'])
    # Simula una eliminación válida: el estado actual no deja referencias rotas.
    consulta('DELETE FROM imagen_producto WHERE empresa_id=%s', (a['id'],))
    foto.unlink()
    consulta("UPDATE producto SET nombre='CAMBIADO EN ENSAYO' WHERE empresa_id=%s", (a['id'],))
    saas.cambiar_estado_empresa(a['id'], 'SUSPENDIDA', saas_id)
    assert respaldos.restaurar_respaldo(rid, saas_id, previa['confirmacion'], a['id'])['estado'] == 'RESTAURADO'
    assert consulta('SELECT nombre FROM producto WHERE empresa_id=%s', (a['id'],), True)['nombre'] == 'Prenda'
    assert foto.read_bytes() == b'imagen sintetica CU25'
    assert consulta('SELECT to_jsonb(p) AS fila FROM producto p WHERE empresa_id=%s ORDER BY id', (b['id'],)) == antes_b
    assert consulta("SELECT count(*) AS n FROM respaldo WHERE empresa_id=%s AND origen='PRE_RESTAURACION'", (a['id'],), True)['n'] == 1
    respaldos.eliminar_respaldo(rid, saas_id, a['id'])
    assert consulta('SELECT estado FROM respaldo WHERE id=%s', (str(rid),), True)['estado'] == 'ELIMINADO'


def test_global_r2_restaura_dump_solo_en_destino_vacio(empresas, almacenamiento_real, monkeypatch, tmp_path):
    _, _, _, saas_id = empresas
    destino = os.environ['STYLEAR_TEST_R2_RESTORE_URL']
    from psycopg2.extensions import parse_dsn
    params = parse_dsn(destino)
    assert params.get('host') in {'localhost', '127.0.0.1'}
    assert params.get('dbname', '').startswith('stylear_test_r2_destino_')
    monkeypatch.setenv('STYLEAR_RESTORE_DATABASE_URL', destino)
    monkeypatch.setenv('STYLEAR_RESTORE_ASSETS_DIR', str(tmp_path / 'restaurados'))
    copia = respaldos.crear_respaldo(saas_id)
    rid = UUID(str(copia['id']))
    previa = respaldos.previsualizar_restauracion(rid, saas_id)
    assert respaldos.restaurar_respaldo(rid, saas_id, previa['confirmacion'])['destino'] == 'ENSAYO'
    with psycopg2.connect(destino) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT count(*) FROM empresa')
            assert cur.fetchone()[0] == consulta('SELECT count(*) AS n FROM empresa', una=True)['n']
            cur.execute('SELECT count(*) FROM sesion WHERE activa')
            assert cur.fetchone()[0] == 0
            cur.execute('SELECT count(*) FROM dispositivo_push WHERE activo')
            assert cur.fetchone()[0] == 0
    respaldos.eliminar_respaldo(rid, saas_id)
