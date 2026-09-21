from fastapi import HTTPException

from app.modules.autenticacion.repositories.bitacora_repository import registrar_bitacora

from app.modules.administracion.repositories.ciudad_sucursal_repository import (
    actualizar_ciudad,
    actualizar_sucursal,
    activar_ciudad,
    activar_sucursal,
    ciudad_tiene_sucursales_activas,
    crear_ciudad,
    crear_sucursal,
    desactivar_ciudad,
    desactivar_sucursal,
    listar_ciudades,
    listar_sucursales,
    obtener_ciudad_por_id,
    obtener_sucursal_por_id,
)
from app.modules.administracion.schemas.ciudad_sucursal.ciudad_sucursal_request import (
    ActualizarCiudadRequest,
    ActualizarSucursalRequest,
    CrearCiudadRequest,
    CrearSucursalRequest,
)
from app.modules.administracion.schemas.ciudad_sucursal.ciudad_sucursal_response import (
    CiudadResponse,
    MensajeResponse,
    SucursalResponse,
)


def obtener_ciudades() -> list[CiudadResponse]:
    ciudades = listar_ciudades()
    return [construir_ciudad_response(ciudad) for ciudad in ciudades]


def obtener_ciudad(ciudad_id: int) -> CiudadResponse:
    ciudad = obtener_ciudad_por_id(ciudad_id)

    if ciudad is None or ciudad["activo"] is not True:
        raise HTTPException(status_code=404, detail="Ciudad no encontrada.")

    return construir_ciudad_response(ciudad)


