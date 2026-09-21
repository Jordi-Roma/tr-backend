from fastapi import APIRouter, Request

from app.modules.autenticacion.schemas.password_reset.password_reset_request import (
    ConfirmarPasswordResetRequest,
    SolicitarPasswordResetRequest,
)
from app.modules.autenticacion.schemas.password_reset.password_reset_response import (
    PasswordResetMensajeResponse,
)
from app.modules.autenticacion.services.password_reset_service import (
    confirmar_reset_password,
    solicitar_reset_password,
)

router = APIRouter(
    prefix="/api/v1/autenticacion",
    tags=["Autenticacion"],
)


def _extraer_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _extraer_ua(request: Request) -> str | None:
    return request.headers.get("User-Agent")


@router.post("/password-reset/solicitar", response_model=PasswordResetMensajeResponse)
def solicitar_password_reset_endpoint(
    request: SolicitarPasswordResetRequest,
    http_request: Request,
) -> PasswordResetMensajeResponse:
    return solicitar_reset_password(
        request,
        direccion_ip=_extraer_ip(http_request),
        user_agent=_extraer_ua(http_request),
    )


@router.post("/password-reset/confirmar", response_model=PasswordResetMensajeResponse)
def confirmar_password_reset_endpoint(
    request: ConfirmarPasswordResetRequest,
    http_request: Request,
) -> PasswordResetMensajeResponse:
    return confirmar_reset_password(
        request,
        direccion_ip=_extraer_ip(http_request),
        user_agent=_extraer_ua(http_request),
    )
