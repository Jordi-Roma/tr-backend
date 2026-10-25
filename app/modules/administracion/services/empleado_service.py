from fastapi import HTTPException
from app.modules.autenticacion.dependencies.admin_required import requerir_admin
from app.modules.administracion.repositories.empleado_repository import ROLES_LABORALES
from app.core.contexto_empresa import exigir_empresa_id

from app.core.security import hashear_password
from app.modules.administracion.repositories.empleado_repository import (
    actualizar_empleado,
    activar_empleado,
    crear_empleado_usuario_existente,
    crear_usuario_empleado,
    desactivar_empleado,
    listar_empleados,
    obtener_empleado_activo_por_usuario_id,
    obtener_empleado_por_id,
    obtener_rol_por_nombre,
    obtener_sucursal_por_id,
    obtener_usuario_por_correo,
    obtener_usuario_por_id,
    obtener_usuario_por_username,
    usuario_tiene_empleado_activo,
)
from app.modules.administracion.schemas.empleado.empleado_request import (
    ActivarEmpleadoRequest,
    ActualizarEmpleadoRequest,
    AsignarUsuarioEmpleadoRequest,
    CrearUsuarioEmpleadoRequest,
)
from app.modules.administracion.schemas.empleado.empleado_response import (
    EmpleadoResponse,
    MensajeResponse,
)


def obtener_empleados(usuario_actual: dict[str, object], incluir_inactivos: bool = False) -> list[EmpleadoResponse]:
    sucursal_id = obtener_sucursal_permitida(usuario_actual)
    empleados = listar_empleados(exigir_empresa_id(usuario_actual), sucursal_id, incluir_inactivos)

    return [construir_empleado_response(empleado) for empleado in empleados]


def obtener_empleado(
    empleado_id: int,
    usuario_actual: dict[str, object],
) -> EmpleadoResponse:
    empleado = obtener_empleado_por_id(empleado_id, exigir_empresa_id(usuario_actual))

    if empleado is None:
        raise HTTPException(status_code=404, detail="Empleado no encontrado.")

    validar_acceso_sucursal(usuario_actual, int(empleado["sucursal_id"]))
    return construir_empleado_response(empleado)


def asignar_usuario_empleado(
    request: AsignarUsuarioEmpleadoRequest,
    usuario_actual: dict[str, object],
) -> EmpleadoResponse:
    requerir_admin(usuario_actual)
    validar_acceso_sucursal(usuario_actual, request.sucursal_id)
    empresa_id = exigir_empresa_id(usuario_actual)
    usuario = obtener_usuario_por_id(request.usuario_id, empresa_id)

    if usuario is None or usuario["activo"] is not True:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    validar_sucursal_activa(request.sucursal_id, empresa_id)
    rol = validar_rol_laboral(request.rol)

    if usuario_tiene_empleado_activo(request.usuario_id, empresa_id):
        raise HTTPException(
            status_code=409,
            detail="El usuario ya tiene un empleado activo.",
        )

    empleado = crear_empleado_usuario_existente(
        request.usuario_id,
        request.sucursal_id,
        request.codigo_empleado.strip(),
        request.cargo.strip(),
        int(rol["id"]),
        int(usuario_actual["id"]),
        empresa_id,
    )
    return construir_empleado_response(empleado)


def registrar_usuario_empleado(
    request: CrearUsuarioEmpleadoRequest,
    usuario_actual: dict[str, object],
) -> EmpleadoResponse:
    requerir_admin(usuario_actual)
    roles = [str(rol) for rol in usuario_actual.get("roles", [])]

    if "ADMINISTRADOR" not in roles:
        raise HTTPException(
            status_code=403,
            detail="Solo el administrador puede crear usuarios empleados.",
        )

    username = request.username.strip().lower()
    correo = request.correo.strip().lower()

    if obtener_usuario_por_username(username) is not None:
        raise HTTPException(status_code=409, detail="El username ya esta registrado.")

    if obtener_usuario_por_correo(correo) is not None:
        raise HTTPException(status_code=409, detail="El correo ya esta registrado.")

    empresa_id = exigir_empresa_id(usuario_actual)
    validar_sucursal_activa(request.sucursal_id, empresa_id)
    rol = validar_rol_laboral(request.rol)

    try:
        password_hash = hashear_password(request.password)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    empleado = crear_usuario_empleado(
        request.nombre.strip(),
        request.apellido.strip(),
        username,
        correo,
        password_hash,
        request.sucursal_id,
        request.codigo_empleado.strip(),
        request.cargo.strip(),
        int(rol["id"]),
        int(usuario_actual["id"]),
        empresa_id,
    )
    return construir_empleado_response(empleado)


