"""Regresiones Unicode reales sobre el destino local desechable validado."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unicodedata import normalize
import json

import psycopg2
from psycopg2 import sql
from psycopg2.errors import UniqueViolation
import pytest
from fastapi.testclient import TestClient

from test_multitenant_integration import actor, empresas, consulta, DSN
from test_cuenta_integration import login
from app.main import app


VERSION = '2026_10_27_cu09_unicode_01'
MIGRACION = Path(__file__).resolve().parents[1] / 'database/migracion_cu09_unicode_01.sql'
RUTAS = ['categorias', 'tallas', 'colores', 'marcas', 'temporadas', 'colecciones']
TABLAS = ['categoria', 'talla', 'color', 'marca', 'temporada', 'coleccion']


@pytest.fixture
def api():
    with TestClient(app) as client:
        yield client


def extras(tabla, empresa_id):
    if tabla == 'talla':
        return {'tipo_prenda': 'SUPERIOR'}
    if tabla == 'temporada':
        return {'anio': 2026}
    if tabla == 'coleccion':
        temporada = consulta(
            'INSERT INTO temporada(empresa_id,nombre,anio) VALUES(%s,%s,2026) RETURNING id',
            (empresa_id, 'Temporada de regresión'), True,
        )
        return {'temporada_id': temporada['id']}
    return {}


def insertar_sql(cur, tabla, empresa_id, nombre, datos):
    campos = ['empresa_id', 'nombre', *datos]
    cur.execute(sql.SQL('INSERT INTO public.{} ({}) VALUES ({}) RETURNING id').format(
        sql.Identifier(tabla), sql.SQL(',').join(map(sql.Identifier, campos)),
        sql.SQL(',').join(sql.Placeholder() for _ in campos),
    ), [empresa_id, nombre, *datos.values()])
    return cur.fetchone()[0]


def test_clave_unicode_conserva_tildes_y_no_hereda_collation():
    for texto, esperado in [
        (' ÚNICA ', 'única'), ('U\u0301NICA', 'única'),
        ('NIÑOS', 'niños'), ('PINGÜINO', 'pingüino'), ('I', 'i'),
    ]:
        fila = consulta('''SELECT
            public.normalizar_nombre_catalogo(%s COLLATE "C") AS desde_c,
            public.normalizar_nombre_catalogo(%s COLLATE "und-x-icu") AS desde_icu''',
            (texto, texto), True)
        assert fila == {'desde_c': esperado, 'desde_icu': esperado}
    fila = consulta('''SELECT
        public.normalizar_nombre_catalogo('Única') COLLATE "C" <>
        public.normalizar_nombre_catalogo('Unica') COLLATE "C" AS conserva_tilde,
        public.normalizar_nombre_catalogo('Ñ') COLLATE "C" <>
        public.normalizar_nombre_catalogo('N') COLLATE "C" AS conserva_enie''', una=True)
    assert fila == {'conserva_tilde': True, 'conserva_enie': True}


@pytest.mark.parametrize('ruta,tabla', zip(RUTAS, TABLAS))
def test_api_crear_editar_inactivos_y_empresa_con_nombre_unicode(api, empresas, ruta, tabla):
    a, b, _, _ = empresas
    ha, hb = login(api, a, a['codigo']), login(api, b, b['codigo'])
    datos = extras(tabla, a['id'])
    url = '/api/v1/' + ruta
    creada = api.post(url, headers=ha, json={'nombre': 'ÚNICA', **datos})
    assert creada.status_code == 200, creada.text
    registro = creada.json()
    assert registro['nombre'] == 'ÚNICA'  # No se altera el nombre presentado.
    for nombre in [' única ', normalize('NFD', 'única')]:
        assert api.post(url, headers=ha, json={'nombre': nombre, **datos}).status_code == 409
    otra = api.post(url, headers=ha, json={'nombre': 'Otro nombre', **datos}).json()
    assert api.put(f'{url}/{otra["id"]}', headers=ha,
                   json={'nombre': normalize('NFD', 'Única'), **datos}).status_code == 409
    assert api.get(f'{url}/{otra["id"]}', headers=ha).json()['nombre'] == 'Otro nombre'
    # El acento sigue siendo significativo y el alcance continúa por empresa.
    assert api.post(url, headers=ha, json={'nombre': 'Unica', **datos}).status_code == 200
    assert api.post(url, headers=hb, json={'nombre': 'ÚNICA', **extras(tabla, b['id'])}).status_code == 200
    assert api.patch(f'{url}/{registro["id"]}/desactivar', headers=ha).status_code == 200
    assert api.post(url, headers=ha, json={'nombre': 'única', **datos}).status_code == 409


@pytest.mark.parametrize('tabla', TABLAS)
def test_indices_rechazan_insert_directo_concurrente_unicode(empresas, tabla):
    a, _, _, _ = empresas
    datos = extras(tabla, a['id'])
    barrera = Barrier(2)

    def crear(nombre):
        try:
            with psycopg2.connect(DSN) as conn:
                with conn.cursor() as cur:
                    barrera.wait(timeout=15)
                    insertar_sql(cur, tabla, a['id'], nombre, datos)
            return 200
        except UniqueViolation:
            return 409

    with ThreadPoolExecutor(max_workers=2) as pool:
        respuestas = list(pool.map(crear, [' ÚNICA ', normalize('NFD', 'única')]))
    assert sorted(respuestas) == [200, 409]


def test_identidad_por_tipo_anio_y_temporada_se_conserva(api, empresas):
    a, _, _, _ = empresas
    h = login(api, a, a['codigo'])
    for tipo in ['SUPERIOR', 'INFERIOR']:
        assert api.post('/api/v1/tallas', headers=h,
                        json={'nombre': 'Única', 'tipo_prenda': tipo}).status_code == 200
    temporadas = []
    for anio in [2026, 2027]:
        r = api.post('/api/v1/temporadas', headers=h, json={'nombre': 'VERÁNO', 'anio': anio})
        assert r.status_code == 200, r.text
        temporadas.append(r.json()['id'])
    for temporada in temporadas:
        assert api.post('/api/v1/colecciones', headers=h,
                        json={'nombre': 'CÁPSULA', 'temporada_id': temporada}).status_code == 200


def test_consultas_por_nombre_comparten_normalizacion_y_aislamiento(empresas):
    from app.modules.administracion.repositories import catalogo_repository as catalogo
    from app.modules.administracion.repositories import coleccion_repository as colecciones
    from app.modules.administracion.repositories import temporada_repository as temporadas

    a, b, _, _ = empresas
    nombre = normalize('NFD', ' única ')
    for tabla, buscar in [
        ('categoria', lambda eid, d: catalogo.obtener_categoria_por_nombre(nombre, empresa_id=eid)),
        ('talla', lambda eid, d: catalogo.obtener_talla_por_nombre_y_tipo(nombre, 'SUPERIOR', empresa_id=eid)),
        ('color', lambda eid, d: catalogo.obtener_color_por_nombre(nombre, empresa_id=eid)),
        ('marca', lambda eid, d: catalogo.obtener_marca_por_nombre(nombre, empresa_id=eid)),
        ('temporada', lambda eid, d: temporadas.obtener_temporada_por_nombre_anio(nombre, 2026, eid)),
        ('coleccion', lambda eid, d: colecciones.obtener_coleccion_por_temporada_nombre(d['temporada_id'], nombre, eid)),
    ]:
        datos = extras(tabla, a['id'])
        with psycopg2.connect(DSN) as conn:
            with conn.cursor() as cur:
                registro = insertar_sql(cur, tabla, a['id'], 'ÚNICA', datos)
        assert buscar(a['id'], datos)['id'] == registro
        assert buscar(b['id'], datos) is None
    assert catalogo.obtener_talla_por_nombre(nombre, empresa_id=a['id']) is not None


def preparar_esquema_anterior(cur):
    # Se hace exclusivamente dentro de una transacción del test, revertida al
    # terminar. CASCADE retira los seis índices de la versión nueva, no tablas.
    cur.execute('DROP FUNCTION public.normalizar_nombre_catalogo(text) CASCADE')
    cur.execute('DROP COLLATION public.stylear_catalogo_unicode')
    # Reconstruir los cinco índices que realmente tenía la versión anterior.
    # Colección sólo tenía su restricción exacta (temporada_id, nombre).
    for tabla, indice, campo in [
        ('categoria', 'uq_categoria_empresa_nombre', ''),
        ('talla', 'uq_talla_empresa_nombre_tipo', ', tipo_prenda'),
        ('color', 'uq_color_empresa_nombre', ''),
        ('marca', 'uq_marca_empresa_nombre', ''),
        ('temporada', 'uq_temporada_empresa_nombre_anio', ', anio'),
    ]:
        cur.execute(sql.SQL('CREATE UNIQUE INDEX {} ON public.{} (empresa_id, lower(nombre){})').format(
            sql.Identifier(indice), sql.Identifier(tabla), sql.SQL(campo),
        ))


@pytest.mark.parametrize('tabla', TABLAS)
def test_migracion_con_duplicados_revierte_sin_borrar_datos(empresas, tabla):
    a, _, _, _ = empresas
    datos = extras(tabla, a['id'])
    conn = psycopg2.connect(DSN)
    try:
        with conn.cursor() as cur:
            preparar_esquema_anterior(cur)
            ids = [insertar_sql(cur, tabla, a['id'], n, datos)
                   for n in ['Única', normalize('NFD', 'única')]]
            with pytest.raises(UniqueViolation) as error:
                cur.execute(MIGRACION.read_text(encoding='utf-8'))
            detalle = json.loads(error.value.diag.message_detail)
            assert detalle['tabla'] == tabla
            assert detalle['grupos'][0]['ids'] == ids
    finally:
        conn.rollback()
        conn.close()
    # La protección y la versión anteriores al ensayo siguen intactas.
    assert consulta('SELECT to_regprocedure(%s) IS NOT NULL AS existe',
                    ('public.normalizar_nombre_catalogo(text)',), True)['existe']
    assert consulta('SELECT count(*) AS n FROM schema_migrations WHERE version=%s',
                    (VERSION,), True)['n'] == 1


def test_migracion_valida_preserva_ids_nombres_y_referencias(empresas):
    a, _, _, _ = empresas
    conn = psycopg2.connect(DSN)
    try:
        with conn.cursor() as cur:
            preparar_esquema_anterior(cur)
            categoria = insertar_sql(cur, 'categoria', a['id'], 'Árbol original', {})
            cur.execute('INSERT INTO producto(empresa_id,categoria_id,nombre) VALUES(%s,%s,%s) RETURNING id',
                        (a['id'], categoria, 'Producto conservado'))
            producto = cur.fetchone()[0]
            cur.execute(MIGRACION.read_text(encoding='utf-8'))
            cur.execute('SELECT c.id,c.nombre,p.categoria_id FROM categoria c '
                        'JOIN producto p ON p.categoria_id=c.id WHERE p.id=%s', (producto,))
            assert cur.fetchone() == (categoria, 'Árbol original', categoria)
    finally:
        conn.rollback()
        conn.close()


def test_inicializador_omite_migracion_ya_aplicada():
    import init_db
    antes = consulta('SELECT oid FROM pg_proc WHERE oid=%s::regprocedure',
                     ('public.normalizar_nombre_catalogo(text)',), True)
    conn = psycopg2.connect(DSN)
    try:
        with conn.cursor() as cur:
            init_db._ejecutar_versionada(cur, conn, VERSION, 'database/migracion_cu09_unicode_01.sql')
    finally:
        conn.close()
    assert consulta('SELECT oid FROM pg_proc WHERE oid=%s::regprocedure',
                    ('public.normalizar_nombre_catalogo(text)',), True) == antes
    assert consulta('SELECT count(*) AS n FROM schema_migrations WHERE version=%s',
                    (VERSION,), True)['n'] == 1
