from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from app.core.contexto_empresa import exigir_empresa_id
from app.core.plan_empresa import exigir_funcion_empresa

from app.modules.inteligencia.router.reporte_router import requerir_reportes
from app.modules.inteligencia.schemas.reportes.analitica_request import FiltrosAnalitica, FiltrosSegmentacion
from app.modules.inteligencia.schemas.reportes.analitica_request import ExportarAnaliticaRequest, InterpretarAnaliticaRequest
from app.modules.inteligencia.services.analitica_reporte_service import preparar_reporte, interpretar_solicitud
from app.modules.inteligencia.exports.analitica_export import crear_pdf_ml, crear_excel_ml
from app.modules.inteligencia.services.analitica_consulta_service import (
    consultar_predicciones, consultar_segmentos, estado_analitica,
)


def sin_cache(response: Response):
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(prefix="/api/v1/reportes/analitica", tags=["Analítica ML"],
                   dependencies=[Depends(sin_cache)])


@router.get("/estado")
def estado(usuario=Depends(requerir_reportes)):
    return estado_analitica(usuario)


@router.get("/predicciones")
def predicciones(filtros: Annotated[FiltrosAnalitica, Query()], usuario=Depends(requerir_reportes)):
    return consultar_predicciones(usuario, filtros)


@router.get("/segmentos")
def segmentos(filtros: Annotated[FiltrosSegmentacion, Query()], usuario=Depends(requerir_reportes)):
    return consultar_segmentos(usuario, filtros)


@router.get("/metricas")
def metricas(filtros: Annotated[FiltrosAnalitica, Query()], usuario=Depends(requerir_reportes)):
    resultado = consultar_predicciones(usuario, filtros)
    return {k: resultado[k] for k in ("origen", "estado", "tipo_resultado", "advertencia", "metricas",
                                     "total_filas", "sucursales_efectivas")}


@router.post('/interpretar')
def interpretar(request: InterpretarAnaliticaRequest, usuario=Depends(requerir_reportes)):
    exigir_funcion_empresa(exigir_empresa_id(usuario), 'reportes_interpretacion')
    if request.origen_entrada == 'VOZ':
        exigir_funcion_empresa(exigir_empresa_id(usuario), 'reportes_voz')
    return interpretar_solicitud(usuario, request)


def _exportar(request, usuario, formato):
    exigir_funcion_empresa(exigir_empresa_id(usuario), 'reportes_pdf' if formato == 'pdf' else 'reportes_excel')
    reporte = preparar_reporte(usuario, request)
    datos = crear_pdf_ml(reporte) if formato == 'pdf' else crear_excel_ml(reporte)
    extension = 'pdf' if formato == 'pdf' else 'xlsx'
    mime = 'application/pdf' if formato == 'pdf' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    nombre = f'analitica_{request.tipo.lower()}_{request.origen.lower()}.{extension}'
    return Response(datos, media_type=mime, headers={'Content-Disposition': f'attachment; filename="{nombre}"', 'Cache-Control': 'no-store'})


@router.post('/exportar/pdf')
def pdf(request: ExportarAnaliticaRequest, usuario=Depends(requerir_reportes)):
    return _exportar(request, usuario, 'pdf')


@router.post('/exportar/excel')
def excel(request: ExportarAnaliticaRequest, usuario=Depends(requerir_reportes)):
    return _exportar(request, usuario, 'excel')
