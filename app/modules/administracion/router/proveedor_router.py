from fastapi import APIRouter, Depends, Request

from app.modules.administracion.schemas.proveedor.proveedor_request import (
    ActualizarProveedorRequest,
    CrearProveedorRequest,
    VincularUsuarioProveedorRequest,
    CrearCuentaProveedorRequest,
    VincularProductoProveedorRequest,
)
from app.modules.administracion.schemas.proveedor.proveedor_response import (
    MensajeResponse,
    ProveedorEntregaResponse,
    ProveedorPerfilResponse,
    ProveedorProductoResponse,
    ProveedorResponse,
    ProveedorStockResponse,
)
from app.modules.administracion.services.proveedor_service import (
    editar_proveedor,
    desvincular_usuario,
    eliminar_proveedor,
    listar_entregas_panel_proveedor,
    listar_productos_panel_proveedor,
    listar_stock_panel_proveedor,
    obtener_proveedor,
    obtener_perfil_proveedor,
    obtener_proveedores,
    reactivar_proveedor,
    registrar_proveedor,
    vincular_usuario,
)
from app.modules.administracion.repositories import proveedor_repository as proveedores
from app.core.contexto_empresa import exigir_empresa_id
from app.core.security import hashear_password
from fastapi import HTTPException
from app.modules.autenticacion.dependencies.admin_required import requerir_admin
from app.modules.autenticacion.dependencies.usuario_actual import obtener_usuario_actual

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
    return obtener_proveedores(usuario_actual)


@router.post("/proveedores", response_model=ProveedorResponse)
def crear_proveedor_endpoint(
    request: CrearProveedorRequest,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> ProveedorResponse:
    return registrar_proveedor(request, usuario_actual, _ip(http_request), _ua(http_request))


@router.get("/proveedores/cuentas-disponibles")
def cuentas_disponibles(actor=Depends(requerir_admin)):
    return proveedores.listar_cuentas_vinculables(exigir_empresa_id(actor))


@router.get("/proveedores/productos-disponibles")
def productos_disponibles(actor=Depends(requerir_admin)):
    return proveedores.listar_productos_vinculables(exigir_empresa_id(actor))


@router.get("/proveedores/{proveedor_id}", response_model=ProveedorResponse)
def obtener_proveedor_endpoint(
    proveedor_id: int,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> ProveedorResponse:
    return obtener_proveedor(proveedor_id, usuario_actual)


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


@router.post("/proveedores/{proveedor_id}/usuarios", response_model=ProveedorResponse)
def vincular_usuario_proveedor_endpoint(
    proveedor_id: int,
    request: VincularUsuarioProveedorRequest,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> ProveedorResponse:
    return vincular_usuario(proveedor_id, request, usuario_actual, _ip(http_request), _ua(http_request))


@router.delete("/proveedores/{proveedor_id}/usuarios/{usuario_id}", response_model=ProveedorResponse)
def desvincular_usuario_proveedor_endpoint(
    proveedor_id: int,
    usuario_id: int,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> ProveedorResponse:
    return desvincular_usuario(proveedor_id, usuario_id, usuario_actual, _ip(http_request), _ua(http_request))


@router.get("/proveedor-panel/perfil", response_model=ProveedorPerfilResponse)
def obtener_perfil_proveedor_endpoint(
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> ProveedorPerfilResponse:
    return obtener_perfil_proveedor(usuario_actual)


@router.get("/proveedor-panel/productos", response_model=list[ProveedorProductoResponse])
def listar_productos_proveedor_endpoint(
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> list[ProveedorProductoResponse]:
    return listar_productos_panel_proveedor(usuario_actual)


@router.get("/proveedor-panel/stock", response_model=list[ProveedorStockResponse])
def listar_stock_proveedor_endpoint(
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> list[ProveedorStockResponse]:
    return listar_stock_panel_proveedor(usuario_actual)


@router.get("/proveedor-panel/entregas", response_model=list[ProveedorEntregaResponse])
def listar_entregas_proveedor_endpoint(
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> list[ProveedorEntregaResponse]:
    return listar_entregas_panel_proveedor(usuario_actual)


@router.post('/proveedores/{proveedor_id}/crear-usuario', response_model=ProveedorResponse)
def crear_cuenta(proveedor_id: int, datos: CrearCuentaProveedorRequest, actor=Depends(requerir_admin)):
    try:
        password_hash = hashear_password(datos.password)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    return proveedores.crear_cuenta_proveedor(proveedor_id, datos, password_hash, exigir_empresa_id(actor), int(actor['id']))


@router.get('/proveedores/{proveedor_id}/productos', response_model=list[ProveedorProductoResponse])
def productos_vinculados(proveedor_id: int, actor=Depends(requerir_admin)):
    obtener_proveedor(proveedor_id, actor)
    return proveedores.listar_productos_proveedor_panel(proveedor_id, exigir_empresa_id(actor))


@router.post('/proveedores/{proveedor_id}/productos', response_model=list[ProveedorProductoResponse])
def asociar_producto(proveedor_id: int, datos: VincularProductoProveedorRequest, actor=Depends(requerir_admin)):
    return proveedores.vincular_producto_proveedor(proveedor_id, datos.producto_id, exigir_empresa_id(actor), int(actor['id']))


@router.delete('/proveedores/{proveedor_id}/productos/{producto_id}', response_model=list[ProveedorProductoResponse])
def retirar_producto(proveedor_id: int, producto_id: int, actor=Depends(requerir_admin)):
    return proveedores.vincular_producto_proveedor(proveedor_id, producto_id, exigir_empresa_id(actor), int(actor['id']), activo=False)
