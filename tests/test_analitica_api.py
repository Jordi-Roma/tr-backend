import csv
import hashlib
import json

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.modules.autenticacion.dependencies.usuario_actual import obtener_usuario_actual
from app.modules.inteligencia.router.analitica_router import router
from app.modules.inteligencia.router import reporte_router
from app.modules.inteligencia.router import analitica_router
from app.modules.inteligencia.repositories import reporte_repository
from app.modules.inteligencia.services import analitica_consulta_service as servicio


@pytest.fixture
def contexto(tmp_path, monkeypatch):
    def guardar(nombre, objeto):
        ruta = tmp_path / nombre
        ruta.write_text(json.dumps(objeto), encoding="utf-8")
        return {"ruta": nombre, "sha256": hashlib.sha256(ruta.read_bytes()).hexdigest()}

    def guardar_csv(nombre, filas):
        ruta = tmp_path / nombre
        with ruta.open("w", encoding="utf-8", newline="") as f:
            escritor = csv.DictWriter(f, fieldnames=list(filas[0]))
            escritor.writeheader()
            escritor.writerows(filas)
        return {"ruta": nombre, "sha256": hashlib.sha256(ruta.read_bytes()).hexdigest()}

    meta = {"origen": "SINTETICO", "empresa_id": "SYN-E01", "dataset_id": "demo1",
            "modelo": "RandomForestRegressor", "entrenado_en": "2026-11-08T00:00:00Z"}
    predicciones = [dict(origen="SINTETICO", empresa_id="SYN-E01", sucursal_id=f"SYN-S{s}",
                        producto_id=f"P{p}", fecha_corte="2026-01-01", objetivo_hasta="2026-01-08",
                        unidades_reales="10", unidades_predichas=str(8 if s == 1 else 100),
                        referencia_semana_anterior="7") for s in (1, 2) for p in (1, 2)]
    perfil = dict(grupo=1, nombre="Grupo 1", clientes=3, proporcion=1, recencia_media_dias=2,
                  recencia_mediana_dias=2, frecuencia_media_compras=4, frecuencia_mediana_compras=4,
                  gasto_medio_centavos=5000, gasto_mediano_centavos=5000, descripcion="Perfil sintético")
    segmentos = {**meta, "modelo": "KMeans", "perfiles": [perfil], "fecha_corte": "2026-01-01",
                 "ventana_dias": 180, "clientes_sin_compras_ventana": 1, "silhouette": 0.4,
                 "ari_medio": 1, "k_elegido": 1, "clientes_analizados": 3,
                 "evaluacion": "INTERNA_SOBRE_LA_MISMA_INSTANTANEA"}
    asignaciones = [dict(origen="SINTETICO", empresa_id="SYN-E01", cliente_id=f"C{i}", grupo=1,
                        recencia_dias=2, frecuencia_compras=4, gasto_centavos=5000) for i in range(3)]
    demo = {"estado": "DISPONIBLE", "empresa_dataset": "SYN-E01", "sucursales": {"10": "SYN-S1", "20": "SYN-S2"},
            "predicciones": {"evaluacion": guardar("pred.json", meta), "filas": guardar_csv("pred.csv", predicciones)},
            "segmentos": {"evaluacion": guardar("seg.json", segmentos), "filas": guardar_csv("seg.csv", asignaciones)}}
    registro = {"version": 1, "empresas": {"stylear": {"empresa_id": 1, "demostracion": demo,
                "oficial": {"estado": "HISTORIAL_INSUFICIENTE", "fuente_datos": "AUDITORIA_RAILWAY",
                            "resumen_historial": {"ventas_completadas": 8, "password": "no-exponer"}}}}}
    ruta = tmp_path / "registro.json"
    ruta.write_text(json.dumps(registro), encoding="utf-8")
    monkeypatch.setenv("STYLEAR_ANALITICA_REGISTRO", str(ruta))
    actor = {"id": 1, "empresa_id": 1, "empresa_codigo": "stylear", "roles": ["ADMINISTRADOR"]}
    monkeypatch.setattr(servicio, "listar_sucursales", lambda eid: (
        [{"id": 10, "nombre": "Sucursal A"}, {"id": 20, "nombre": "Sucursal B"}] if eid == 1 else [{"id": 30, "nombre": "Empresa B"}]))
    monkeypatch.setattr(reporte_repository, "sucursal_encargado", lambda eid, uid: 10)
    monkeypatch.setattr(reporte_router, "exigir_funcion_empresa", lambda *a, **k: None)
    monkeypatch.setattr(analitica_router, "exigir_funcion_empresa", lambda *a, **k: None)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[obtener_usuario_actual] = lambda: actor
    with TestClient(app) as api:
        yield api, actor, ruta, registro, app


