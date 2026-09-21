from fastapi import APIRouter, Depends, Request
from app.modules.administracion.schemas.producto.producto_request import (
    ActualizarProductoRequest,
    CrearProductoRequest,
)
from app.modules.administracion.schemas.producto.producto_response import ProductoResponse
from app.modules.administracion.schemas.catalogo.catalogo_response import MensajeResponse
from app.modules.administracion.services.producto_service import (
    editar_producto,
    eliminar_producto,
    obtener_producto,
    obtener_productos,
    reactivar_producto,
    registrar_producto,
)
from app.modules.autenticacion.dependencies.admin_required import requerir_admin

router = APIRouter(
    prefix="/api/v1/productos",
    tags=["Productos"],
)


def _ip(req: Request) -> str | None:
    fwd = req.headers.get("X-Forwarded-For")
    return fwd.split(",")[0].strip() if fwd else (req.client.host if req.client else None)


def _ua(req: Request) -> str | None:
    return req.headers.get("User-Agent")


@router.get("", response_model=list[ProductoResponse])
def listar_productos_endpoint(
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> list[ProductoResponse]:
    return obtener_productos()


@router.post("", response_model=ProductoResponse)
def crear_producto_endpoint(
    request: CrearProductoRequest,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> ProductoResponse:
    return registrar_producto(request, usuario_actual, _ip(http_request), _ua(http_request))


@router.get("/{producto_id}", response_model=ProductoResponse)
def obtener_producto_endpoint(
    producto_id: int,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> ProductoResponse:
    return obtener_producto(producto_id)


@router.put("/{producto_id}", response_model=ProductoResponse)
def actualizar_producto_endpoint(
    producto_id: int,
    request: ActualizarProductoRequest,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> ProductoResponse:
    return editar_producto(producto_id, request, usuario_actual, _ip(http_request), _ua(http_request))


@router.patch("/{producto_id}/desactivar", response_model=MensajeResponse)
def desactivar_producto_endpoint(
    producto_id: int,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> MensajeResponse:
    return eliminar_producto(producto_id, usuario_actual, _ip(http_request), _ua(http_request))


@router.patch("/{producto_id}/activar", response_model=ProductoResponse)
def activar_producto_endpoint(
    producto_id: int,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> ProductoResponse:
    return reactivar_producto(producto_id, usuario_actual, _ip(http_request), _ua(http_request))
