"""Reportes ML: consultas registradas, alcance verificado y sin SQL generado."""
import re
import unicodedata
from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from pydantic import ValidationError

from app.modules.inteligencia.schemas.reportes.analitica_request import (
    ExportarAnaliticaRequest, FiltrosAnalitica, FiltrosSegmentacion,
)
from app.modules.inteligencia.services.analitica_consulta_service import (
    _alcance, consultar_predicciones, consultar_segmentos,
)


def preparar_reporte(usuario, solicitud):
    filtros = solicitud.model_dump(exclude={"tipo"}, exclude_none=True)
    if solicitud.tipo == "PREDICCIONES":
        filtros.pop("grupo", None)
        datos = consultar_predicciones(usuario, FiltrosAnalitica(**filtros), exportar=True)
    else:
        datos = consultar_segmentos(usuario, FiltrosSegmentacion(**filtros), exportar=True)
    sucursales = _alcance(usuario, solicitud.sucursal_id)[0] if solicitud.tipo == 'PREDICCIONES' else []
    return {"tipo": solicitud.tipo, "titulo": "Evaluación histórica de predicciones" if solicitud.tipo == "PREDICCIONES" else "Segmentación de clientes",
            "generado_en": datetime.now(ZoneInfo("America/La_Paz")).isoformat(),
            "empresa": usuario.get("empresa_codigo"), "filtros": solicitud.model_dump(mode="json", exclude_none=True),
            "alcance_sucursales": ', '.join(s['nombre'] for s in sucursales) if sucursales else 'Empresa completa',
            "datos": datos}


def _normalizar(texto):
    return " ".join("".join(c for c in unicodedata.normalize("NFD", texto.casefold()) if unicodedata.category(c) != "Mn").split())


