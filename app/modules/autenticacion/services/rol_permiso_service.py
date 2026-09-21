from fastapi import HTTPException

from app.modules.autenticacion.repositories.bitacora_repository import registrar_bitacora

from app.modules.autenticacion.repositories.rol_permiso_repository import (
    actualizar_rol,
    activar_permiso,
    activar_permiso_de_rol,
    activar_rol,
    asignar_permiso_a_rol,
    crear_permiso,
    crear_rol,
    desactivar_permiso,
    desactivar_permiso_de_rol,
    desactivar_rol,
    listar_permisos,
    listar_permisos_de_rol,
    listar_roles,
    obtener_permiso_por_id,
    obtener_permiso_por_modulo_accion,
    obtener_permiso_por_nombre,
    obtener_rol_por_id,
    obtener_rol_por_nombre,
    reemplazar_permisos_de_rol,
)
from app.modules.autenticacion.schemas.rol_permiso.rol_permiso_request import (
    ActualizarRolRequest,
    ActualizarPermisosRolRequest,
    CrearPermisoRequest,
    CrearRolRequest,
)
from app.modules.autenticacion.schemas.rol_permiso.rol_permiso_response import (
    MensajeResponse,
    PermisoResponse,
    RolPermisosResponse,
    RolResponse,
)


def obtener_roles() -> list[RolResponse]:
    roles = listar_roles()
    return [construir_rol_response(rol) for rol in roles]


