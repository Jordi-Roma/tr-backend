import csv
import hashlib
import json
import shutil

import pytest

pytest.importorskip("sklearn", reason="Requiere requirements-ml.txt")
import joblib
import numpy as np

from app.modules.inteligencia.services.analitica_datos_service import ConfiguracionDatos, generar_dataset
from app.modules.inteligencia.services.analitica_segmentacion_service import (
    VARIABLES_RFM, cargar_perfiles, entrenar_segmentacion,
)


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    ruta = tmp_path_factory.mktemp("rfm") / "datos"
    generar_dataset(ruta, ConfiguracionDatos(dias=210, empresas=2, sucursales=1, productos=4, clientes=45))
    return ruta


@pytest.fixture
def datos(base, tmp_path):
    ruta = tmp_path / "datos"
    shutil.copytree(base, ruta)
    return ruta


def modificar_perfiles(datos, accion):
    archivo = datos / "clientes_rfm.csv"
    with archivo.open(encoding="utf-8", newline="") as entrada:
        lector = csv.DictReader(entrada)
        campos, filas = lector.fieldnames, list(lector)
    accion(filas)
    with archivo.open("w", encoding="utf-8", newline="") as salida:
        escritor = csv.DictWriter(salida, fieldnames=campos, lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(filas)
    p = datos / "manifiesto.json"
    m = json.loads(p.read_text(encoding="utf-8"))
    m["archivos"][archivo.name]["sha256"] = hashlib.sha256(archivo.read_bytes()).hexdigest()
    p.write_text(json.dumps(m), encoding="utf-8")


def test_modelo_evaluacion_perfiles_y_asignaciones_solo_empresa_solicitada(base, tmp_path):
    salida = tmp_path / "modelo"
    reporte = entrenar_segmentacion(base, "SYN-E01", salida)
    assert reporte["estado"] == "DEMOSTRACION_SINTETICA" and reporte["origen"] == "SINTETICO"
    elegibles = [r for r in reporte["candidatos"] if r["elegible"]]
    assert reporte["k_elegido"] == max(elegibles, key=lambda r: r["silhouette"])["k"]
    assert -1 <= reporte["silhouette"] <= 1
    assert -1 <= reporte["ari_medio"] <= 1
    assert reporte["evaluacion"] == "INTERNA_SOBRE_LA_MISMA_INSTANTANEA"
    assert len(reporte["estabilidad_semillas"]) == 2
    assert sum(p["clientes"] for p in reporte["perfiles"]) == reporte["clientes_analizados"]
    assert all(p["clientes"] >= 3 for p in reporte["perfiles"])
    assert sum(p["proporcion"] for p in reporte["perfiles"]) == pytest.approx(1)
    assert reporte["clientes_analizados"] + reporte["clientes_sin_compras_ventana"] == 45
    assert hashlib.sha256((salida / "modelo.joblib").read_bytes()).hexdigest() == reporte["sha256_modelo"]
    modelo = joblib.load(salida / "modelo.joblib")  # Artefacto propio de esta prueba.
    _, filas, _ = cargar_perfiles(base, "SYN-E01")
    x = np.array([[r[c] for c in VARIABLES_RFM] for r in filas], dtype=float)
    # Ni los IDs ni perfiles de otra empresa participan del ajuste del escalador.
    assert modelo.n_features_in_ == 3
    assert np.allclose(modelo["escala"].mean_, np.log1p(x).mean(axis=0))
    with (salida / "asignaciones.csv").open(encoding="utf-8", newline="") as archivo:
        asignaciones = list(csv.DictReader(archivo))
    assert {r["empresa_id"] for r in asignaciones} == {"SYN-E01"}
    esperadas = [reporte["mapa_etiquetas"][str(int(e))] for e in modelo.predict(x)]
    assert [int(r["grupo"]) for r in asignaciones] == esperadas
    for perfil in reporte["perfiles"]:
        clientes = [r for r in asignaciones if int(r["grupo"]) == perfil["grupo"]]
        assert perfil["gasto_medio_centavos"] == pytest.approx(sum(int(r["gasto_centavos"]) for r in clientes) / len(clientes))


def test_reproducibilidad_sin_sobrescribir_artefactos(base, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    ra = entrenar_segmentacion(base, "SYN-E01", a)
    rb = entrenar_segmentacion(base, "SYN-E01", b)
    for campo in ("silhouette", "k_elegido", "perfiles", "candidatos", "estabilidad_semillas"):
        assert ra[campo] == rb[campo]
    assert (a / "asignaciones.csv").read_bytes() == (b / "asignaciones.csv").read_bytes()
    with pytest.raises(FileExistsError):
        entrenar_segmentacion(base, "SYN-E01", a)


def test_empresa_sin_historial_y_archivo_alterado(datos, tmp_path):
    with pytest.raises(ValueError, match="Historial insuficiente"):
        entrenar_segmentacion(datos, "NO-EXISTE", tmp_path / "modelo")
    with (datos / "clientes_rfm.csv").open("a", encoding="utf-8") as archivo:
        archivo.write("\n")
    with pytest.raises(ValueError, match="hash"):
        entrenar_segmentacion(datos, "SYN-E01", tmp_path / "modelo")
    assert not (tmp_path / "modelo").exists()


def test_pocos_clientes_o_perfiles_identicos_no_producen_grupos_ficticios(datos, tmp_path):
    def uniformes(filas):
        for fila in filas:
            if fila["empresa_id"] == "SYN-E01":
                fila.update(recencia_dias="5", frecuencia_compras="3", gasto_centavos="500")
    modificar_perfiles(datos, uniformes)
    with pytest.raises(ValueError, match="variedad"):
        entrenar_segmentacion(datos, "SYN-E01", tmp_path / "modelo")
    modificar_perfiles(datos, lambda filas: filas.__setitem__(slice(None),
        [f for f in filas if f["empresa_id"] != "SYN-E01"] + [f for f in filas if f["empresa_id"] == "SYN-E01"][:9]))
    with pytest.raises(ValueError, match="10 clientes"):
        entrenar_segmentacion(datos, "SYN-E01", tmp_path / "modelo")
    assert not (tmp_path / "modelo").exists()


@pytest.mark.parametrize("campo,valor,mensaje", [
    ("recencia_dias", "nan", "inválido"),
    ("gasto_centavos", "-1", "inválido"),
    ("frecuencia_compras", "0", "ventana declarada"),
    ("recencia_dias", "180", "ventana declarada"),
    ("fecha_corte", "2020-01-01", "compartir fecha"),
    ("cliente_id", "SYN-E02-C0001", "ajenos"),
    ("origen", "OFICIAL", "mezcla orígenes"),
])
def test_rechaza_perfiles_incoherentes_aunque_el_hash_coincida(datos, campo, valor, mensaje):
    modificar_perfiles(datos, lambda filas: filas[0].update({campo: valor}))
    with pytest.raises(ValueError, match=mensaje):
        cargar_perfiles(datos, "SYN-E01")


def test_rechaza_duplicados_y_oficial_sin_trazabilidad(datos):
    modificar_perfiles(datos, lambda filas: filas[1].update(cliente_id=filas[0]["cliente_id"]))
    with pytest.raises(ValueError, match="duplicados"):
        cargar_perfiles(datos, "SYN-E01")
    p = datos / "manifiesto.json"
    m = json.loads(p.read_text(encoding="utf-8"))
    m["origen"] = "OFICIAL"
    p.write_text(json.dumps(m), encoding="utf-8")
    with pytest.raises(ValueError, match="exportación autorizada"):
        cargar_perfiles(datos, "SYN-E01")
