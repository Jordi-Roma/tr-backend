from fastapi import APIRouter, Depends, Request

from app.modules.administracion.schemas.proveedor.proveedor_request import (
    ActualizarProveedorRequest,
    CrearProveedorRequest,
)
from app.modules.administracion.schemas.proveedor.proveedor_response import (
    MensajeResponse,
    ProveedorResponse,
)
from app.modules.administracion.services.proveedor_service import (
    editar_proveedor,
    eliminar_proveedor,
    obtener_proveedor,
    obtener_proveedores,
    reactivar_proveedor,
    registrar_proveedor,
)
from app.modules.autenticacion.dependencies.admin_required import requerir_admin

router = APIRouter(
    prefix="/api/v1",
    tags=["Proveedores"],
)


def _ip(req: Request) -> str | None:
    fwd = req.headers.get("X-Forwarded-For")
    return fwd.split(",")[0].strip() if fwd else (req.client.host if req.client else None)


def _ua(req: Request) -> str | None:
    return req.headers.get("User-Agent")


@router.get("/proveedores", response_model=list[ProveedorResponse])
def listar_proveedores_endpoint(
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> list[ProveedorResponse]:
    return obtener_proveedores()


@router.post("/proveedores", response_model=ProveedorResponse)
def crear_proveedor_endpoint(
    request: CrearProveedorRequest,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> ProveedorResponse:
    return registrar_proveedor(request, usuario_actual, _ip(http_request), _ua(http_request))


@router.get("/proveedores/{proveedor_id}", response_model=ProveedorResponse)
def obtener_proveedor_endpoint(
    proveedor_id: int,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> ProveedorResponse:
    return obtener_proveedor(proveedor_id)


@router.put("/proveedores/{proveedor_id}", response_model=ProveedorResponse)
def actualizar_proveedor_endpoint(
    proveedor_id: int,
    request: ActualizarProveedorRequest,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> ProveedorResponse:
    return editar_proveedor(proveedor_id, request, usuario_actual, _ip(http_request), _ua(http_request))


@router.patch("/proveedores/{proveedor_id}/desactivar", response_model=MensajeResponse)
def desactivar_proveedor_endpoint(
    proveedor_id: int,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> MensajeResponse:
    return eliminar_proveedor(proveedor_id, usuario_actual, _ip(http_request), _ua(http_request))


@router.patch("/proveedores/{proveedor_id}/activar", response_model=ProveedorResponse)
def activar_proveedor_endpoint(
    proveedor_id: int,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> ProveedorResponse:
    return reactivar_proveedor(proveedor_id, usuario_actual, _ip(http_request), _ua(http_request))
