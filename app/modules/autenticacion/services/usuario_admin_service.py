from fastapi import HTTPException

from app.modules.autenticacion.repositories.bitacora_repository import registrar_bitacora
from app.core.security import hashear_password

from app.modules.autenticacion.repositories.usuario_admin_repository import (
    actualizar_usuario,
    crear_usuario_con_rol,
    activar_rol_de_usuario,
    activar_usuario,
    asignar_rol_a_usuario,
    desactivar_rol_de_usuario,
    desactivar_usuario,
    listar_usuarios,
    obtener_rol_por_id,
    obtener_usuario_admin_por_id,
    obtener_usuario_por_correo,
    obtener_usuario_por_username,
)
from app.modules.autenticacion.schemas.usuario_admin.usuario_admin_request import (
    ActualizarUsuarioRequest,
    CrearUsuarioAdminRequest,
)
from app.modules.autenticacion.schemas.usuario_admin.usuario_admin_response import (
    MensajeResponse,
    UsuarioAdminResponse,
)


def obtener_usuarios() -> list[UsuarioAdminResponse]:
    usuarios = listar_usuarios()
    return [construir_usuario_response(usuario) for usuario in usuarios]


def registrar_usuario(
    request: CrearUsuarioAdminRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> UsuarioAdminResponse:
    username = request.username.strip().lower()
    correo = request.correo.strip().lower()

    if obtener_usuario_por_username(username) is not None:
        raise HTTPException(status_code=409, detail="El username ya esta registrado.")
    if obtener_usuario_por_correo(correo) is not None:
        raise HTTPException(status_code=409, detail="El correo ya esta registrado.")

    rol = obtener_rol_por_id(request.rol_id)
    if rol is None or rol["activo"] is not True:
        raise HTTPException(status_code=404, detail="Rol no encontrado.")

    try:
        password_hash = hashear_password(request.password)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    usuario = crear_usuario_con_rol(
        request.nombre.strip(),
        request.apellido.strip(),
        username,
        correo,
        password_hash,
        request.rol_id,
        str(rol["nombre"]),
        request.telefono,
        int(usuario_actual["id"]),
    )
    return construir_usuario_response(usuario)


def obtener_usuario(usuario_id: int) -> UsuarioAdminResponse:
    usuario = obtener_usuario_admin_por_id(usuario_id)

    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    return construir_usuario_response(usuario)


def editar_usuario(
    usuario_id: int,
    request: ActualizarUsuarioRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> UsuarioAdminResponse:
    usuario = obtener_usuario_admin_por_id(usuario_id)

    if usuario is None or usuario["activo"] is not True:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    username = request.username.strip().lower()
    correo = request.correo.strip().lower()

    usuario_username = obtener_usuario_por_username(username)

    if usuario_username is not None and int(usuario_username["id"]) != usuario_id:
        raise HTTPException(status_code=409, detail="El username ya esta registrado.")

    usuario_correo = obtener_usuario_por_correo(correo)

    if usuario_correo is not None and int(usuario_correo["id"]) != usuario_id:
        raise HTTPException(status_code=409, detail="El correo ya esta registrado.")

    usuario_actualizado = actualizar_usuario(
        usuario_id,
        request.nombre.strip(),
        request.apellido.strip(),
        username,
        correo,
        int(usuario_actual["id"]),
    )

    if usuario_actualizado is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="ACTUALIZAR",
        modulo="USUARIOS",
        resultado="EXITOSO",
        descripcion=f"Usuario actualizado: id={usuario_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return construir_usuario_response(usuario_actualizado)


def eliminar_usuario(
    usuario_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    usuario_admin_id = int(usuario_actual["id"])

    if usuario_id == usuario_admin_id:
        raise HTTPException(
            status_code=400,
            detail="No puede desactivar su propio usuario.",
        )

    usuario = obtener_usuario_admin_por_id(usuario_id)

    if usuario is None or usuario["activo"] is not True:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    desactivado = desactivar_usuario(usuario_id, usuario_admin_id)

    if not desactivado:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="DESACTIVAR",
        modulo="USUARIOS",
        resultado="EXITOSO",
        descripcion=f"Usuario desactivado: id={usuario_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return MensajeResponse(mensaje="Usuario desactivado correctamente.")


def reactivar_usuario(
    usuario_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    usuario = obtener_usuario_admin_por_id(usuario_id)

    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    activado = activar_usuario(usuario_id, int(usuario_actual["id"]))

    if not activado:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="ACTIVAR",
        modulo="USUARIOS",
        resultado="EXITOSO",
        descripcion=f"Usuario activado: id={usuario_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return MensajeResponse(mensaje="Usuario activado correctamente.")


def asignar_rol_usuario(
    usuario_id: int,
    rol_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    usuario = obtener_usuario_admin_por_id(usuario_id)

    if usuario is None or usuario["activo"] is not True:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    rol = obtener_rol_por_id(rol_id)

    if rol is None or rol["activo"] is not True:
        raise HTTPException(status_code=404, detail="Rol no encontrado.")

    asignar_rol_a_usuario(usuario_id, rol_id, int(usuario_actual["id"]))
    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="ASIGNAR_ROL",
        modulo="USUARIOS",
        resultado="EXITOSO",
        descripcion=f"Rol id={rol_id} asignado a usuario id={usuario_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return MensajeResponse(mensaje="Rol asignado correctamente.")


def desactivar_rol_usuario(
    usuario_id: int,
    rol_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    usuario_admin_id = int(usuario_actual["id"])
    usuario = obtener_usuario_admin_por_id(usuario_id)

    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    rol = obtener_rol_por_id(rol_id)

    if rol is None:
        raise HTTPException(status_code=404, detail="Rol no encontrado.")

    if usuario_id == usuario_admin_id and str(rol["nombre"]) == "ADMINISTRADOR":
        raise HTTPException(
            status_code=400,
            detail="No puede quitarse a si mismo el rol ADMINISTRADOR.",
        )

    desactivado = desactivar_rol_de_usuario(usuario_id, rol_id, usuario_admin_id)

    if not desactivado:
        raise HTTPException(
            status_code=404,
            detail="Relacion usuario-rol no encontrada.",
        )

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="DESACTIVAR_ROL",
        modulo="USUARIOS",
        resultado="EXITOSO",
        descripcion=f"Rol id={rol_id} desactivado de usuario id={usuario_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return MensajeResponse(mensaje="Rol desactivado del usuario correctamente.")


def activar_rol_usuario(
    usuario_id: int,
    rol_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    usuario = obtener_usuario_admin_por_id(usuario_id)

    if usuario is None or usuario["activo"] is not True:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    rol = obtener_rol_por_id(rol_id)

    if rol is None or rol["activo"] is not True:
        raise HTTPException(status_code=404, detail="Rol no encontrado.")

    activar_rol_de_usuario(usuario_id, rol_id, int(usuario_actual["id"]))
    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="ACTIVAR_ROL",
        modulo="USUARIOS",
        resultado="EXITOSO",
        descripcion=f"Rol id={rol_id} activado en usuario id={usuario_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return MensajeResponse(mensaje="Rol activado del usuario correctamente.")


def construir_usuario_response(usuario: dict[str, object]) -> UsuarioAdminResponse:
    return UsuarioAdminResponse(
        id=int(usuario["id"]),
        nombre=str(usuario["nombre"]),
        apellido=str(usuario["apellido"]),
        username=str(usuario["username"]),
        correo=str(usuario["correo"]),
        activo=bool(usuario["activo"]),
        roles=[str(rol) for rol in usuario["roles"]],
        es_cliente=bool(usuario["es_cliente"]),
        es_empleado=bool(usuario["es_empleado"]),
    )
