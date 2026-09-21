import hashlib
import secrets

from fastapi import HTTPException

from app.core.config import PASSWORD_RESET_EMAIL, PASSWORD_RESET_TOKEN_MINUTES, SECRET_KEY
from app.core.email import enviar_correo
from app.core.security import hashear_password
from app.modules.autenticacion.repositories.bitacora_repository import registrar_bitacora
from app.modules.autenticacion.repositories.password_reset_repository import (
    consumir_token_reset,
    guardar_token_reset,
    obtener_usuario_por_identificador,
)
from app.modules.autenticacion.schemas.password_reset.password_reset_request import (
    ConfirmarPasswordResetRequest,
    SolicitarPasswordResetRequest,
)
from app.modules.autenticacion.schemas.password_reset.password_reset_response import (
    PasswordResetMensajeResponse,
)


MENSAJE_SOLICITUD = (
    "Si la cuenta existe, enviaremos un codigo de recuperacion al correo configurado."
)


def solicitar_reset_password(
    request: SolicitarPasswordResetRequest,
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> PasswordResetMensajeResponse:
    usuario = obtener_usuario_por_identificador(request.identificador)

    if usuario is None or not bool(usuario["activo"]):
        registrar_bitacora(
            usuario_id=None,
            accion="SOLICITUD_RESET_PASSWORD",
            modulo="AUTENTICACION",
            resultado="FALLIDO",
            descripcion="Solicitud de recuperacion para cuenta inexistente o inactiva.",
            direccion_ip=direccion_ip,
            user_agent=user_agent,
        )
        return PasswordResetMensajeResponse(mensaje=MENSAJE_SOLICITUD)

    codigo = f"{secrets.randbelow(1_000_000):06d}"
    guardar_token_reset(
        int(usuario["id"]),
        _hashear_codigo(codigo),
        PASSWORD_RESET_TOKEN_MINUTES,
    )
    enviar_correo(
        PASSWORD_RESET_EMAIL,
        "Codigo de recuperacion - StyleAR",
        (
            "Se solicito recuperar una contrasena en StyleAR.\n\n"
            f"Cuenta: {usuario['username']} ({usuario['correo']})\n"
            f"Codigo: {codigo}\n\n"
            f"Este codigo vence en {PASSWORD_RESET_TOKEN_MINUTES} minutos."
        ),
    )
    registrar_bitacora(
        usuario_id=int(usuario["id"]),
        accion="SOLICITUD_RESET_PASSWORD",
        modulo="AUTENTICACION",
        resultado="EXITOSO",
        descripcion="Codigo de recuperacion enviado al correo configurado.",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )

    return PasswordResetMensajeResponse(mensaje=MENSAJE_SOLICITUD)


def confirmar_reset_password(
    request: ConfirmarPasswordResetRequest,
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> PasswordResetMensajeResponse:
    if request.password_nuevo != request.confirmar_password_nuevo:
        raise HTTPException(status_code=400, detail="Las contrasenas no coinciden.")

    usuario = obtener_usuario_por_identificador(request.identificador)

    if usuario is None or not bool(usuario["activo"]):
        raise HTTPException(status_code=400, detail="Codigo invalido o expirado.")

    try:
        password_hash = hashear_password(request.password_nuevo)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    actualizado = consumir_token_reset(
        int(usuario["id"]),
        _hashear_codigo(request.codigo),
        password_hash,
    )

    if not actualizado:
        registrar_bitacora(
            usuario_id=int(usuario["id"]),
            accion="RESET_PASSWORD_FALLIDO",
            modulo="AUTENTICACION",
            resultado="FALLIDO",
            descripcion="Intento de cambio de contrasena con codigo invalido o expirado.",
            direccion_ip=direccion_ip,
            user_agent=user_agent,
        )
        raise HTTPException(status_code=400, detail="Codigo invalido o expirado.")

    registrar_bitacora(
        usuario_id=int(usuario["id"]),
        accion="RESET_PASSWORD_EXITOSO",
        modulo="AUTENTICACION",
        resultado="EXITOSO",
        descripcion="Contrasena restablecida mediante codigo de recuperacion.",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )

    return PasswordResetMensajeResponse(mensaje="Contrasena actualizada correctamente.")


def _hashear_codigo(codigo: str) -> str:
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY no esta configurada.")

    return hashlib.sha256(f"{codigo}:{SECRET_KEY}".encode("utf-8")).hexdigest()
