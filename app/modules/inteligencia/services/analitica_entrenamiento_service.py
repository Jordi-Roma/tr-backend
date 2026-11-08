"""Entrenamiento explícito por empresa. Sin conexiones de base de datos o HTTP."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import joblib
import numpy as np
import scipy
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

VERSION_ENTRENAMIENTO = "1"
CATEGORICAS = ("producto_id", "sucursal_id", "categoria")
NUMERICAS = ("mes", "precio_corte_centavos", "descuento_corte_pct", "stock_corte",
             "unidades_7d", "unidades_28d", "dias_sin_stock_28d")
VARIABLES = CATEGORICAS + NUMERICAS
PARTICIONES = ("ENTRENAMIENTO", "VALIDACION", "PRUEBA")
CANDIDATOS = ((6, 2), (6, 5), (None, 2), (None, 5))


def cargar_muestras(dataset: Path, empresa_id: str) -> tuple[dict, dict[str, list[dict]]]:
    dataset = Path(dataset)
    manifiesto = json.loads((dataset / "manifiesto.json").read_text(encoding="utf-8"))
    origen = manifiesto.get("origen")
    if manifiesto.get("version_datos") != "1" or origen not in {"SINTETICO", "OFICIAL"}:
        raise ValueError("Versión u origen de datos no soportados.")
    if origen == "OFICIAL" and not manifiesto.get("fuente", {}).get("referencia_exportacion"):
        raise ValueError("Los datos oficiales requieren trazabilidad de su exportación autorizada.")
    archivo = dataset / "prediccion_semanal.csv"
    info = manifiesto.get("archivos", {}).get(archivo.name, {})
    if hashlib.sha256(archivo.read_bytes()).hexdigest() != info.get("sha256"):
        raise ValueError("El CSV no coincide con el hash de su manifiesto.")
    particiones = {nombre: [] for nombre in PARTICIONES}
    claves = set()
    with archivo.open(encoding="utf-8", newline="") as entrada:
        for fila in csv.DictReader(entrada):
            if fila.get("empresa_id") != empresa_id:
                continue
            if fila.get("origen") != origen or fila.get("particion") not in particiones:
                raise ValueError("Una muestra tiene origen o partición incompatibles.")
            if any(not fila.get(campo) for campo in CATEGORICAS):
                raise ValueError("Una muestra no identifica producto, sucursal o categoría.")
            corte = date.fromisoformat(fila["fecha_corte"])
            if date.fromisoformat(fila["objetivo_desde"]) != corte + timedelta(days=1) or \
                    date.fromisoformat(fila["objetivo_hasta"]) != corte + timedelta(days=7):
                raise ValueError("El horizonte objetivo debe ser posterior al corte y durar siete días.")
            clave = (fila["producto_id"], fila["sucursal_id"], corte)
            if clave in claves:
                raise ValueError("Hay muestras duplicadas para la misma serie y fecha.")
            claves.add(clave)
            for campo in NUMERICAS + ("objetivo_unidades_7d",):
                valor = float(fila[campo])
                if not math.isfinite(valor) or valor < 0:
                    raise ValueError(f"Valor inválido en {campo}.")
                fila[campo] = valor
            if not 1 <= fila["mes"] <= 12 or fila["descuento_corte_pct"] > 100:
                raise ValueError("Mes o descuento fuera de rango.")
            particiones[fila["particion"]].append(fila)
    for nombre, minimo in zip(PARTICIONES, (8, 2, 2)):
        filas = particiones[nombre]
        if len({r["fecha_corte"] for r in filas}) < minimo:
            raise ValueError(f"Historial insuficiente en {nombre}: se requieren {minimo} fechas de corte.")
        filas.sort(key=lambda r: (r["fecha_corte"], r["sucursal_id"], r["producto_id"]))
    for antes, despues in zip(PARTICIONES, PARTICIONES[1:]):
        # El objetivo del último corte de entrenamiento puede terminar al cierre
        # del primer corte de validación, pero nunca después de ese cierre.
        if max(r["objetivo_hasta"] for r in particiones[antes]) > min(r["fecha_corte"] for r in particiones[despues]):
            raise ValueError("Las particiones temporales tienen fuga de información.")
    return manifiesto, particiones


def _matriz(filas: list[dict]) -> np.ndarray:
    return np.array([[r[campo] for campo in VARIABLES] for r in filas], dtype=object)


def _metricas(reales, predichas) -> dict:
    return {"mae": float(mean_absolute_error(reales, predichas)),
            "rmse": float(root_mean_squared_error(reales, predichas)), "muestras": len(reales)}


def entrenar_prediccion(dataset: Path, empresa_id: str, destino: Path, *, semilla: int = 20261108) -> dict:
    """Entrena una empresa y publica artefactos nuevos sin cargar modelos ajenos."""
    destino = Path(destino).resolve()
    if destino.exists():
        raise FileExistsError("La carpeta de salida ya existe. Usa una carpeta nueva para esta ejecución.")
    if not empresa_id or not isinstance(semilla, int):
        raise ValueError("Empresa y semilla son obligatorias.")
    manifiesto, partes = cargar_muestras(dataset, empresa_id)
    matrices = {nombre: _matriz(filas) for nombre, filas in partes.items()}
    objetivos = {nombre: np.array([r["objetivo_unidades_7d"] for r in filas])
                 for nombre, filas in partes.items()}
    resultados, mejor, mejor_mae = [], None, float("inf")
    for profundidad, hojas in CANDIDATOS:
        preprocesamiento = ColumnTransformer([
            ("categoricas", OneHotEncoder(handle_unknown="ignore", sparse_output=False), list(range(len(CATEGORICAS)))),
            ("numericas", "passthrough", list(range(len(CATEGORICAS), len(VARIABLES)))),
        ])
        modelo = Pipeline([
            ("variables", preprocesamiento),
            ("regresor", RandomForestRegressor(n_estimators=120, max_depth=profundidad,
                                               min_samples_leaf=hojas, random_state=semilla, n_jobs=1)),
        ])
        modelo.fit(matrices["ENTRENAMIENTO"], objetivos["ENTRENAMIENTO"])
        validacion = _metricas(objetivos["VALIDACION"], modelo.predict(matrices["VALIDACION"]))
        parametros = {"n_estimators": 120, "max_depth": profundidad, "min_samples_leaf": hojas}
        resultados.append({"parametros": parametros, "validacion": validacion})
        if validacion["mae"] < mejor_mae:
            mejor_mae, mejor = validacion["mae"], modelo
            seleccion = parametros
    # El conjunto de prueba no decide el modelo: se evalúa después de seleccionarlo.
    predicciones = mejor.predict(matrices["PRUEBA"])
    referencia = np.array([r["unidades_7d"] for r in partes["PRUEBA"]])
    prueba = _metricas(objetivos["PRUEBA"], predicciones)
    baseline = _metricas(objetivos["PRUEBA"], referencia)
    sucursales = {}
    for sid in sorted({r["sucursal_id"] for r in partes["PRUEBA"]}):
        indices = [i for i, r in enumerate(partes["PRUEBA"]) if r["sucursal_id"] == sid]
        sucursales[sid] = {"modelo": _metricas(objetivos["PRUEBA"][indices], predicciones[indices]),
                           "referencia": _metricas(objetivos["PRUEBA"][indices], referencia[indices])}
    reporte = {
        "version_entrenamiento": VERSION_ENTRENAMIENTO, "empresa_id": empresa_id,
        "origen": manifiesto["origen"], "dataset_id": manifiesto["dataset_id"],
        "sha256_muestras": manifiesto["archivos"]["prediccion_semanal.csv"]["sha256"],
        "fuente": manifiesto.get("fuente"), "entrenado_en": datetime.now(timezone.utc).isoformat(),
        "semilla": semilla, "modelo": "RandomForestRegressor", "variables": list(VARIABLES),
        "objetivo": "objetivo_unidades_7d", "horizonte_dias": 7,
        "unidad_error": "UNIDADES_POR_PRODUCTO_SUCURSAL_SEMANA",
        "particiones": {nombre: {"filas": len(filas),
                        "corte_desde": min(r["fecha_corte"] for r in filas),
                        "corte_hasta": max(r["fecha_corte"] for r in filas),
                        "objetivo_hasta": max(r["objetivo_hasta"] for r in filas)} for nombre, filas in partes.items()},
        "candidatos": resultados, "parametros_elegidos": seleccion,
        "prueba": {"modelo": prueba, "referencia_semana_anterior": baseline,
                   "mejora_mae_absoluta": baseline["mae"] - prueba["mae"],
                   "supera_referencia": prueba["mae"] < baseline["mae"]},
        "por_sucursal": sucursales,
        "versiones": {"python": platform.python_version(), "numpy": np.__version__,
                      "scipy": scipy.__version__, "scikit_learn": sklearn.__version__, "joblib": joblib.__version__},
        "estado": "DEMOSTRACION_SINTETICA" if manifiesto["origen"] == "SINTETICO" else "EVALUADO_SIN_PUBLICAR",
        "advertencia": ("Métricas sobre datos sintéticos; no demuestran precisión en el despliegue oficial."
                        if manifiesto["origen"] == "SINTETICO" else
                        "Evaluación histórica de una exportación autorizada; no garantiza resultados futuros."),
    }
    destino.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".entrenamiento-", dir=destino.parent) as temporal:
        carpeta = Path(temporal) / "modelo"
        carpeta.mkdir()
        # Solo artefactos propios, locales y de confianza. No hay endpoint para cargar joblib.
        joblib.dump(mejor, carpeta / "modelo.joblib", compress=3)
        reporte["sha256_modelo"] = hashlib.sha256((carpeta / "modelo.joblib").read_bytes()).hexdigest()
        (carpeta / "evaluacion.json").write_text(json.dumps(reporte, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        with (carpeta / "predicciones_prueba.csv").open("w", encoding="utf-8", newline="") as salida:
            escritor = csv.writer(salida, lineterminator="\n")
            escritor.writerow(["origen", "empresa_id", "sucursal_id", "producto_id", "fecha_corte",
                                "objetivo_hasta", "unidades_reales", "unidades_predichas", "referencia_semana_anterior"])
            for fila, pred, ref in zip(partes["PRUEBA"], predicciones, referencia):
                escritor.writerow([fila[k] for k in ("origen", "empresa_id", "sucursal_id", "producto_id", "fecha_corte", "objetivo_hasta")]
                                   + [fila["objetivo_unidades_7d"], float(pred), float(ref)])
        carpeta.rename(destino)
    return reporte
