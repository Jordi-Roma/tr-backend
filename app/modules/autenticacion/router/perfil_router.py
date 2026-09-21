from fastapi import APIRouter, Depends, Request

from app.modules.autenticacion.dependencies.usuario_actual import obtener_usuario_actual
from app.modules.autenticacion.schemas.perfil.perfil_request import (
    ActualizarDireccionRequest,
    ActualizarPerfilRequest,
    CambiarPasswordRequest,
    CrearDireccionRequest,
)
from app.modules.autenticacion.schemas.perfil.perfil_response import (
    DireccionResponse,
    ListaDireccionesResponse,
    MensajeResponse,
    PerfilResponse,
)
from app.modules.autenticacion.services.perfil_service import (
    actualizar_direccion,
    actualizar_perfil,
    cambiar_password,
    crear_direccion,
    desactivar_direccion,
    listar_direcciones,
    obtener_perfil,
)

router = APIRouter(
    prefix="/api/v1/perfil",
    tags=["Perfil"],
)


@router.get("", response_model=PerfilResponse)
def ver_perfil(
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> PerfilResponse:
    return obtener_perfil(usuario_actual)


@router.put("", response_model=PerfilResponse)
def editar_perfil(
    request: ActualizarPerfilRequest,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> PerfilResponse:
    ip = http_request.client.host if http_request.client else None
    ua = http_request.headers.get("User-Agent")
    return actualizar_perfil(usuario_actual, request, direccion_ip=ip, user_agent=ua)


@router.put("/password", response_model=MensajeResponse)
def editar_password(
    request: CambiarPasswordRequest,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> MensajeResponse:
    ip = http_request.client.host if http_request.client else None
    ua = http_request.headers.get("User-Agent")
    return cambiar_password(usuario_actual, request, direccion_ip=ip, user_agent=ua)


@router.get("/direcciones", response_model=ListaDireccionesResponse)
def ver_direcciones(
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> ListaDireccionesResponse:
    return listar_direcciones(usuario_actual)


@router.post("/direcciones", response_model=DireccionResponse)
def registrar_direccion(
    request: CrearDireccionRequest,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> DireccionResponse:
    return crear_direccion(usuario_actual, request)


@router.put("/direcciones/{direccion_id}", response_model=DireccionResponse)
def editar_direccion(
    direccion_id: int,
    request: ActualizarDireccionRequest,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> DireccionResponse:
    return actualizar_direccion(usuario_actual, direccion_id, request)


@router.delete("/direcciones/{direccion_id}", response_model=MensajeResponse)
def eliminar_direccion(
    direccion_id: int,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> MensajeResponse:
    return desactivar_direccion(usuario_actual, direccion_id)
