from fastapi import APIRouter, Depends, Request
from app.modules.administracion.schemas.variante.variante_request import (
    ActualizarVarianteRequest,
    CrearVarianteRequest,
    AsignarPrecioRequest,
)
from app.modules.administracion.schemas.variante.variante_response import VarianteResponse
from app.modules.administracion.schemas.catalogo.catalogo_response import MensajeResponse
from app.modules.administracion.services.variante_service import (
    editar_variante,
    eliminar_variante,
    obtener_variante,
    obtener_variantes,
    reactivar_variante,
    registrar_variante,
    registrar_precio,
)
from app.modules.autenticacion.dependencies.admin_required import requerir_admin

router = APIRouter(
    prefix="/api/v1/variantes",
    tags=["Variantes"],
)


def _ip(req: Request) -> str | None:
    fwd = req.headers.get("X-Forwarded-For")
    return fwd.split(",")[0].strip() if fwd else (req.client.host if req.client else None)


def _ua(req: Request) -> str | None:
    return req.headers.get("User-Agent")


@router.get("", response_model=list[VarianteResponse])
def listar_variantes_endpoint(
    producto_id: int | None = None,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> list[VarianteResponse]:
    return obtener_variantes(producto_id)


@router.post("", response_model=VarianteResponse)
def crear_variante_endpoint(
    request: CrearVarianteRequest,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> VarianteResponse:
    return registrar_variante(request, usuario_actual, _ip(http_request), _ua(http_request))


@router.get("/{variante_id}", response_model=VarianteResponse)
def obtener_variante_endpoint(
    variante_id: int,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> VarianteResponse:
    return obtener_variante(variante_id)


@router.put("/{variante_id}", response_model=VarianteResponse)
def actualizar_variante_endpoint(
    variante_id: int,
    request: ActualizarVarianteRequest,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> VarianteResponse:
    return editar_variante(variante_id, request, usuario_actual, _ip(http_request), _ua(http_request))


@router.patch("/{variante_id}/desactivar", response_model=MensajeResponse)
def desactivar_variante_endpoint(
    variante_id: int,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> MensajeResponse:
    return eliminar_variante(variante_id, usuario_actual, _ip(http_request), _ua(http_request))


@router.patch("/{variante_id}/activar", response_model=VarianteResponse)
def activar_variante_endpoint(
    variante_id: int,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> VarianteResponse:
    return reactivar_variante(variante_id, usuario_actual, _ip(http_request), _ua(http_request))


@router.post("/{variante_id}/precios", response_model=VarianteResponse)
def asignar_precio_endpoint(
    variante_id: int,
    request: AsignarPrecioRequest,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> VarianteResponse:
    return registrar_precio(variante_id, request, usuario_actual, _ip(http_request), _ua(http_request))
