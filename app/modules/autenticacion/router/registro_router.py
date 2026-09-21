from fastapi import APIRouter, Request

from app.modules.autenticacion.schemas.usuario.usuario_request import (
    UsuarioRegistroRequest,
)
from app.modules.autenticacion.schemas.usuario.usuario_response import (
    UsuarioRegistroResponse,
)
from app.modules.autenticacion.services.registro_service import registrar_cliente

router = APIRouter(
    prefix="/api/v1/autenticacion",
    tags=["Autenticacion"],
)


@router.post("/registro", response_model=UsuarioRegistroResponse)
def registrar_usuario(
    request: UsuarioRegistroRequest,
    http_request: Request,
) -> UsuarioRegistroResponse:
    ip = http_request.client.host if http_request.client else None
    ua = http_request.headers.get("User-Agent")
    return registrar_cliente(request, direccion_ip=ip, user_agent=ua)