def registrar_rol(
    request: CrearRolRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> RolResponse:
    nombre = request.nombre.strip().upper()
    rol_existente = obtener_rol_por_nombre(nombre)

    if rol_existente is not None:
        raise HTTPException(status_code=409, detail="El rol ya existe.")

    rol = crear_rol(nombre, request.descripcion, int(usuario_actual["id"]))
    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="CREAR",
        modulo="ROLES",
        resultado="EXITOSO",
        descripcion=f"Rol creado: {nombre}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return construir_rol_response(rol)


def editar_rol(
    rol_id: int,
    request: ActualizarRolRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> RolResponse:
    rol_actual = obtener_rol_por_id(rol_id)

    if rol_actual is None or rol_actual["activo"] is not True:
        raise HTTPException(status_code=404, detail="Rol no encontrado.")

    nombre = request.nombre.strip().upper()
    rol_repetido = obtener_rol_por_nombre(nombre)

    if rol_repetido is not None and int(rol_repetido["id"]) != rol_id:
        raise HTTPException(status_code=409, detail="El rol ya existe.")

    rol = actualizar_rol(rol_id, nombre, request.descripcion, int(usuario_actual["id"]))

    if rol is None:
        raise HTTPException(status_code=404, detail="Rol no encontrado.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="ACTUALIZAR",
        modulo="ROLES",
        resultado="EXITOSO",
        descripcion=f"Rol actualizado: id={rol_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return construir_rol_response(rol)


def eliminar_rol(
    rol_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    rol = obtener_rol_por_id(rol_id)

    if rol is None or rol["activo"] is not True:
        raise HTTPException(status_code=404, detail="Rol no encontrado.")

    if str(rol["nombre"]) == "ADMINISTRADOR":
        raise HTTPException(
            status_code=400,
            detail="No se puede desactivar el rol ADMINISTRADOR.",
        )

    desactivado = desactivar_rol(rol_id, int(usuario_actual["id"]))

    if not desactivado:
        raise HTTPException(status_code=404, detail="Rol no encontrado.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="DESACTIVAR",
        modulo="ROLES",
        resultado="EXITOSO",
        descripcion=f"Rol desactivado: id={rol_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return MensajeResponse(mensaje="Rol desactivado correctamente.")


def reactivar_rol(
    rol_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    rol = obtener_rol_por_id(rol_id)

    if rol is None:
        raise HTTPException(status_code=404, detail="Rol no encontrado.")

    activado = activar_rol(rol_id, int(usuario_actual["id"]))

    if not activado:
        raise HTTPException(status_code=404, detail="Rol no encontrado.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="ACTIVAR",
        modulo="ROLES",
        resultado="EXITOSO",
        descripcion=f"Rol activado: id={rol_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return MensajeResponse(mensaje="Rol activado correctamente.")


def obtener_permisos() -> list[PermisoResponse]:
    permisos = listar_permisos()
    return [construir_permiso_response(permiso) for permiso in permisos]


def obtener_permisos_por_rol(rol_id: int) -> RolPermisosResponse:
    rol = obtener_rol_por_id(rol_id)

    if rol is None or rol["activo"] is not True:
        raise HTTPException(status_code=404, detail="Rol no encontrado.")

    permiso_ids = listar_permisos_de_rol(rol_id)

    rol_response = construir_rol_response(
        {
            **rol,
            "cantidad_permisos": len(permiso_ids),
        }
    )
    return RolPermisosResponse(rol=rol_response, permiso_ids=permiso_ids)


def actualizar_permisos_por_rol(
    rol_id: int,
    request: ActualizarPermisosRolRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> RolPermisosResponse:
    rol = obtener_rol_por_id(rol_id)

    if rol is None or rol["activo"] is not True:
        raise HTTPException(status_code=404, detail="Rol no encontrado.")

    try:
        permiso_ids = reemplazar_permisos_de_rol(
            rol_id,
            request.permiso_ids,
            int(usuario_actual["id"]),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="ACTUALIZAR_PERMISOS",
        modulo="ROLES",
        resultado="EXITOSO",
        descripcion=f"Permisos actualizados para rol id={rol_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    rol_response = construir_rol_response(
        {
            **rol,
            "cantidad_permisos": len(permiso_ids),
        }
    )
    return RolPermisosResponse(rol=rol_response, permiso_ids=permiso_ids)


def registrar_permiso(
    request: CrearPermisoRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> PermisoResponse:
    nombre = request.nombre.strip()
    modulo = request.modulo.strip().upper().replace(" ", "_")
    accion = request.accion.strip().lower()

    permiso_por_nombre = obtener_permiso_por_nombre(nombre)

    if permiso_por_nombre is not None:
        raise HTTPException(status_code=409, detail="El permiso ya existe.")

    permiso_por_modulo_accion = obtener_permiso_por_modulo_accion(modulo, accion)

    if permiso_por_modulo_accion is not None:
        raise HTTPException(status_code=409, detail="El permiso ya existe.")

    permiso = crear_permiso(
        nombre,
        modulo,
        accion,
        request.descripcion,
        int(usuario_actual["id"]),
    )
    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="CREAR",
        modulo="PERMISOS",
        resultado="EXITOSO",
        descripcion=f"Permiso creado: {nombre}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return construir_permiso_response(permiso)


def eliminar_permiso(
    permiso_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    permiso = obtener_permiso_por_id(permiso_id)

    if permiso is None or permiso["activo"] is not True:
        raise HTTPException(status_code=404, detail="Permiso no encontrado.")

    desactivado = desactivar_permiso(permiso_id, int(usuario_actual["id"]))

    if not desactivado:
        raise HTTPException(status_code=404, detail="Permiso no encontrado.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="DESACTIVAR",
        modulo="PERMISOS",
        resultado="EXITOSO",
        descripcion=f"Permiso desactivado: id={permiso_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return MensajeResponse(mensaje="Permiso desactivado correctamente.")


def reactivar_permiso(
    permiso_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    permiso = obtener_permiso_por_id(permiso_id)

    if permiso is None:
        raise HTTPException(status_code=404, detail="Permiso no encontrado.")

    activado = activar_permiso(permiso_id, int(usuario_actual["id"]))

    if not activado:
        raise HTTPException(status_code=404, detail="Permiso no encontrado.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="ACTIVAR",
        modulo="PERMISOS",
        resultado="EXITOSO",
        descripcion=f"Permiso activado: id={permiso_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return MensajeResponse(mensaje="Permiso activado correctamente.")


def asignar_permiso(
    rol_id: int,
    permiso_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    rol = obtener_rol_por_id(rol_id)

    if rol is None or rol["activo"] is not True:
        raise HTTPException(status_code=404, detail="Rol no encontrado.")

    permiso = obtener_permiso_por_id(permiso_id)

    if permiso is None or permiso["activo"] is not True:
        raise HTTPException(status_code=404, detail="Permiso no encontrado.")

    asignar_permiso_a_rol(rol_id, permiso_id, int(usuario_actual["id"]))
    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="ASIGNAR_PERMISO",
        modulo="ROLES",
        resultado="EXITOSO",
        descripcion=f"Permiso id={permiso_id} asignado a rol id={rol_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return MensajeResponse(mensaje="Permiso asignado correctamente.")


def quitar_permiso(
    rol_id: int,
    permiso_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    rol = obtener_rol_por_id(rol_id)

    if rol is None or rol["activo"] is not True:
        raise HTTPException(status_code=404, detail="Rol no encontrado.")

    permiso = obtener_permiso_por_id(permiso_id)

    if permiso is None or permiso["activo"] is not True:
        raise HTTPException(status_code=404, detail="Permiso no encontrado.")

    desactivado = desactivar_permiso_de_rol(
        rol_id,
        permiso_id,
        int(usuario_actual["id"]),
    )

    if not desactivado:
        raise HTTPException(status_code=404, detail="Relacion rol-permiso no encontrada.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="QUITAR_PERMISO",
        modulo="ROLES",
        resultado="EXITOSO",
        descripcion=f"Permiso id={permiso_id} quitado de rol id={rol_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return MensajeResponse(mensaje="Permiso quitado del rol correctamente.")


def reactivar_permiso_rol(
    rol_id: int,
    permiso_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    rol = obtener_rol_por_id(rol_id)

    if rol is None or rol["activo"] is not True:
        raise HTTPException(status_code=404, detail="Rol no encontrado.")

    permiso = obtener_permiso_por_id(permiso_id)

    if permiso is None or permiso["activo"] is not True:
        raise HTTPException(status_code=404, detail="Permiso no encontrado.")

    activar_permiso_de_rol(rol_id, permiso_id, int(usuario_actual["id"]))
    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="ACTIVAR_PERMISO",
        modulo="ROLES",
        resultado="EXITOSO",
        descripcion=f"Permiso id={permiso_id} activado en rol id={rol_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return MensajeResponse(mensaje="Permiso activado en el rol correctamente.")


def construir_rol_response(rol: dict[str, object]) -> RolResponse:
    return RolResponse(
        id=int(rol["id"]),
        nombre=str(rol["nombre"]),
        descripcion=None if rol["descripcion"] is None else str(rol["descripcion"]),
        activo=bool(rol["activo"]),
        cantidad_permisos=int(rol.get("cantidad_permisos", 0) or 0),
    )


def construir_permiso_response(permiso: dict[str, object]) -> PermisoResponse:
    return PermisoResponse(
        id=int(permiso["id"]),
        nombre=str(permiso["nombre"]),
        modulo=str(permiso["modulo"]),
        accion=str(permiso["accion"]),
        descripcion=(
            None if permiso["descripcion"] is None else str(permiso["descripcion"])
        ),
        activo=bool(permiso["activo"]),
    )
