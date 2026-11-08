import csv
import hashlib
import json

import pytest

pytest.importorskip("sklearn", reason="Requiere las dependencias opcionales de requirements-ml.txt")
import joblib
import numpy as np

from app.modules.inteligencia.services.analitica_datos_service import ConfiguracionDatos, generar_dataset
from app.modules.inteligencia.services.analitica_entrenamiento_service import (
    VARIABLES, cargar_muestras, entrenar_prediccion,
)


@pytest.fixture
def datos(tmp_path):
    carpeta = tmp_path / "dataset"
    generar_dataset(carpeta, ConfiguracionDatos(dias=210, empresas=2, sucursales=1, productos=2, clientes=20))
    return carpeta


def reescribir(dataset, modificar):
    archivo = dataset / "prediccion_semanal.csv"
    with archivo.open(encoding="utf-8", newline="") as entrada:
        lector = csv.DictReader(entrada)
        campos, filas = lector.fieldnames, list(lector)
    modificar(filas)
    with archivo.open("w", encoding="utf-8", newline="") as salida:
        escritor = csv.DictWriter(salida, fieldnames=campos, lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(filas)
    manifiesto = dataset / "manifiesto.json"
    m = json.loads(manifiesto.read_text(encoding="utf-8"))
    m["archivos"][archivo.name]["sha256"] = hashlib.sha256(archivo.read_bytes()).hexdigest()
    manifiesto.write_text(json.dumps(m), encoding="utf-8")


def test_entrenamiento_aislado_evalua_referencia_y_persiste_modelo_propio(datos, tmp_path):
    salida = tmp_path / "modelo"
    reporte = entrenar_prediccion(datos, "SYN-E01", salida)
    assert reporte["origen"] == "SINTETICO" and reporte["estado"] == "DEMOSTRACION_SINTETICA"
    assert reporte["parametros_elegidos"] == min(reporte["candidatos"], key=lambda r: r["validacion"]["mae"])["parametros"]
    assert reporte["prueba"]["modelo"]["mae"] >= 0
    assert reporte["prueba"]["referencia_semana_anterior"]["mae"] >= 0
    assert set(reporte["por_sucursal"]) == {"SYN-E01-S01"}
    assert hashlib.sha256((salida / "modelo.joblib").read_bytes()).hexdigest() == reporte["sha256_modelo"]
    modelo = joblib.load(salida / "modelo.joblib")  # Solo el artefacto propio creado en esta prueba.
    _, partes = cargar_muestras(datos, "SYN-E01")
    x = np.array([[f[campo] for campo in VARIABLES] for f in partes["PRUEBA"]], dtype=object)
    with (salida / "predicciones_prueba.csv").open(encoding="utf-8", newline="") as archivo:
        filas = list(csv.DictReader(archivo))
    assert {f["empresa_id"] for f in filas} == {"SYN-E01"}
    assert np.allclose(modelo.predict(x), [float(f["unidades_predichas"]) for f in filas])
    referencia_mae = sum(abs(float(f["unidades_reales"]) - float(f["referencia_semana_anterior"])) for f in filas) / len(filas)
    assert reporte["prueba"]["referencia_semana_anterior"]["mae"] == pytest.approx(referencia_mae)
    categorias = modelo.named_steps["variables"].named_transformers_["categoricas"].categories_
    assert all("SYN-E02" not in str(valor) for columna in categorias for valor in columna)
    with pytest.raises(FileExistsError):
        entrenar_prediccion(datos, "SYN-E01", salida)


def test_rechaza_csv_alterado_y_empresa_sin_historial(datos, tmp_path):
    with pytest.raises(ValueError, match="Historial insuficiente"):
        entrenar_prediccion(datos, "EMPRESA-INEXISTENTE", tmp_path / "sin_historial")
    with (datos / "prediccion_semanal.csv").open("a", encoding="utf-8") as archivo:
        archivo.write("\n")
    with pytest.raises(ValueError, match="hash"):
        entrenar_prediccion(datos, "SYN-E01", tmp_path / "alterado")
    assert not (tmp_path / "alterado").exists()


def test_rechaza_fuga_temporal_aunque_el_hash_sea_valido(datos):
    def modificar(filas):
        for fila in filas:
            if fila["particion"] == "PRUEBA":
                fila["particion"] = "ENTRENAMIENTO"
                break
    reescribir(datos, modificar)
    with pytest.raises(ValueError, match="fuga de información"):
        cargar_muestras(datos, "SYN-E01")


def test_rechaza_valores_no_finitos_y_origen_oficial_sin_trazabilidad(datos):
    def modificar(filas):
        filas[0]["unidades_7d"] = "nan"
    reescribir(datos, modificar)
    with pytest.raises(ValueError, match="Valor inválido"):
        cargar_muestras(datos, "SYN-E01")
    archivo = datos / "manifiesto.json"
    m = json.loads(archivo.read_text(encoding="utf-8"))
    m["origen"] = "OFICIAL"
    archivo.write_text(json.dumps(m), encoding="utf-8")
    with pytest.raises(ValueError, match="exportación autorizada"):
        cargar_muestras(datos, "SYN-E01")