BASE = "/api/v1/reportes/analitica"


def test_oficial_por_defecto_no_sustituye_historial_con_demo_y_no_expone_secretos(contexto):
    api, _, ruta, _, _ = contexto
    r = api.get(BASE + "/predicciones")
    assert r.status_code == 200 and r.json()["estado"] == "HISTORIAL_INSUFICIENTE"
    assert r.json()["filas"] == [] and r.json()["metricas"] is None
    assert r.headers["cache-control"] == "no-store"
    r = api.get(BASE + "/estado")
    assert "no-exponer" not in r.text and "password" not in r.text and str(ruta.parent) not in r.text
    assert r.json()["fuentes"][0]["resumen_historial"] == {"ventas_completadas": 8}


def test_predicciones_paginacion_y_metricas_corresponden_a_todos_los_filtros(contexto):
    api, *_ = contexto
    r = api.get(BASE + "/predicciones", params={"origen": "DEMOSTRACION", "sucursal_id": 10, "tamano": 1})
    assert r.status_code == 200, r.text
    x = r.json()
    assert len(x["filas"]) == 1 and x["total_filas"] == 2
    assert x["metricas"]["muestras"] == 2 and x["metricas"]["mae"] == 2
    assert x["serie"][0]["unidades_reales"] == 20
    assert x["tipo_resultado"] == "EVALUACION_HISTORICA"
    q = api.get(BASE + "/metricas", params={"origen": "DEMOSTRACION", "sucursal_id": 10}).json()
    assert q["metricas"] == x["metricas"]
    vacio = api.get(BASE + "/predicciones", params={"origen": "DEMOSTRACION", "corte_desde": "2026-02-01"}).json()
    assert vacio["sin_datos"] and vacio["metricas"] is None


def test_encargado_no_ve_otra_sucursal_estadisticas_globales_o_segmentos(contexto):
    api, actor, *_ = contexto
    actor["roles"] = ["ENCARGADO_SUCURSAL"]
    x = api.get(BASE + "/predicciones?origen=DEMOSTRACION").json()
    assert x["sucursales_efectivas"] == [10] and x["metricas"]["mae"] == 2
    assert {r["sucursal_id"] for r in x["filas"]} == {10}
    assert api.get(BASE + "/predicciones?origen=DEMOSTRACION&sucursal_id=20").status_code == 403
    assert api.get(BASE + "/segmentos?origen=DEMOSTRACION").status_code == 403
    e = api.get(BASE + "/estado").json()
    assert not e["segmentacion_permitida"]
    assert all("resumen_historial" not in f for f in e["fuentes"])


@pytest.mark.parametrize("rol", ["CLIENTE", "CAJERO", "PERSONAL_VENTAS", "PROVEEDOR", "ADMIN_SAAS"])
def test_roles_no_autorizados(contexto, rol):
    api, actor, *_ = contexto
    actor["roles"] = [rol]
    for endpoint in ("estado", "predicciones", "segmentos", "metricas"):
        assert api.get(BASE + "/" + endpoint).status_code == 403


def test_empresa_no_registrada_no_hereda_demostracion_de_otra(contexto):
    api, actor, *_ = contexto
    actor.update(empresa_codigo="otra", empresa_id=2)
    x = api.get(BASE + "/predicciones?origen=DEMOSTRACION").json()
    assert x["estado"] == "NO_CONFIGURADO" and x["filas"] == []
    assert api.get(BASE + "/predicciones?sucursal_id=10").status_code == 404


def test_segmentacion_solo_admin_filtra_y_pagina_con_metricas_internas(contexto):
    api, *_ = contexto
    r = api.get(BASE + "/segmentos?origen=DEMOSTRACION&grupo=1&tamano=1")
    assert r.status_code == 200, r.text
    x = r.json()
    assert x["total_filas"] == 3 and len(x["filas"]) == 1
    assert x["perfiles"][0]["clientes"] == 3 and x["metricas"]["silhouette"] == 0.4
    assert "no es porcentaje" in x["advertencia"]


