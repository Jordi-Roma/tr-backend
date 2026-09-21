from fastapi import APIRouter, Depends, Request
from app.modules.administracion.schemas.catalogo.temporada_request import (
    ActualizarTemporadaRequest,
    CrearTemporadaRequest,
)
from app.modules.administracion.schemas.catalogo.temporada_response import TemporadaResponse
from app.modules.administracion.schemas.catalogo.catalogo_response import MensajeResponse
from app.modules.administracion.services.temporada_service import (
    editar_temporada,
    eliminar_temporada,
    obtener_temporada,
    obtener_temporadas,
    reactivar_temporada,
    registrar_temporada,
)
from app.modules.autenticacion.dependencies.admin_required import requerir_admin

router = APIRouter(
    prefix="/api/v1/temporadas",
    tags=["Temporadas"],
)


def _ip(req: Request) -> str | None:
    fwd = req.headers.get("X-Forwarded-For")
    return fwd.split(",")[0].strip() if fwd else (req.client.host if req.client else None)


def _ua(req: Request) -> str | None:
    return req.headers.get("User-Agent")


@router.get("", response_model=list[TemporadaResponse])
def listar_temporadas_endpoint(
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> list[TemporadaResponse]:
    return obtener_temporadas()


@router.post("", response_model=TemporadaResponse)
def crear_temporada_endpoint(
    request: CrearTemporadaRequest,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> TemporadaResponse:
    return registrar_temporada(request, usuario_actual, _ip(http_request), _ua(http_request))


@router.get("/{temporada_id}", response_model=TemporadaResponse)
def obtener_temporada_endpoint(
    temporada_id: int,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> TemporadaResponse:
    return obtener_temporada(temporada_id)


@router.put("/{temporada_id}", response_model=TemporadaResponse)
def actualizar_temporada_endpoint(
    temporada_id: int,
    request: ActualizarTemporadaRequest,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> TemporadaResponse:
    return editar_temporada(temporada_id, request, usuario_actual, _ip(http_request), _ua(http_request))


@router.patch("/{temporada_id}/desactivar", response_model=MensajeResponse)
def desactivar_temporada_endpoint(
    temporada_id: int,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> MensajeResponse:
    return eliminar_temporada(temporada_id, usuario_actual, _ip(http_request), _ua(http_request))


@router.patch("/{temporada_id}/activar", response_model=TemporadaResponse)
def activar_temporada_endpoint(
    temporada_id: int,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> TemporadaResponse:
    return reactivar_temporada(temporada_id, usuario_actual, _ip(http_request), _ua(http_request))
