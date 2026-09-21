from fastapi import HTTPException

from app.core.security import hashear_password
from app.modules.autenticacion.entities.usuario_entity import UsuarioEntity
from app.modules.autenticacion.repositories.bitacora_repository import registrar_bitacora
from app.modules.autenticacion.repositories.usuario_repository import (
    crear_usuario_cliente,
    obtener_usuario_por_correo,
    obtener_usuario_por_username,
)
from app.modules.autenticacion.schemas.usuario.usuario_request import (
    UsuarioRegistroRequest,
)
from app.modules.autenticacion.schemas.usuario.usuario_response import (
    UsuarioRegistroResponse,
)


def registrar_cliente(
    request: UsuarioRegistroRequest,
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> UsuarioRegistroResponse:
    correo = request.correo.strip().lower()
    username = request.username.strip().lower()
    usuario_existente = obtener_usuario_por_correo(correo)

    if usuario_existente is not None:
        raise HTTPException(
            status_code=409,
            detail="El correo ya esta registrado.",
        )

    username_existente = obtener_usuario_por_username(username)

    if username_existente is not None:
        raise HTTPException(
            status_code=409,
            detail="El username ya esta registrado.",
        )

    try:
        password_hash = hashear_password(request.password)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    usuario = UsuarioEntity(
        id=None,
        nombre=request.nombre.strip(),
        apellido=request.apellido.strip(),
        username=username,
        correo=correo,
        password_hash=password_hash,
    )

    try:
        usuario_creado = crear_usuario_cliente(usuario, request.telefono)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    registrar_bitacora(
        usuario_id=int(usuario_creado["id"]),
        accion="REGISTRO",
        modulo="USUARIOS",
        resultado="EXITOSO",
        descripcion=f"Nuevo cliente registrado: {str(usuario_creado['username'])}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )

    return UsuarioRegistroResponse(
        id=int(usuario_creado["id"]),
        nombre=str(usuario_creado["nombre"]),
        apellido=str(usuario_creado["apellido"]),
        username=str(usuario_creado["username"]),
        correo=str(usuario_creado["correo"]),
        rol=str(usuario_creado["rol"]),
        mensaje="Cliente registrado correctamente.",
    )