def registrar_ciudad(
    request: CrearCiudadRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> CiudadResponse:
    ciudad = crear_ciudad(
        request.nombre.strip(),
        request.departamento,
        int(usuario_actual["id"]),
    )
    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="CREAR",
        modulo="CIUDADES",
        resultado="EXITOSO",
        descripcion=f"Ciudad creada: {request.nombre.strip()}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return construir_ciudad_response(ciudad)


def editar_ciudad(
    ciudad_id: int,
    request: ActualizarCiudadRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> CiudadResponse:
    ciudad_actual = obtener_ciudad_por_id(ciudad_id)

    if ciudad_actual is None or ciudad_actual["activo"] is not True:
        raise HTTPException(status_code=404, detail="Ciudad no encontrada.")

    ciudad = actualizar_ciudad(
        ciudad_id,
        request.nombre.strip(),
        request.departamento,
        int(usuario_actual["id"]),
    )

    if ciudad is None:
        raise HTTPException(status_code=404, detail="Ciudad no encontrada.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="ACTUALIZAR",
        modulo="CIUDADES",
        resultado="EXITOSO",
        descripcion=f"Ciudad actualizada: id={ciudad_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return construir_ciudad_response(ciudad)


def eliminar_ciudad(
    ciudad_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    ciudad = obtener_ciudad_por_id(ciudad_id)

    if ciudad is None or ciudad["activo"] is not True:
        raise HTTPException(status_code=404, detail="Ciudad no encontrada.")

    if ciudad_tiene_sucursales_activas(ciudad_id):
        raise HTTPException(
            status_code=400,
            detail="No se puede desactivar una ciudad con sucursales activas.",
        )

    desactivada = desactivar_ciudad(ciudad_id, int(usuario_actual["id"]))

    if not desactivada:
        raise HTTPException(status_code=404, detail="Ciudad no encontrada.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="DESACTIVAR",
        modulo="CIUDADES",
        resultado="EXITOSO",
        descripcion=f"Ciudad desactivada: id={ciudad_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return MensajeResponse(mensaje="Ciudad desactivada correctamente.")


def reactivar_ciudad(
    ciudad_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    ciudad = obtener_ciudad_por_id(ciudad_id)

    if ciudad is None:
        raise HTTPException(status_code=404, detail="Ciudad no encontrada.")

    activada = activar_ciudad(ciudad_id, int(usuario_actual["id"]))

    if not activada:
        raise HTTPException(status_code=404, detail="Ciudad no encontrada.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="ACTIVAR",
        modulo="CIUDADES",
        resultado="EXITOSO",
        descripcion=f"Ciudad activada: id={ciudad_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return MensajeResponse(mensaje="Ciudad activada correctamente.")


def obtener_sucursales() -> list[SucursalResponse]:
    sucursales = listar_sucursales()
    return [construir_sucursal_response(sucursal) for sucursal in sucursales]


def obtener_sucursal(sucursal_id: int) -> SucursalResponse:
    sucursal = obtener_sucursal_por_id(sucursal_id)

    if sucursal is None or sucursal["activo"] is not True:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada.")

    return construir_sucursal_response(sucursal)


def registrar_sucursal(
    request: CrearSucursalRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> SucursalResponse:
    validar_ciudad_activa(request.ciudad_id)
    sucursal = crear_sucursal(
        request.ciudad_id,
        request.nombre.strip(),
        request.direccion.strip(),
        request.telefono,
        request.latitud,
        request.longitud,
        int(usuario_actual["id"]),
    )
    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="CREAR",
        modulo="SUCURSALES",
        resultado="EXITOSO",
        descripcion=f"Sucursal creada: {request.nombre.strip()}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return construir_sucursal_response(sucursal)


def editar_sucursal(
    sucursal_id: int,
    request: ActualizarSucursalRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> SucursalResponse:
    sucursal_actual = obtener_sucursal_por_id(sucursal_id)

    if sucursal_actual is None or sucursal_actual["activo"] is not True:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada.")

    validar_ciudad_activa(request.ciudad_id)
    sucursal = actualizar_sucursal(
        sucursal_id,
        request.ciudad_id,
        request.nombre.strip(),
        request.direccion.strip(),
        request.telefono,
        request.latitud,
        request.longitud,
        int(usuario_actual["id"]),
    )

    if sucursal is None:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="ACTUALIZAR",
        modulo="SUCURSALES",
        resultado="EXITOSO",
        descripcion=f"Sucursal actualizada: id={sucursal_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return construir_sucursal_response(sucursal)


def eliminar_sucursal(
    sucursal_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    sucursal = obtener_sucursal_por_id(sucursal_id)

    if sucursal is None or sucursal["activo"] is not True:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada.")

    desactivada = desactivar_sucursal(sucursal_id, int(usuario_actual["id"]))

    if not desactivada:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="DESACTIVAR",
        modulo="SUCURSALES",
        resultado="EXITOSO",
        descripcion=f"Sucursal desactivada: id={sucursal_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return MensajeResponse(mensaje="Sucursal desactivada correctamente.")


def reactivar_sucursal(
    sucursal_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    sucursal = obtener_sucursal_por_id(sucursal_id)

    if sucursal is None:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada.")

    if sucursal["ciudad_activa"] is not True:
        raise HTTPException(
            status_code=400,
            detail="No se puede activar una sucursal de una ciudad inactiva.",
        )

    activada = activar_sucursal(sucursal_id, int(usuario_actual["id"]))

    if not activada:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="ACTIVAR",
        modulo="SUCURSALES",
        resultado="EXITOSO",
        descripcion=f"Sucursal activada: id={sucursal_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return MensajeResponse(mensaje="Sucursal activada correctamente.")


def validar_ciudad_activa(ciudad_id: int) -> None:
    ciudad = obtener_ciudad_por_id(ciudad_id)

    if ciudad is None or ciudad["activo"] is not True:
        raise HTTPException(
            status_code=400,
            detail="La ciudad no existe o esta inactiva.",
        )


def construir_ciudad_response(ciudad: dict[str, object]) -> CiudadResponse:
    return CiudadResponse(
        id=int(ciudad["id"]),
        nombre=str(ciudad["nombre"]),
        departamento=(
            None if ciudad["departamento"] is None else str(ciudad["departamento"])
        ),
        activo=bool(ciudad["activo"]),
    )


def construir_sucursal_response(sucursal: dict[str, object]) -> SucursalResponse:
    return SucursalResponse(
        id=int(sucursal["id"]),
        ciudad_id=int(sucursal["ciudad_id"]),
        ciudad_nombre=str(sucursal["ciudad_nombre"]),
        nombre=str(sucursal["nombre"]),
        direccion=str(sucursal["direccion"]),
        telefono=None if sucursal["telefono"] is None else str(sucursal["telefono"]),
        latitud=sucursal.get("latitud"),
        longitud=sucursal.get("longitud"),
        activo=bool(sucursal["activo"]),
    )