@pytest.mark.parametrize("query", ["empresa_id=2", "origen=SINTETICO", "tamano=101", "sucursal_id=-1",
                                    "corte_desde=2026-02-01&corte_hasta=2026-01-01", "producto_id=../../secret"])
def test_rechaza_parametros_no_permitidos(contexto, query):
    assert contexto[0].get(BASE + "/predicciones?" + query).status_code == 422


def test_archivo_alterado_y_ruta_fuera_del_registro_fallan_sin_exponer_contenido(contexto, tmp_path):
    api, _, ruta, registro, _ = contexto
    (ruta.parent / "pred.csv").write_text("contenido-corrupto", encoding="utf-8")
    r = api.get(BASE + "/predicciones?origen=DEMOSTRACION")
    assert r.status_code == 503 and "contenido-corrupto" not in r.text and str(tmp_path) not in r.text
    registro["empresas"]["stylear"]["demostracion"]["predicciones"]["evaluacion"]["ruta"] = "../fuera.json"
    ruta.write_text(json.dumps(registro), encoding="utf-8")
    assert api.get(BASE + "/predicciones?origen=DEMOSTRACION").status_code == 503


def test_rechaza_metadatos_de_otra_empresa_aunque_registro_tenga_hash_valido(contexto):
    api, _, ruta, registro, _ = contexto
    p = ruta.parent / "pred.json"
    m = json.loads(p.read_text(encoding="utf-8"))
    m["empresa_id"] = "SYN-E02"
    p.write_text(json.dumps(m), encoding="utf-8")
    registro["empresas"]["stylear"]["demostracion"]["predicciones"]["evaluacion"]["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
    ruta.write_text(json.dumps(registro), encoding="utf-8")
    assert api.get(BASE + "/predicciones?origen=DEMOSTRACION").status_code == 503


def test_autenticacion_y_plan_se_mantienen(contexto, monkeypatch):
    api, _, _, _, app = contexto
    def prohibir(*a, **k):
        raise HTTPException(403, "Función no incluida en el plan.")
    monkeypatch.setattr(reporte_router, "exigir_funcion_empresa", prohibir)
    assert api.get(BASE + "/estado").status_code == 403
    app.dependency_overrides.clear()
    assert api.get(BASE + "/estado").status_code in (401, 403)


def test_codigo_igual_con_id_de_empresa_distinto_no_reutiliza_registro(contexto):
    api, actor, *_ = contexto
    actor["empresa_id"] = 2
    assert api.get(BASE + "/estado").status_code == 503


def test_sucursal_sin_mapeo_no_anuncia_predicciones_de_otra(contexto):
    api, actor, ruta, registro, _ = contexto
    actor["roles"] = ["ENCARGADO_SUCURSAL"]
    del registro["empresas"]["stylear"]["demostracion"]["sucursales"]["10"]
    ruta.write_text(json.dumps(registro), encoding="utf-8")
    demo = api.get(BASE + "/estado").json()["fuentes"][1]
    assert not demo["predicciones_disponibles"]
    r = api.get(BASE + "/predicciones?origen=DEMOSTRACION").json()
    assert not r["filas"] and r["metricas"] is None


def test_registro_demo_verifica_origen_preserva_otras_empresas_y_rechaza_sobrescritura(contexto):
    from scripts.registrar_analitica_demo import registrar
    _, _, ruta, _, _ = contexto
    pred, seg = ruta.parent / "pred", ruta.parent / "seg"
    pred.mkdir()
    seg.mkdir()
    for origen, destino in (("pred.json", pred / "evaluacion.json"), ("pred.csv", pred / "predicciones_prueba.csv"),
                            ("seg.json", seg / "evaluacion.json"), ("seg.csv", seg / "asignaciones.csv")):
        destino.write_bytes((ruta.parent / origen).read_bytes())
    registrar(ruta, "otra", 2, "SYN-E01", {"30": "SYN-S1"}, pred, seg)
    original = ruta.read_bytes()
    assert set(json.loads(original)["empresas"]) == {"stylear", "otra"}
    with pytest.raises(FileExistsError):
        registrar(ruta, "otra", 2, "SYN-E01", {"30": "SYN-S1"}, pred, seg)
    assert ruta.read_bytes() == original
    with pytest.raises(ValueError, match="empresa sintética"):
        registrar(ruta, "tercera", 3, "SYN-E02", {"40": "SYN-S1"}, pred, seg)
    assert ruta.read_bytes() == original


def test_exporta_todo_el_filtro_excel_y_pdf_con_origen_y_ceros(contexto):
    from io import BytesIO
    from openpyxl import load_workbook
    from pypdf import PdfReader
    api, *_ = contexto
    body = {'tipo': 'PREDICCIONES', 'origen': 'DEMOSTRACION', 'sucursal_id': 10}
    x = api.post(BASE + '/exportar/excel', json=body)
    assert x.status_code == 200 and x.headers['cache-control'] == 'no-store'
    wb = load_workbook(BytesIO(x.content))
    assert wb['Datos'].max_row == 3  # Dos filas, no una página elegida por el cliente.
    assert 'DEMOSTRACIÓN SINTÉTICA' in str(list(wb['Resumen'].values))
    assert len(wb['Gráfico']._charts) == 1
    p = api.post(BASE + '/exportar/pdf', json=body)
    assert p.status_code == 200
    lector = PdfReader(BytesIO(p.content))
    texto = '\n'.join(p.extract_text() for p in lector.pages)
    assert 'DEMOSTRACION SINTETICA' in texto and 'Sucursal B' not in texto
    assert 'Detalle completo del filtro: 2 filas' in texto
    for pagina in lector.pages: assert 'DEMOSTRACION SINTETICA' in pagina.extract_text()
    oficial = api.post(BASE + '/exportar/pdf', json={'tipo': 'PREDICCIONES'})
    assert oficial.status_code == 200
    texto = '\n'.join(p.extract_text() for p in PdfReader(BytesIO(oficial.content)).pages)
    assert 'HISTORIAL_INSUFICIENTE' in texto and 'SINTETICA' not in texto


def test_exportacion_segmentos_reutiliza_roles_y_no_admite_paginacion(contexto):
    api, actor, *_ = contexto
    assert api.post(BASE + '/exportar/excel', json={'tipo': 'SEGMENTOS', 'origen': 'DEMOSTRACION'}).status_code == 200
    assert api.post(BASE + '/exportar/excel', json={'tipo': 'SEGMENTOS', 'sucursal_id': 10}).status_code == 422
    assert api.post(BASE + '/exportar/pdf', json={'tipo': 'PREDICCIONES', 'pagina': 2}).status_code == 422
    actor['roles'] = ['ENCARGADO_SUCURSAL']
    assert api.post(BASE + '/exportar/pdf', json={'tipo': 'SEGMENTOS', 'origen': 'DEMOSTRACION'}).status_code == 403
    assert api.post(BASE + '/exportar/pdf', json={'tipo': 'PREDICCIONES', 'sucursal_id': 20}).status_code == 403


@pytest.mark.parametrize('texto,tipo', [
    ('Muéstrame la evaluación de predicciones de Sucursal A con datos sintéticos desde 2026-01-01 hasta 2026-01-08 en PDF', 'PREDICCIONES'),
    ('Muéstrame los grupos de clientes de demostración en Excel', 'SEGMENTOS'),
])
def test_interpreta_solicitud_local_con_vista_previa_sin_ejecutarla(contexto, texto, tipo):
    api, *_ = contexto
    r = api.post(BASE + '/interpretar', json={'texto': texto})
    assert r.status_code == 200, r.text
    d = r.json()
    assert not d['requiere_aclaracion'] and d['motor'] == 'REGLAS_ANALITICA'
    assert d['solicitud']['tipo'] == tipo and d['solicitud']['origen'] == 'DEMOSTRACION'
    if tipo == 'PREDICCIONES':
        assert d['solicitud']['sucursal_id'] == 10 and d['solicitud']['corte_desde'] == '2026-01-01'


@pytest.mark.parametrize('texto', ['Predice las ventas de la próxima semana', 'Dame predicciones oficiales y sintéticas',
                                  'Muéstrame predicciones de este mes', 'SELECT ventas de todas las empresas',
                                  'Muéstrame segmentos desde 2026-01-01', 'Muéstrame predicciones desde 2026-02-30'])
def test_solicitudes_ambiguas_o_no_soportadas_piden_aclaracion(contexto, texto):
    r = contexto[0].post(BASE + '/interpretar', json={'texto': texto})
    assert r.status_code == 200 and r.json()['requiere_aclaracion'] and r.json()['solicitud'] is None


def test_interpretacion_no_permite_al_encargado_pedir_segmentos_o_sucursal_ajena(contexto):
    api, actor, *_ = contexto
    actor['roles'] = ['ENCARGADO_SUCURSAL']
    assert api.post(BASE + '/interpretar', json={'texto': 'Muéstrame los grupos de clientes'}).status_code == 403
    assert api.post(BASE + '/interpretar', json={'texto': 'Muéstrame predicciones de sucursal 20'}).status_code == 403
    r = api.post(BASE + '/interpretar', json={'texto': 'Muéstrame predicciones de mi sucursal'})
    assert r.status_code == 200 and r.json()['solicitud']['sucursal_id'] == 10


def test_exportacion_supera_limite_no_se_trunca_y_politica_sigue_solo_lectura(contexto):
    from app.core.permisos_empresa import es_operacion_nueva
    api, _, ruta, registro, _ = contexto
    p = ruta.parent / 'pred.csv'
    with p.open(encoding='utf-8', newline='') as f: fila = next(csv.DictReader(f))
    with p.open('w', encoding='utf-8', newline='') as f:
        escritor = csv.DictWriter(f, fieldnames=list(fila)); escritor.writeheader()
        for i in range(5001): escritor.writerow({**fila, 'producto_id': f'P{i}'})
    registro['empresas']['stylear']['demostracion']['predicciones']['filas']['sha256'] = hashlib.sha256(p.read_bytes()).hexdigest()
    ruta.write_text(json.dumps(registro), encoding='utf-8')
    r = api.post(BASE + '/exportar/pdf', json={'tipo': 'PREDICCIONES', 'origen': 'DEMOSTRACION'})
    assert r.status_code == 422 and '5000' in r.json()['detail']
    for final in ('interpretar', 'exportar/pdf', 'exportar/excel'):
        assert not es_operacion_nueva('POST', BASE + '/' + final)
    assert es_operacion_nueva('POST', BASE + '/entrenar')


def test_excel_no_interpreta_textos_como_formulas_y_pdf_preserva_cero():
    from io import BytesIO
    from openpyxl import load_workbook
    from pypdf import PdfReader
    from app.modules.inteligencia.exports.analitica_export import crear_excel_ml, crear_pdf_ml
    r = {'tipo': 'PREDICCIONES', 'titulo': 'Ensayo', 'empresa': '=1+1', 'generado_en': '2026-11-08', 'filtros': {},
         'datos': {'origen': 'DEMOSTRACION', 'estado': 'DISPONIBLE', 'advertencia': 'Ensayo sintético', 'serie': [],
                   'total_filas': 1, 'metricas': {'mae': 0}, 'filas': [{'fecha_corte': '2026-01-01', 'objetivo_hasta': '2026-01-08',
                   'sucursal': '  =1+1', 'producto_id': '@SUM(A1)', 'unidades_reales': 0, 'unidades_predichas': 0, 'referencia_semana_anterior': 0}]}}
    wb = load_workbook(BytesIO(crear_excel_ml(r)))
    assert all(c.data_type != 'f' for sheet in wb for fila in sheet for c in fila)
    assert wb['Datos'].cell(2,5).value == 0
    pdf = PdfReader(BytesIO(crear_pdf_ml(r)))
    assert '0' in pdf.pages[-1].extract_text()


def test_interpretacion_voz_y_exportacion_respetan_funciones_del_plan(contexto, monkeypatch):
    api, *_ = contexto
    funciones = []
    def exigir(eid, clave):
        funciones.append(clave)
        if clave in {'reportes_voz', 'reportes_excel'}: raise HTTPException(403, 'Función no incluida.')
    monkeypatch.setattr(analitica_router, 'exigir_funcion_empresa', exigir)
    assert api.post(BASE + '/interpretar', json={'texto': 'Muéstrame predicciones', 'origen_entrada': 'VOZ'}).status_code == 403
    assert 'reportes_interpretacion' in funciones and 'reportes_voz' in funciones
    assert api.post(BASE + '/exportar/excel', json={'tipo': 'PREDICCIONES'}).status_code == 403