def interpretar_solicitud(usuario, request):
    sucursales, limitada = _alcance(usuario)
    texto = _normalizar(request.texto)
    base = {"motor": "REGLAS_ANALITICA", "requiere_aclaracion": True, "solicitud": None,
            "formato_sugerido": "PANTALLA", "mensaje": "Indica si deseas evaluación de predicciones o grupos de clientes."}
    def aclarar(mensaje):
        return {**base, "mensaje": mensaje}
    if re.search(r"\b(select|insert|update|delete|drop|alter)\b|https?://|otras? empresas?|todas las empresas", texto):
        return aclarar("Solo se admiten reportes registrados de tu empresa; no consultas SQL ni fuentes externas.")
    if re.search(r"\b(mayor|menor|mas de|menos de|top|color|talla|descuento)\b", texto):
        return aclarar("Esos criterios no están soportados en estos reportes ML. Usa sucursal, producto, fechas de corte o número de grupo.")
    if re.search(r"\d{2,4}/\d{1,2}/\d{1,4}", texto):
        return aclarar("Usa fechas de corte explícitas con formato AAAA-MM-DD.")
    if 'pdf' in texto and re.search(r'excel|xlsx', texto):
        return aclarar("Elige un formato sugerido por solicitud: PDF o Excel. Después puedes descargar ambos desde los botones.")
    pred = bool(re.search(r"predic|pronostic|\bmae\b|\brmse\b|ventas estimadas", texto))
    seg = bool(re.search(r"segment|grupos? de clientes|clientes agrupados", texto))
    if pred == seg:
        return aclarar("Elige un análisis: evaluación histórica de predicciones o segmentación de clientes.")
    if pred and re.search(r"proxim|futur|manana|siguiente semana", texto):
        return aclarar("Actualmente hay evaluación histórica de semanas de prueba; todavía no hay pronóstico oficial vigente. Solicita esa evaluación si deseas consultarla.")
    demo = bool(re.search(r"sintetic|demostracion|simulad", texto))
    oficial = "oficial" in texto
    if demo and oficial:
        return aclarar("Indica un solo origen: historial oficial o demostración sintética.")
    origen = "DEMOSTRACION" if demo else "OFICIAL" if oficial else request.origen
    solicitud = {"tipo": "PREDICCIONES" if pred else "SEGMENTOS", "origen": origen}
    if seg and limitada:
        raise HTTPException(403, "La segmentación está reservada al administrador de empresa.")
    fechas = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", texto)
    if re.search(r"este mes|ultim|enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre", texto) and not fechas:
        return aclarar("Usa fechas de corte explícitas AAAA-MM-DD para la evaluación histórica; no se asume que existan datos del mes actual.")
    if len(fechas) > 2 or seg and fechas:
        return aclarar("La segmentación usa la fecha de su instantánea. Para predicciones se admite una fecha de corte o un rango de dos fechas.")
    if fechas:
        try:
            for f in fechas: date.fromisoformat(f)
        except ValueError:
            return aclarar("Revisa las fechas; usa fechas de calendario válidas AAAA-MM-DD.")
        solicitud.update(corte_desde=fechas[0], corte_hasta=fechas[-1])
    def mencion(sucursal):
        nombre = _normalizar(sucursal['nombre'])
        alias = re.sub(r"^(suc\.?|sucursal)\s+", "", nombre)
        return bool(re.search(r"\b" + re.escape(nombre) + r"\b", texto) or
                    len(alias) >= 3 and re.search(r"\b" + re.escape(alias) + r"\b", texto))
    menciones = [s for s in sucursales if mencion(s)]
    numero = re.search(r"\bsucursal(?: id| numero)?\s+(\d+)\b", texto)
    if numero:
        sid = int(numero.group(1)); _alcance(usuario, sid)
        menciones = [s for s in sucursales if s["id"] == sid]
    if seg and (menciones or re.search(r"\bsucursal\b", texto)):
        return aclarar("Los segmentos corresponden a la empresa completa y no admiten filtro por sucursal.")
    if len(menciones) > 1:
        return aclarar("Selecciona una sucursal o solicita todas las autorizadas sin nombrar varias.")
    if pred and menciones:
        solicitud["sucursal_id"] = menciones[0]["id"]
    elif pred and re.search(r"\bsucursal\b", texto) and not re.search(r"mi sucursal|todas las sucursales", texto):
        return aclarar("No se identificó una sucursal autorizada. Usa su nombre exacto o 'mi sucursal'.")
    if pred and limitada:
        solicitud["sucursal_id"] = sucursales[0]["id"]
    elif pred and 'mi sucursal' in texto and not menciones:
        if len(sucursales) != 1:
            return aclarar("Indica el nombre de la sucursal o solicita todas las autorizadas; tu cuenta administra más de una.")
        solicitud['sucursal_id'] = sucursales[0]['id']
    producto = re.search(r"\bproducto\s+([a-z0-9_-]+)", texto)
    if producto:
        if seg:
            return aclarar("El filtro de producto solo corresponde a predicciones.")
        # Conserva el identificador original; los IDs sintéticos distinguen mayúsculas.
        original = re.search(r"\bproducto\s+([a-z0-9_-]+)", request.texto, flags=re.I)
        solicitud["producto_id"] = original.group(1)
    grupo = re.search(r"\b(?:grupo|segmento)\s+(\d+)\b", texto)
    if grupo:
        if pred:
            return aclarar("El filtro de grupo solo corresponde a segmentación.")
        solicitud["grupo"] = int(grupo.group(1))
    try:
        validada = ExportarAnaliticaRequest(**solicitud)
    except ValidationError:
        return aclarar("Revisa el rango de fechas, el grupo (1–6) y los filtros solicitados.")
    formato = "PDF" if "pdf" in texto else "EXCEL" if re.search(r"excel|xlsx", texto) else "PANTALLA"
    return {**base, "requiere_aclaracion": False, "solicitud": validada.model_dump(mode="json", exclude_none=True),
            "formato_sugerido": formato,
            "mensaje": "Revisa y aplica estos filtros antes de consultar o exportar. Interpretación local por reglas; no se ejecutó SQL ni se entrenó un modelo."}
