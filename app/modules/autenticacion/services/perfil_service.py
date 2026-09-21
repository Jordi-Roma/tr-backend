from fastapi import HTTPException

from app.core.security import hashear_password, verificar_password
from app.modules.autenticacion.repositories.bitacora_repository import registrar_bitacora
from app.modules.autenticacion.repositories.perfil_repository import (
    actualizar_direccion_cliente,
    actualizar_password_hash,
    actualizar_perfil_cliente,
    crear_direccion_cliente,
    desactivar_direccion_cliente,
    listar_direcciones_cliente,
    obtener_password_hash,
    obtener_perfil_cliente,
)
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


def obtener_perfil(usuario_actual: dict[str, object]) -> PerfilResponse:
    usuario_id = int(usuario_actual["id"])
    perfil = obtener_perfil_cliente(usuario_id)

    if perfil is None:
        raise HTTPException(status_code=404, detail="Perfil no encontrado.")

    return construir_perfil_response(perfil)


def actualizar_perfil(
    usuario_actual: dict[str, object],
    request: ActualizarPerfilRequest,
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> PerfilResponse:
    usuario_id = int(usuario_actual["id"])
    perfil = actualizar_perfil_cliente(
        usuario_id,
        request.nombre.strip(),
        request.apellido.strip(),
        request.telefono,
    )

    if perfil is None:
        raise HTTPException(status_code=404, detail="Perfil no encontrado.")

    registrar_bitacora(
        usuario_id=usuario_id,
        accion="ACTUALIZAR",
        modulo="PERFIL",
        resultado="EXITOSO",
        descripcion="Perfil actualizado correctamente.",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return construir_perfil_response(perfil)


def cambiar_password(
    usuario_actual: dict[str, object],
    request: CambiarPasswordRequest,
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    usuario_id = int(usuario_actual["id"])

    if request.password_nuevo != request.confirmar_password_nuevo:
        raise HTTPException(
            status_code=400,
            detail="Las contraseñas nuevas no coinciden.",
        )

    password_hash_actual = obtener_password_hash(usuario_id)

    if password_hash_actual is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    if not verificar_password(request.password_actual, password_hash_actual):
        raise HTTPException(
            status_code=400,
            detail="La contraseña actual es incorrecta.",
        )

    try:
        nuevo_password_hash = hashear_password(request.password_nuevo)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    actualizado = actualizar_password_hash(usuario_id, nuevo_password_hash)

    if not actualizado:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    registrar_bitacora(
        usuario_id=usuario_id,
        accion="CAMBIAR_CONTRASENA",
        modulo="PERFIL",
        resultado="EXITOSO",
        descripcion="Contraseña actualizada correctamente.",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return MensajeResponse(mensaje="Contraseña actualizada correctamente.")


def listar_direcciones(usuario_actual: dict[str, object]) -> ListaDireccionesResponse:
    usuario_id = int(usuario_actual["id"])
    direcciones = listar_direcciones_cliente(usuario_id)

    return ListaDireccionesResponse(
        direcciones=[
            construir_direccion_response(direccion) for direccion in direcciones
        ]
    )


def crear_direccion(
    usuario_actual: dict[str, object],
    request: CrearDireccionRequest,
) -> DireccionResponse:
    usuario_id = int(usuario_actual["id"])
    direccion = crear_direccion_cliente(
        usuario_id,
        request.ciudad_id,
        request.direccion.strip(),
        request.referencia,
        request.es_principal,
    )

    if direccion is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")

    return construir_direccion_response(direccion)


def actualizar_direccion(
    usuario_actual: dict[str, object],
    direccion_id: int,
    request: ActualizarDireccionRequest,
) -> DireccionResponse:
    usuario_id = int(usuario_actual["id"])
    direccion = actualizar_direccion_cliente(
        usuario_id,
        direccion_id,
        request.ciudad_id,
        request.direccion.strip(),
        request.referencia,
        request.es_principal,
    )

    if direccion is None:
        raise HTTPException(status_code=404, detail="Direccion no encontrada.")

    return construir_direccion_response(direccion)


def desactivar_direccion(
    usuario_actual: dict[str, object],
    direccion_id: int,
) -> MensajeResponse:
    usuario_id = int(usuario_actual["id"])
    desactivada = desactivar_direccion_cliente(usuario_id, direccion_id)

    if not desactivada:
        raise HTTPException(status_code=404, detail="Direccion no encontrada.")

    return MensajeResponse(mensaje="Direccion desactivada correctamente.")


def construir_perfil_response(perfil: dict[str, object]) -> PerfilResponse:
    return PerfilResponse(
        id=int(perfil["id"]),
        nombre=str(perfil["nombre"]),
        apellido=str(perfil["apellido"]),
        username=str(perfil["username"]),
        correo=str(perfil["correo"]),
        telefono=None if perfil["telefono"] is None else str(perfil["telefono"]),
        roles=[str(rol) for rol in perfil["roles"]],
    )


def construir_direccion_response(direccion: dict[str, object]) -> DireccionResponse:
    return DireccionResponse(
        id=int(direccion["id"]),
        ciudad_id=int(direccion["ciudad_id"]),
        direccion=str(direccion["direccion"]),
        referencia=(
            None if direccion["referencia"] is None else str(direccion["referencia"])
        ),
        es_principal=bool(direccion["es_principal"]),
    )