def editar_empleado(
    empleado_id: int,
    request: ActualizarEmpleadoRequest,
    usuario_actual: dict[str, object],
) -> EmpleadoResponse:
    requerir_admin(usuario_actual)
    empresa_id = exigir_empresa_id(usuario_actual)
    empleado_actual = obtener_empleado_por_id(empleado_id, empresa_id)

    if empleado_actual is None or empleado_actual["activo"] is not True:
        raise HTTPException(status_code=404, detail="Empleado no encontrado.")

    validar_acceso_sucursal(usuario_actual, int(empleado_actual["sucursal_id"]))
    validar_acceso_sucursal(usuario_actual, request.sucursal_id)
    validar_sucursal_activa(request.sucursal_id, empresa_id)
    rol = validar_rol_laboral(request.rol)

    empleado = actualizar_empleado(
        empleado_id,
        request.sucursal_id,
        request.codigo_empleado.strip(),
        request.cargo.strip(),
        int(rol["id"]),
        int(usuario_actual["id"]),
        empresa_id,
    )

    if empleado is None:
        raise HTTPException(status_code=404, detail="Empleado no encontrado.")

    return construir_empleado_response(empleado)


def eliminar_empleado(
    empleado_id: int,
    usuario_actual: dict[str, object],
) -> MensajeResponse:
    requerir_admin(usuario_actual)
    empresa_id = exigir_empresa_id(usuario_actual)
    empleado = obtener_empleado_por_id(empleado_id, empresa_id)

    if empleado is None or empleado["activo"] is not True:
        raise HTTPException(status_code=404, detail="Empleado no encontrado.")

    validar_acceso_sucursal(usuario_actual, int(empleado["sucursal_id"]))
    desactivado = desactivar_empleado(empleado_id, int(usuario_actual["id"]), empresa_id)

    if not desactivado:
        raise HTTPException(status_code=404, detail="Empleado no encontrado.")

    return MensajeResponse(mensaje="Empleado desactivado correctamente.")


def reactivar_empleado(
    empleado_id: int,
    request: ActivarEmpleadoRequest,
    usuario_actual: dict[str, object],
) -> EmpleadoResponse:
    requerir_admin(usuario_actual)
    empresa_id = exigir_empresa_id(usuario_actual)
    empleado_actual = obtener_empleado_por_id(empleado_id, empresa_id)

    if empleado_actual is None:
        raise HTTPException(status_code=404, detail="Empleado no encontrado.")

    validar_acceso_sucursal(usuario_actual, int(empleado_actual["sucursal_id"]))

    usuario = obtener_usuario_por_id(int(empleado_actual["usuario_id"]), empresa_id)

    if usuario is None or usuario["activo"] is not True:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    validar_sucursal_activa(int(empleado_actual["sucursal_id"]), empresa_id)
    rol = validar_rol_laboral(request.rol)

    empleado = activar_empleado(
        empleado_id,
        int(rol["id"]),
        int(usuario_actual["id"]),
        empresa_id,
    )

    if empleado is None:
        raise HTTPException(status_code=404, detail="Empleado no encontrado.")

    return construir_empleado_response(empleado)


def validar_rol_laboral(nombre_rol: str) -> dict[str, object]:
    rol_nombre = nombre_rol.strip().upper()

    if rol_nombre not in ROLES_LABORALES:
        raise HTTPException(
            status_code=400,
            detail="Solo se permiten CAJERO, ENCARGADO_SUCURSAL y PERSONAL_VENTAS desde empleados.",
        )

    rol = obtener_rol_por_nombre(rol_nombre)

    if rol is None or rol["activo"] is not True:
        raise HTTPException(status_code=404, detail="Rol no encontrado.")

    return rol


def validar_sucursal_activa(sucursal_id: int, empresa_id: int) -> None:
    sucursal = obtener_sucursal_por_id(sucursal_id, empresa_id)

    if sucursal is None or sucursal["activo"] is not True:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada.")


def obtener_sucursal_permitida(usuario_actual: dict[str, object]) -> int | None:
    roles = [str(rol) for rol in usuario_actual.get("roles", [])]

    if "ADMINISTRADOR" in roles:
        return None

    empleado = obtener_empleado_activo_por_usuario_id(int(usuario_actual["id"]), exigir_empresa_id(usuario_actual))

    if empleado is None:
        raise HTTPException(
            status_code=403,
            detail="El encargado no tiene una sucursal activa asignada.",
        )

    return int(empleado["sucursal_id"])


def validar_acceso_sucursal(
    usuario_actual: dict[str, object],
    sucursal_id: int,
) -> None:
    sucursal_permitida = obtener_sucursal_permitida(usuario_actual)

    if sucursal_permitida is not None and sucursal_permitida != sucursal_id:
        raise HTTPException(
            status_code=403,
            detail="Solo puede gestionar empleados de su sucursal.",
        )


def construir_empleado_response(empleado: dict[str, object]) -> EmpleadoResponse:
    return EmpleadoResponse(
        empleado_id=int(empleado["empleado_id"]),
        usuario_id=int(empleado["usuario_id"]),
        nombre=str(empleado["nombre"]),
        apellido=str(empleado["apellido"]),
        username=str(empleado["username"]),
        correo=str(empleado["correo"]),
        sucursal_id=int(empleado["sucursal_id"]),
        sucursal_nombre=str(empleado["sucursal_nombre"]),
        codigo_empleado=str(empleado["codigo_empleado"]),
        cargo=str(empleado["cargo"]),
        fecha_ingreso=empleado["fecha_ingreso"],
        activo=bool(empleado["activo"]),
        roles=[str(rol) for rol in empleado["roles"]],
        rol_laboral=empleado.get("rol_laboral"),
    )
