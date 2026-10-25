from fastapi import APIRouter, Depends, Request

from app.modules.administracion.schemas.ciudad_sucursal.ciudad_sucursal_request import (
    ActualizarCiudadRequest,
    ActualizarSucursalRequest,
    CrearCiudadRequest,
    CrearSucursalRequest,
)
from app.modules.administracion.schemas.ciudad_sucursal.ciudad_sucursal_response import (
    CiudadResponse,
    MensajeResponse,
    SucursalResponse,
)
from app.modules.administracion.services.ciudad_sucursal_service import (
    editar_ciudad,
    editar_sucursal,
    eliminar_ciudad,
    eliminar_sucursal,
    obtener_ciudad,
    obtener_ciudades,
    obtener_sucursal,
    obtener_sucursales,
    reactivar_ciudad,
    reactivar_sucursal,
    registrar_ciudad,
    registrar_sucursal,
)
from app.modules.autenticacion.dependencies.admin_required import requerir_admin
from app.modules.autenticacion.dependencies.usuario_actual import obtener_usuario_actual
from app.modules.autenticacion.autorizacion import exigir_permiso

router = APIRouter(
    prefix="/api/v1",
    tags=["Ciudades y Sucursales"],
)


def admin_cu06(accion: str):
    def validar(actor=Depends(exigir_permiso(accion))):
        return requerir_admin(actor)
    return validar


def _ip(req: Request) -> str | None:
    fwd = req.headers.get("X-Forwarded-For")
    return fwd.split(",")[0].strip() if fwd else (req.client.host if req.client else None)


def _ua(req: Request) -> str | None:
    return req.headers.get("User-Agent")


@router.get("/ciudades", response_model=list[CiudadResponse])
def listar_ciudades_endpoint(
    incluir_inactivos: bool = False,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> list[CiudadResponse]:
    if incluir_inactivos:
        requerir_admin(usuario_actual)
    if "ADMINISTRADOR" in usuario_actual.get("roles", []):
        exigir_permiso("ciudades:ver")(usuario_actual)
    return obtener_ciudades(usuario_actual, incluir_inactivos)


@router.post("/ciudades", response_model=CiudadResponse)
def crear_ciudad_endpoint(
    request: CrearCiudadRequest,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(admin_cu06("ciudades:crear")),
) -> CiudadResponse:
    return registrar_ciudad(request, usuario_actual, _ip(http_request), _ua(http_request))


@router.get("/ciudades/{ciudad_id}", response_model=CiudadResponse)
def obtener_ciudad_endpoint(
    ciudad_id: int,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> CiudadResponse:
    if "ADMINISTRADOR" in usuario_actual.get("roles", []):
        exigir_permiso("ciudades:ver")(usuario_actual)
    return obtener_ciudad(ciudad_id, usuario_actual)


@router.put("/ciudades/{ciudad_id}", response_model=CiudadResponse)
def actualizar_ciudad_endpoint(
    ciudad_id: int,
    request: ActualizarCiudadRequest,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(admin_cu06("ciudades:editar")),
) -> CiudadResponse:
    return editar_ciudad(ciudad_id, request, usuario_actual, _ip(http_request), _ua(http_request))


@router.patch("/ciudades/{ciudad_id}/desactivar", response_model=MensajeResponse)
def desactivar_ciudad_endpoint(
    ciudad_id: int,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(admin_cu06("ciudades:desactivar")),
) -> MensajeResponse:
    return eliminar_ciudad(ciudad_id, usuario_actual, _ip(http_request), _ua(http_request))


@router.patch("/ciudades/{ciudad_id}/activar", response_model=MensajeResponse)
def activar_ciudad_endpoint(
    ciudad_id: int,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(admin_cu06("ciudades:editar")),
) -> MensajeResponse:
    return reactivar_ciudad(ciudad_id, usuario_actual, _ip(http_request), _ua(http_request))


@router.get("/sucursales", response_model=list[SucursalResponse])
def listar_sucursales_endpoint(
    incluir_inactivos: bool = False,
    usuario_actual: dict[str, object] = Depends(admin_cu06("sucursales:ver")),
) -> list[SucursalResponse]:
    return obtener_sucursales(usuario_actual, incluir_inactivos)


@router.post("/sucursales", response_model=SucursalResponse)
def crear_sucursal_endpoint(
    request: CrearSucursalRequest,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(admin_cu06("sucursales:crear")),
) -> SucursalResponse:
    return registrar_sucursal(request, usuario_actual, _ip(http_request), _ua(http_request))


@router.get("/sucursales/{sucursal_id}", response_model=SucursalResponse)
def obtener_sucursal_endpoint(
    sucursal_id: int,
    usuario_actual: dict[str, object] = Depends(admin_cu06("sucursales:ver")),
) -> SucursalResponse:
    return obtener_sucursal(sucursal_id, usuario_actual)


@router.put("/sucursales/{sucursal_id}", response_model=SucursalResponse)
def actualizar_sucursal_endpoint(
    sucursal_id: int,
    request: ActualizarSucursalRequest,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(admin_cu06("sucursales:editar")),
) -> SucursalResponse:
    return editar_sucursal(sucursal_id, request, usuario_actual, _ip(http_request), _ua(http_request))


@router.patch("/sucursales/{sucursal_id}/desactivar", response_model=MensajeResponse)
def desactivar_sucursal_endpoint(
    sucursal_id: int,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(admin_cu06("sucursales:desactivar")),
) -> MensajeResponse:
    return eliminar_sucursal(sucursal_id, usuario_actual, _ip(http_request), _ua(http_request))


@router.patch("/sucursales/{sucursal_id}/activar", response_model=MensajeResponse)
def activar_sucursal_endpoint(
    sucursal_id: int,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(admin_cu06("sucursales:editar")),
) -> MensajeResponse:
    return reactivar_sucursal(sucursal_id, usuario_actual, _ip(http_request), _ua(http_request))
