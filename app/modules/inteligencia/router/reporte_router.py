from io import BytesIO

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.contexto_empresa import exigir_empresa_id
from app.core.plan_empresa import exigir_funcion_empresa
from app.modules.autenticacion.dependencies.admin_required import requerir_admin
from app.modules.inteligencia.exports.reporte_excel import crear_excel
from app.modules.inteligencia.exports.reporte_pdf import crear_pdf
from app.modules.inteligencia.schemas.reportes.reporte_request import (
    ActualizarEstadoProgramadoRequest,
    CrearReporteProgramadoRequest,
    InterpretarRequest,
    ReporteRequest,
)
from app.modules.inteligencia.services.reporte_service import (
    actualizar_estado_programado_service,
    catalogo_reportes,
    crear_programado_service,
    ejecutar_programado_service,
    eliminar_programado_service,
    generar_reporte,
    interpretar,
    listar_programados_service,
)

def requerir_reportes(usuario: dict[str, object] = Depends(requerir_admin)):
    exigir_funcion_empresa(exigir_empresa_id(usuario), "reportes", permitir_consulta=True)
    return usuario


router = APIRouter(prefix="/api/v1/reportes", tags=["Reportes"], dependencies=[Depends(requerir_reportes)])


@router.get("/catalogo")
def catalogo_endpoint(usuario_actual: dict[str, object] = Depends(requerir_admin)):
    return catalogo_reportes(exigir_empresa_id(usuario_actual))


@router.post("/interpretar")
def interpretar_endpoint(request: InterpretarRequest, usuario_actual: dict[str, object] = Depends(requerir_admin)):
    return interpretar(request.texto, exigir_empresa_id(usuario_actual))


@router.post("/generar")
def generar_endpoint(request: ReporteRequest, usuario_actual: dict[str, object] = Depends(requerir_admin)):
    return generar_reporte(request, exigir_empresa_id(usuario_actual))


def _archivo(request: ReporteRequest, extension: str, empresa_id: int):
    reporte = generar_reporte(request, empresa_id)
    data = crear_pdf(reporte) if extension == "pdf" else crear_excel(reporte)
    mime = "application/pdf" if extension == "pdf" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    filename = f"{request.tipo.lower()}_{request.fecha_desde}_{request.fecha_hasta}.{extension}"
    return StreamingResponse(BytesIO(data), media_type=mime, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.post("/exportar/pdf")
def pdf_endpoint(request: ReporteRequest, usuario_actual: dict[str, object] = Depends(requerir_admin)):
    return _archivo(request, "pdf", exigir_empresa_id(usuario_actual))


@router.post("/exportar/excel")
def excel_endpoint(request: ReporteRequest, usuario_actual: dict[str, object] = Depends(requerir_admin)):
    return _archivo(request, "xlsx", exigir_empresa_id(usuario_actual))


# ── Reportes Programados / Automáticos ─────────────────────────────


@router.get("/programados")
def listar_programados(usuario_actual: dict[str, object] = Depends(requerir_admin)):
    return listar_programados_service(usuario_actual)


@router.post("/programados")
def crear_programado(request: CrearReporteProgramadoRequest, usuario_actual: dict[str, object] = Depends(requerir_admin)):
    return crear_programado_service(request, usuario_actual)


@router.patch("/programados/{programado_id}/estado")
def cambiar_estado_programado(
    programado_id: int,
    request: ActualizarEstadoProgramadoRequest,
    usuario_actual: dict[str, object] = Depends(requerir_admin)
):
    return actualizar_estado_programado_service(programado_id, request.activo, usuario_actual)


@router.delete("/programados/{programado_id}")
def eliminar_programado(programado_id: int, usuario_actual: dict[str, object] = Depends(requerir_admin)):
    return eliminar_programado_service(programado_id, usuario_actual)


@router.post("/programados/{programado_id}/ejecutar")
def ejecutar_programado(programado_id: int, usuario_actual: dict[str, object] = Depends(requerir_admin)):
    return ejecutar_programado_service(programado_id, usuario_actual)
