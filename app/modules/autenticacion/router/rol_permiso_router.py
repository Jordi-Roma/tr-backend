from fastapi import APIRouter, Depends, Request

from app.modules.autenticacion.dependencies.admin_required import requerir_admin
from app.modules.autenticacion.schemas.rol_permiso.rol_permiso_request import (
    ActualizarPermisosRolRequest,
    ActualizarRolRequest,
    CrearPermisoRequest,
    CrearRolRequest,
)
from app.modules.autenticacion.schemas.rol_permiso.rol_permiso_response import (
    MensajeResponse,
    PermisoResponse,
    RolPermisosResponse,
    RolResponse,
)
from app.modules.autenticacion.services.rol_permiso_service import (
    actualizar_permisos_por_rol,
    asignar_permiso,
    editar_rol,
    eliminar_permiso,
    eliminar_rol,
    obtener_permisos,
    obtener_permisos_por_rol,
    obtener_roles,
    quitar_permiso,
    reactivar_permiso,
    reactivar_permiso_rol,
    reactivar_rol,
    registrar_permiso,
    registrar_rol,
)

router = APIRouter(
    prefix="/api/v1",
    tags=["Roles y Permisos"],
)


def _ip(req: Request) -> str | None:
    fwd = req.headers.get("X-Forwarded-For")
    return fwd.split(",")[0].strip() if fwd else (req.client.host if req.client else None)


def _ua(req: Request) -> str | None:
    return req.headers.get("User-Agent")


@router.get("/roles", response_model=list[RolResponse])
def listar_roles_endpoint(
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> list[RolResponse]:
    return obtener_roles()


@router.post("/roles", response_model=RolResponse)
def crear_rol_endpoint(
    request: CrearRolRequest,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> RolResponse:
    return registrar_rol(request, usuario_actual, _ip(http_request), _ua(http_request))


@router.put("/roles/{rol_id}", response_model=RolResponse)
def actualizar_rol_endpoint(
    rol_id: int,
    request: ActualizarRolRequest,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> RolResponse:
    return editar_rol(rol_id, request, usuario_actual, _ip(http_request), _ua(http_request))


@router.patch("/roles/{rol_id}/desactivar", response_model=MensajeResponse)
def desactivar_rol_endpoint(
    rol_id: int,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> MensajeResponse:
    return eliminar_rol(rol_id, usuario_actual, _ip(http_request), _ua(http_request))


@router.patch("/roles/{rol_id}/activar", response_model=MensajeResponse)
def activar_rol_endpoint(
    rol_id: int,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> MensajeResponse:
    return reactivar_rol(rol_id, usuario_actual, _ip(http_request), _ua(http_request))


@router.get("/permisos", response_model=list[PermisoResponse])
def listar_permisos_endpoint(
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> list[PermisoResponse]:
    return obtener_permisos()


@router.get("/roles/{rol_id}/permisos", response_model=RolPermisosResponse)
def listar_permisos_rol_endpoint(
    rol_id: int,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> RolPermisosResponse:
    return obtener_permisos_por_rol(rol_id)


@router.put("/roles/{rol_id}/permisos", response_model=RolPermisosResponse)
def actualizar_permisos_rol_endpoint(
    rol_id: int,
    request: ActualizarPermisosRolRequest,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> RolPermisosResponse:
    return actualizar_permisos_por_rol(
        rol_id,
        request,
        usuario_actual,
        _ip(http_request),
        _ua(http_request),
    )


@router.post("/permisos", response_model=PermisoResponse)
def crear_permiso_endpoint(
    request: CrearPermisoRequest,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> PermisoResponse:
    return registrar_permiso(request, usuario_actual, _ip(http_request), _ua(http_request))


@router.patch("/permisos/{permiso_id}/desactivar", response_model=MensajeResponse)
def desactivar_permiso_endpoint(
    permiso_id: int,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> MensajeResponse:
    return eliminar_permiso(permiso_id, usuario_actual, _ip(http_request), _ua(http_request))


@router.patch("/permisos/{permiso_id}/activar", response_model=MensajeResponse)
def activar_permiso_endpoint(
    permiso_id: int,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> MensajeResponse:
    return reactivar_permiso(permiso_id, usuario_actual, _ip(http_request), _ua(http_request))


@router.post("/roles/{rol_id}/permisos/{permiso_id}", response_model=MensajeResponse)
def asignar_permiso_endpoint(
    rol_id: int,
    permiso_id: int,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> MensajeResponse:
    return asignar_permiso(rol_id, permiso_id, usuario_actual, _ip(http_request), _ua(http_request))


@router.patch(
    "/roles/{rol_id}/permisos/{permiso_id}/desactivar",
    response_model=MensajeResponse,
)
def quitar_permiso_endpoint(
    rol_id: int,
    permiso_id: int,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> MensajeResponse:
    return quitar_permiso(rol_id, permiso_id, usuario_actual, _ip(http_request), _ua(http_request))


@router.patch(
    "/roles/{rol_id}/permisos/{permiso_id}/activar",
    response_model=MensajeResponse,
)
def activar_permiso_rol_endpoint(
    rol_id: int,
    permiso_id: int,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> MensajeResponse:
    return reactivar_permiso_rol(rol_id, permiso_id, usuario_actual, _ip(http_request), _ua(http_request))
