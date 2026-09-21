from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.modules.autenticacion.schemas.sesion.sesion_request import LoginRequest
from app.modules.autenticacion.schemas.sesion.sesion_response import (
    LoginResponse,
    LogoutResponse,
)
from app.modules.autenticacion.services.sesion_service import cerrar_sesion, iniciar_sesion

router = APIRouter(
    prefix="/api/v1/autenticacion",
    tags=["Autenticacion"],
)

bearer_scheme = HTTPBearer()


def _extraer_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _extraer_ua(request: Request) -> str | None:
    return request.headers.get("User-Agent")


@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, http_request: Request) -> LoginResponse:
    return iniciar_sesion(
        request,
        direccion_ip=_extraer_ip(http_request),
        user_agent=_extraer_ua(http_request),
    )


@router.post("/logout", response_model=LogoutResponse)
def logout(
    http_request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> LogoutResponse:
    token = credentials.credentials
    return cerrar_sesion(
        token,
        direccion_ip=_extraer_ip(http_request),
        user_agent=_extraer_ua(http_request),
    )
