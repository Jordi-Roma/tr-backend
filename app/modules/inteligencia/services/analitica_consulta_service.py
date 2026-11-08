"""Lectura autorizada de resultados JSON/CSV; no carga joblib ni entrena modelos."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
from datetime import date
from pathlib import Path

from fastapi import HTTPException

from app.core.contexto_empresa import exigir_empresa_id
from app.modules.inteligencia.repositories.reporte_repository import listar_sucursales
from app.modules.inteligencia.services.reporte_service import limitar_reporte

REGISTRO_PREDETERMINADO = Path(__file__).resolve().parents[4] / ".private/analitica/registro_api.json"


def _error_configuracion():
    return HTTPException(503, "Los resultados de analítica requieren revisión de su configuración o integridad.")


def _configuracion(usuario):
    ruta = Path(os.getenv("STYLEAR_ANALITICA_REGISTRO", str(REGISTRO_PREDETERMINADO))).resolve()
    if not ruta.exists():
        return ruta.parent, None
    try:
        if ruta.stat().st_size > 2_000_000:
            raise ValueError()
        registro = json.loads(ruta.read_text(encoding="utf-8"))
        if registro["version"] != 1:
            raise ValueError()
        empresa = registro["empresas"].get(str(usuario.get("empresa_codigo", "")))
        if empresa and empresa["empresa_id"] != exigir_empresa_id(usuario):
            raise ValueError()
        return ruta.parent, empresa
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise _error_configuracion() from None


def _archivo(raiz, referencia):
    try:
        ruta = (raiz / referencia["ruta"]).resolve()
        if not ruta.is_relative_to(raiz) or ruta.stat().st_size > 20_000_000:
            raise ValueError()
        contenido = ruta.read_bytes()
        if hashlib.sha256(contenido).hexdigest() != referencia["sha256"]:
            raise ValueError()
        return contenido.decode("utf-8")
    except (OSError, ValueError, KeyError, TypeError):
        raise _error_configuracion() from None


def _alcance(usuario, sucursal_id=None):
    eid = exigir_empresa_id(usuario)
    limitada = limitar_reporte(usuario)
    if limitada is not None and sucursal_id not in (None, limitada):
        raise HTTPException(403, "Solo puedes consultar la sucursal asignada.")
    seleccionada = limitada if limitada is not None else sucursal_id
    sucursales = listar_sucursales(eid)
    if seleccionada is not None and seleccionada not in {r["id"] for r in sucursales}:
        raise HTTPException(404, "Sucursal no encontrada en tu empresa.")
    return [r for r in sucursales if seleccionada is None or r["id"] == seleccionada], limitada is not None


def _fuente(empresa, origen):
    return (empresa or {}).get("demostracion" if origen == "DEMOSTRACION" else "oficial")


def _base(usuario, origen, fuente):
    return {"empresa_codigo": usuario.get("empresa_codigo"), "origen": origen,
            "estado": (fuente or {}).get("estado", "NO_CONFIGURADO"),
            "evaluado_en": (fuente or {}).get("evaluado_en"),
            "fuente_datos": (fuente or {}).get("fuente_datos"),
            "advertencia": ("Demostración con datos sintéticos separados de las ventas oficiales."
                             if origen == "DEMOSTRACION" else
                             "La disponibilidad depende del historial oficial validado; no se reemplaza con datos sintéticos.")}


def estado_analitica(usuario):
    sucursales, limitada = _alcance(usuario)
    _, empresa = _configuracion(usuario)
    fuentes = []
    for origen in ("OFICIAL", "DEMOSTRACION"):
        fuente = _fuente(empresa, origen)
        estado = _base(usuario, origen, fuente)
        estado["evaluado_en"] = (fuente or {}).get("evaluado_en")
        estado["fuente_datos"] = (fuente or {}).get("fuente_datos")
        tiene_sucursal = any(str(s["id"]) in (fuente or {}).get("sucursales", {}) for s in sucursales)
        estado["predicciones_disponibles"] = bool(tiene_sucursal and fuente and fuente.get("predicciones"))
        estado["segmentacion_disponible"] = bool(not limitada and fuente and fuente.get("segmentos"))
        estado["sucursales"] = [{"id": s["id"], "nombre": s["nombre"],
                                   "datos_disponibles": str(s["id"]) in (fuente or {}).get("sucursales", {})}
                                  for s in sucursales]
        if not limitada:
            # El registro contiene solo contadores revisados, nunca la conexión oficial.
            estado["resumen_historial"] = {k: v for k, v in (fuente or {}).get("resumen_historial", {}).items()
                                           if k in {"ventas_completadas", "dias_con_ventas", "clientes_compradores",
                                                    "ventas_con_senal_prueba", "ventas_sin_detalle"}}
        fuentes.append(estado)
    return {"fuentes": fuentes, "segmentacion_permitida": not limitada,
            "alcance": "SUCURSAL_ASIGNADA" if limitada else "EMPRESA"}


def _resultado(raiz, fuente, tipo, origen):
    try:
        archivos = fuente[tipo]
        evaluacion = json.loads(_archivo(raiz, archivos["evaluacion"]))
        esperado = "SINTETICO" if origen == "DEMOSTRACION" else "OFICIAL"
        if evaluacion["origen"] != esperado or evaluacion["empresa_id"] != fuente["empresa_dataset"]:
            raise ValueError()
        filas = list(csv.DictReader(io.StringIO(_archivo(raiz, archivos["filas"]))))
        if len(filas) > 100_000 or any(r.get("origen") != esperado or
                                      r.get("empresa_id") != fuente["empresa_dataset"] for r in filas):
            raise ValueError()
        return evaluacion, filas
    except (ValueError, KeyError, TypeError, csv.Error):
        raise _error_configuracion() from None


def _numero(valor):
    try:
        n = float(valor)
        if not math.isfinite(n) or not 0 <= n <= 1e15:
            raise ValueError()
        return n
    except (ValueError, TypeError):
        raise _error_configuracion() from None


def consultar_predicciones(usuario, filtros, *, exportar=False):
    sucursales, _ = _alcance(usuario, filtros.sucursal_id)
    raiz, empresa = _configuracion(usuario)
    fuente = _fuente(empresa, filtros.origen)
    respuesta = {**_base(usuario, filtros.origen, fuente), "tipo_resultado": "EVALUACION_HISTORICA",
                 "pagina": filtros.pagina, "tamano": filtros.tamano, "filas": [], "total_filas": 0,
                 "metricas": None, "serie": [], "productos": [], "sin_datos": True,
                 "sucursales_efectivas": [s["id"] for s in sucursales]}
    if not fuente or not fuente.get("predicciones"):
        return respuesta
    evaluacion, filas = _resultado(raiz, fuente, "predicciones", filtros.origen)
    mapeo = {str(v): s for s in sucursales if (v := fuente.get("sucursales", {}).get(str(s["id"]))) is not None}
    resultado, productos = [], set()
    try:
        for fila in filas:
            sucursal = mapeo.get(fila["sucursal_id"])
            if sucursal is None:
                continue
            productos.add(fila["producto_id"])
            corte = date.fromisoformat(fila["fecha_corte"])
            if filtros.producto_id and fila["producto_id"] != filtros.producto_id:
                continue
            if filtros.corte_desde and corte < filtros.corte_desde or filtros.corte_hasta and corte > filtros.corte_hasta:
                continue
            resultado.append({"sucursal_id": sucursal["id"], "sucursal": sucursal["nombre"],
                              "producto_id": fila["producto_id"], "fecha_corte": corte.isoformat(),
                              "objetivo_hasta": date.fromisoformat(fila["objetivo_hasta"]).isoformat(),
                              **{k: _numero(fila[k]) for k in ("unidades_reales", "unidades_predichas", "referencia_semana_anterior")}})
    except (ValueError, KeyError, TypeError):
        raise _error_configuracion() from None
    resultado.sort(key=lambda r: (r["fecha_corte"], r["sucursal_id"], r["producto_id"]))
    serie = {}
    for r in resultado:
        punto = serie.setdefault(r["fecha_corte"], {"fecha_corte": r["fecha_corte"], "unidades_reales": 0,
                                                  "unidades_predichas": 0, "referencia_semana_anterior": 0})
        for campo in ("unidades_reales", "unidades_predichas", "referencia_semana_anterior"):
            punto[campo] += r[campo]
    metricas = None
    if resultado:
        errores = [abs(r["unidades_reales"] - r["unidades_predichas"]) for r in resultado]
        referencias = [abs(r["unidades_reales"] - r["referencia_semana_anterior"]) for r in resultado]
        metricas = {"muestras": len(resultado), "mae": sum(errores) / len(errores),
                    "rmse": math.sqrt(sum(e * e for e in errores) / len(errores)),
                    "mae_referencia": sum(referencias) / len(referencias),
                    "unidad": "UNIDADES_POR_PRODUCTO_SUCURSAL_SEMANA"}
    inicio = (filtros.pagina - 1) * filtros.tamano
    if exportar and len(resultado) > 5000:
        raise HTTPException(422, "El reporte supera 5000 filas. Reduce los filtros antes de exportar.")
    respuesta.update(filas=resultado if exportar else resultado[inicio:inicio + filtros.tamano], total_filas=len(resultado),
                     metricas=metricas, serie=list(serie.values()), productos=sorted(productos),
                     sin_datos=not resultado, dataset_id=evaluacion["dataset_id"],
                     modelo=evaluacion["modelo"], entrenado_en=evaluacion["entrenado_en"])
    return respuesta


def consultar_segmentos(usuario, filtros, *, exportar=False):
    if "ADMIN_SAAS" in usuario.get("roles", []) or "ADMINISTRADOR" not in usuario.get("roles", []):
        raise HTTPException(403, "La segmentación está reservada al administrador de empresa.")
    limitar_reporte(usuario)
    raiz, empresa = _configuracion(usuario)
    fuente = _fuente(empresa, filtros.origen)
    respuesta = {**_base(usuario, filtros.origen, fuente), "pagina": filtros.pagina, "tamano": filtros.tamano,
                 "filas": [], "total_filas": 0, "perfiles": [], "metricas": None, "sin_datos": True}
    if not fuente or not fuente.get("segmentos"):
        return respuesta
    e, filas = _resultado(raiz, fuente, "segmentos", filtros.origen)
    try:
        perfiles = [{k: p[k] for k in ("grupo", "nombre", "clientes", "proporcion", "recencia_media_dias",
                     "recencia_mediana_dias", "frecuencia_media_compras", "frecuencia_mediana_compras",
                     "gasto_medio_centavos", "gasto_mediano_centavos", "descripcion")} for p in e["perfiles"]]
        grupos = {p["grupo"] for p in perfiles}
        resultado = []
        for fila in filas:
            grupo = int(fila["grupo"])
            if grupo not in grupos:
                raise ValueError()
            if filtros.grupo is not None and grupo != filtros.grupo:
                continue
            resultado.append({"cliente_id": fila["cliente_id"], "grupo": grupo,
                              **{k: _numero(fila[k]) for k in ("recencia_dias", "frecuencia_compras", "gasto_centavos")}})
        inicio = (filtros.pagina - 1) * filtros.tamano
        if exportar and len(resultado) > 5000:
            raise HTTPException(422, "El reporte supera 5000 filas. Reduce los filtros antes de exportar.")
        respuesta.update(filas=resultado if exportar else resultado[inicio:inicio + filtros.tamano], total_filas=len(resultado),
                         perfiles=perfiles, sin_datos=not resultado, fecha_corte=e["fecha_corte"],
                         ventana_dias=e["ventana_dias"], dataset_id=e["dataset_id"], modelo=e["modelo"],
                         entrenado_en=e["entrenado_en"],
                         clientes_sin_compras_ventana=e["clientes_sin_compras_ventana"],
                         metricas={"silhouette": e["silhouette"], "ari_medio": e["ari_medio"],
                                   "grupos": e["k_elegido"], "clientes_analizados": e["clientes_analizados"],
                                   "evaluacion": e["evaluacion"]},
                         advertencia=respuesta["advertencia"] + " Silhouette no es porcentaje de exactitud; ARI compara semillas, no estabilidad futura.")
        return respuesta
    except (ValueError, KeyError, TypeError):
        raise _error_configuracion() from None
