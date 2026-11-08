"""Segmentación RFM explícita por empresa; no consulta ni modifica bases de datos."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import joblib
import numpy as np
import scipy
import sklearn
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler
from threadpoolctl import threadpool_limits

VARIABLES_RFM = ("recencia_dias", "frecuencia_compras", "gasto_centavos")
VERSION_SEGMENTACION = "1"


def cargar_perfiles(dataset: Path, empresa_id: str) -> tuple[dict, list[dict], int]:
    dataset = Path(dataset)
    m = json.loads((dataset / "manifiesto.json").read_text(encoding="utf-8"))
    if m.get("version_datos") != "1" or m.get("origen") not in {"SINTETICO", "OFICIAL"}:
        raise ValueError("Versión u origen de datos no soportados.")
    if m["origen"] == "OFICIAL" and not m.get("fuente", {}).get("referencia_exportacion"):
        raise ValueError("El dataset oficial requiere trazabilidad de su exportación autorizada.")

    def leer(nombre):
        archivo = dataset / nombre
        if hashlib.sha256(archivo.read_bytes()).hexdigest() != m.get("archivos", {}).get(nombre, {}).get("sha256"):
            raise ValueError(f"El hash de {nombre} no coincide con su manifiesto.")
        with archivo.open(encoding="utf-8", newline="") as entrada:
            return [r for r in csv.DictReader(entrada) if r.get("empresa_id") == empresa_id]

    clientes = leer("clientes.csv")
    ids = [r.get("cliente_id") for r in clientes]
    if any(not cid for cid in ids) or len(set(ids)) != len(ids):
        raise ValueError("El catálogo contiene clientes sin identificador o duplicados.")
    ids_validos = set(ids)
    if any(r.get("origen") != m["origen"] for r in clientes):
        raise ValueError("El catálogo mezcla orígenes de datos.")
    filas = leer("clientes_rfm.csv")
    vistos, cortes, ventanas = set(), set(), set()
    for fila in filas:
        cid = fila.get("cliente_id")
        if cid not in ids_validos or cid in vistos:
            raise ValueError("Hay perfiles duplicados o de clientes ajenos al catálogo de la empresa.")
        vistos.add(cid)
        if fila.get("origen") != m["origen"]:
            raise ValueError("El perfil mezcla orígenes de datos.")
        cortes.add(date.fromisoformat(fila["fecha_corte"]))
        ventana = int(fila["ventana_dias"])
        if not 1 <= ventana <= 180:
            raise ValueError("La ventana RFM debe estar entre 1 y 180 días.")
        ventanas.add(ventana)
        for campo in VARIABLES_RFM:
            valor = float(fila[campo])
            if not math.isfinite(valor) or valor < 0 or not valor.is_integer():
                raise ValueError(f"Valor RFM inválido en {campo}.")
            fila[campo] = int(valor)
        if fila["frecuencia_compras"] < 1 or fila["recencia_dias"] >= ventana:
            raise ValueError("El perfil no representa compras dentro de la ventana declarada.")
    if len(filas) < 10:
        raise ValueError("Historial insuficiente: se requieren al menos 10 clientes con compras en la ventana.")
    if len(filas) > 50_000:
        raise ValueError("El conjunto supera el límite de 50000 perfiles por ejecución.")
    if len(cortes) != 1 or len(ventanas) != 1:
        raise ValueError("Los perfiles deben compartir fecha de corte y ventana de observación.")
    filas.sort(key=lambda r: r["cliente_id"])
    return m, filas, len(ids) - len(filas)


def _pipeline(k, semilla):
    return Pipeline([
        ("logaritmo", FunctionTransformer(np.log1p, validate=True, feature_names_out="one-to-one")),
        ("escala", StandardScaler()),
        ("grupos", KMeans(n_clusters=k, n_init=20, random_state=semilla)),
    ])


def entrenar_segmentacion(dataset: Path, empresa_id: str, destino: Path, *, semilla: int = 20261108) -> dict:
    destino = Path(destino).resolve()
    if destino.exists():
        raise FileExistsError("La salida ya existe. Usa una carpeta nueva para esta ejecución.")
    if not empresa_id or type(semilla) is not int:
        raise ValueError("Empresa y semilla son obligatorias.")
    m, filas, excluidos = cargar_perfiles(dataset, empresa_id)
    x = np.array([[r[campo] for campo in VARIABLES_RFM] for r in filas], dtype=float)
    distintos = len(np.unique(x, axis=0))
    if distintos < 3:
        raise ValueError("No hay suficiente variedad de perfiles para evaluar grupos distintos.")
    candidatos, mejor, mejor_score = [], None, -float("inf")
    maximo = min(6, len(filas) // 3, distintos - 1)
    # Un solo hilo evita que una ejecución académica monopolice el equipo.
    with threadpool_limits(limits=1):
        for k in range(2, maximo + 1):
            modelo = _pipeline(k, semilla)
            etiquetas = modelo.fit_predict(x)
            tamanos = np.bincount(etiquetas, minlength=k)
            if np.count_nonzero(tamanos) != k or tamanos.min() < 3:
                candidatos.append({"k": k, "elegible": False,
                                   "motivo": "Se requieren al menos tres clientes por grupo.",
                                   "tamanos": tamanos.tolist()})
                continue
            transformados = modelo[:-1].transform(x)
            try:
                score = float(silhouette_score(transformados, etiquetas,
                                               sample_size=min(len(filas), 2000), random_state=semilla))
            except ValueError:
                candidatos.append({"k": k, "elegible": False, "motivo": "No se pudo evaluar la separación de los grupos."})
                continue
            candidatos.append({"k": k, "elegible": True, "silhouette": score,
                               "inercia": float(modelo[-1].inertia_), "tamanos": tamanos.tolist()})
            if score > mejor_score:
                mejor_score, mejor, elegidas, k_elegido = score, modelo, etiquetas.copy(), k
        if mejor is None:
            raise ValueError("No se encontraron grupos evaluables con al menos tres clientes por grupo.")
        estabilidad = []
        for otra_semilla in (semilla + 1, semilla + 2):
            otras = _pipeline(k_elegido, otra_semilla).fit_predict(x)
            estabilidad.append({"semilla": otra_semilla,
                                "ari": float(adjusted_rand_score(elegidas, otras)),
                                "grupos_obtenidos": len(np.unique(otras))})

    # La numeración visible es descriptiva y estable por gasto medio, no una etiqueta aprendida.
    orden = sorted(range(k_elegido), key=lambda n: (-float(x[elegidas == n, 2].mean()), n))
    mapa = {int(original): visible + 1 for visible, original in enumerate(orden)}
    perfiles = []
    for original in orden:
        grupo = x[elegidas == original]
        perfiles.append({
            "grupo": mapa[original], "nombre": f"Grupo {mapa[original]}",
            "clientes": len(grupo), "proporcion": len(grupo) / len(filas),
            "recencia_media_dias": float(grupo[:, 0].mean()),
            "recencia_mediana_dias": float(np.median(grupo[:, 0])),
            "frecuencia_media_compras": float(grupo[:, 1].mean()),
            "frecuencia_mediana_compras": float(np.median(grupo[:, 1])),
            "gasto_medio_centavos": float(grupo[:, 2].mean()),
            "gasto_mediano_centavos": float(np.median(grupo[:, 2])),
            "descripcion": f"Promedios en la ventana: {grupo[:, 0].mean():.1f} días desde la última compra, "
                           f"{grupo[:, 1].mean():.1f} compras y Bs {grupo[:, 2].mean() / 100:.2f} de gasto.",
        })
    reporte = {
        "version_segmentacion": VERSION_SEGMENTACION, "modelo": "KMeans", "empresa_id": empresa_id,
        "origen": m["origen"], "dataset_id": m["dataset_id"], "fuente": m.get("fuente"),
        "sha256_perfiles": m["archivos"]["clientes_rfm.csv"]["sha256"],
        "sha256_clientes": m["archivos"]["clientes.csv"]["sha256"],
        "entrenado_en": datetime.now(timezone.utc).isoformat(), "semilla": semilla,
        "fecha_corte": filas[0]["fecha_corte"], "ventana_dias": int(filas[0]["ventana_dias"]),
        "variables": list(VARIABLES_RFM), "transformaciones": ["log1p", "StandardScaler"],
        "clientes_analizados": len(filas), "clientes_sin_compras_ventana": excluidos,
        "k_elegido": k_elegido, "candidatos": candidatos, "silhouette": mejor_score,
        "evaluacion": "INTERNA_SOBRE_LA_MISMA_INSTANTANEA",
        "estabilidad_semillas": estabilidad, "ari_medio": float(np.mean([e["ari"] for e in estabilidad])),
        "perfiles": perfiles, "mapa_etiquetas": {str(k): v for k, v in mapa.items()},
        "versiones": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
                      "scikit_learn": sklearn.__version__, "joblib": joblib.__version__},
        "estado": "DEMOSTRACION_SINTETICA" if m["origen"] == "SINTETICO" else "EVALUADO_SIN_PUBLICAR",
        "advertencia": ("Segmentación de demostración con datos sintéticos; no describe a los clientes oficiales. "
                        if m["origen"] == "SINTETICO" else "Segmentación histórica sin publicación automática. ")
                       + "Silhouette mide separación interna, no porcentaje de exactitud. ARI compara semillas; no mide estabilidad futura.",
    }
    destino.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".segmentacion-", dir=destino.parent) as temporal:
        carpeta = Path(temporal) / "modelo"
        carpeta.mkdir()
        joblib.dump(mejor, carpeta / "modelo.joblib", compress=3)
        reporte["sha256_modelo"] = hashlib.sha256((carpeta / "modelo.joblib").read_bytes()).hexdigest()
        (carpeta / "evaluacion.json").write_text(json.dumps(reporte, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        with (carpeta / "asignaciones.csv").open("w", encoding="utf-8", newline="") as salida:
            escritor = csv.writer(salida, lineterminator="\n")
            escritor.writerow(["origen", "empresa_id", "cliente_id", "fecha_corte", "grupo", *VARIABLES_RFM])
            for fila, etiqueta in zip(filas, elegidas):
                escritor.writerow([fila[c] for c in ("origen", "empresa_id", "cliente_id", "fecha_corte")]
                                   + [mapa[int(etiqueta)]] + [fila[c] for c in VARIABLES_RFM])
        carpeta.rename(destino)
    return reporte
