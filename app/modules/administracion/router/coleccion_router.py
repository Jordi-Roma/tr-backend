from fastapi import APIRouter, Depends, Request
from app.modules.administracion.schemas.catalogo.coleccion_request import (
    ActualizarColeccionRequest,
    CrearColeccionRequest,
)
from app.modules.administracion.schemas.catalogo.coleccion_response import ColeccionDetalleResponse
from app.modules.administracion.schemas.catalogo.catalogo_response import MensajeResponse
from app.modules.administracion.services.coleccion_service import (
    editar_coleccion,
    eliminar_coleccion,
    obtener_coleccion,
    obtener_colecciones,
    reactivar_coleccion,
    registrar_coleccion,
)
from app.modules.autenticacion.dependencies.admin_required import requerir_admin

router = APIRouter(
    prefix="/api/v1/colecciones",
    tags=["Colecciones"],
)


def _ip(req: Request) -> str | None:
    fwd = req.headers.get("X-Forwarded-For")
    return fwd.split(",")[0].strip() if fwd else (req.client.host if req.client else None)


def _ua(req: Request) -> str | None:
    return req.headers.get("User-Agent")


@router.get("", response_model=list[ColeccionDetalleResponse])
def listar_colecciones_endpoint(
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> list[ColeccionDetalleResponse]:
    return obtener_colecciones()


@router.post("", response_model=ColeccionDetalleResponse)
def crear_coleccion_endpoint(
    request: CrearColeccionRequest,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> ColeccionDetalleResponse:
    return registrar_coleccion(request, usuario_actual, _ip(http_request), _ua(http_request))


@router.get("/{coleccion_id}", response_model=ColeccionDetalleResponse)
def obtener_coleccion_endpoint(
    coleccion_id: int,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> ColeccionDetalleResponse:
    return obtener_coleccion(coleccion_id)


@router.put("/{coleccion_id}", response_model=ColeccionDetalleResponse)
def actualizar_coleccion_endpoint(
    coleccion_id: int,
    request: ActualizarColeccionRequest,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> ColeccionDetalleResponse:
    return editar_coleccion(coleccion_id, request, usuario_actual, _ip(http_request), _ua(http_request))


@router.patch("/{coleccion_id}/desactivar", response_model=MensajeResponse)
def desactivar_coleccion_endpoint(
    coleccion_id: int,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> MensajeResponse:
    return eliminar_coleccion(coleccion_id, usuario_actual, _ip(http_request), _ua(http_request))


@router.patch("/{coleccion_id}/activar", response_model=ColeccionDetalleResponse)
def activar_coleccion_endpoint(
    coleccion_id: int,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> ColeccionDetalleResponse:
    return reactivar_coleccion(coleccion_id, usuario_actual, _ip(http_request), _ua(http_request))
