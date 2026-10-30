import hashlib
import secrets

from fastapi import HTTPException

from app.core.contexto_empresa import resolver_empresa_por_codigo
from app.core.config import PASSWORD_RESET_TOKEN_MINUTES, SECRET_KEY
from app.core.email import enviar_correo, usa_destino_fijo
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
    "Si la cuenta está disponible, enviaremos un código de recuperación a su correo registrado."
)


def _mensaje_solicitud() -> str:
    if usa_destino_fijo():
        return "Si la cuenta está disponible, enviaremos un código de recuperación al correo de recepción configurado."
    return MENSAJE_SOLICITUD


def solicitar_reset_password(
    request: SolicitarPasswordResetRequest,
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> PasswordResetMensajeResponse:
    empresa = resolver_empresa_por_codigo(request.empresa_codigo) if request.empresa_codigo else None
    empresa_id = int(empresa["id"]) if empresa else None
    disponible = request.empresa_codigo is None or (empresa is not None and empresa["estado"] in {"ACTIVA", "SUSPENDIDA"})
    usuario = obtener_usuario_por_identificador(request.identificador, empresa_id) if disponible else None

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
        return PasswordResetMensajeResponse(mensaje=_mensaje_solicitud())

    codigo = f"{secrets.randbelow(1_000_000):06d}"
    creado = guardar_token_reset(
        int(usuario["id"]),
        _hashear_codigo(codigo),
        PASSWORD_RESET_TOKEN_MINUTES,
        empresa_id,
        identidad_verificada=usuario,
    )
    if not creado:
        return PasswordResetMensajeResponse(mensaje=_mensaje_solicitud())
    nombre_empresa = empresa["nombre"] if empresa else "Plataforma StyleAR"
    try:
        enviar_correo(
            str(usuario["correo"]),
            f"Codigo de recuperacion - {nombre_empresa}",
            (
                f"Se solicito recuperar una contrasena en {nombre_empresa}.\n\n"
                f"Cuenta: {usuario['username']} ({usuario['correo']})\n"
                f"Codigo: {codigo}\n\n"
                f"Este codigo vence en {PASSWORD_RESET_TOKEN_MINUTES} minutos."
            ),
        )
    except (ValueError, OSError):
        registrar_bitacora(
            usuario_id=int(usuario["id"]),
            accion="SOLICITUD_RESET_PASSWORD",
            modulo="AUTENTICACION",
            resultado="FALLIDO",
            descripcion="No se pudo enviar el correo de recuperación.",
            direccion_ip=direccion_ip,
            user_agent=user_agent,
        )
        raise HTTPException(
            status_code=503,
            detail="No se pudo enviar el correo de recuperación. Intente nuevamente en un minuto.",
        ) from None
    registrar_bitacora(
        usuario_id=int(usuario["id"]),
        accion="SOLICITUD_RESET_PASSWORD",
        modulo="AUTENTICACION",
        resultado="EXITOSO",
        descripcion=("Código de recuperación enviado al correo de recepción configurado."
                     if usa_destino_fijo() else "Código de recuperación enviado al correo registrado."),
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )

    return PasswordResetMensajeResponse(mensaje=_mensaje_solicitud())


def confirmar_reset_password(
    request: ConfirmarPasswordResetRequest,
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> PasswordResetMensajeResponse:
    if request.password_nuevo != request.confirmar_password_nuevo:
        raise HTTPException(status_code=400, detail="Las contrasenas no coinciden.")

    empresa = resolver_empresa_por_codigo(request.empresa_codigo) if request.empresa_codigo else None
    empresa_id = int(empresa["id"]) if empresa else None
    disponible = request.empresa_codigo is None or (empresa is not None and empresa["estado"] in {"ACTIVA", "SUSPENDIDA"})
    usuario = obtener_usuario_por_identificador(request.identificador, empresa_id) if disponible else None

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
        empresa_id,
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
