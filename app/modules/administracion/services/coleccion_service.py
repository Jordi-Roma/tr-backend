from fastapi import HTTPException
from app.modules.autenticacion.repositories.bitacora_repository import registrar_bitacora
from app.modules.administracion.repositories.coleccion_repository import (
    actualizar_coleccion,
    cambiar_estado_coleccion,
    crear_coleccion,
    listar_colecciones,
    obtener_coleccion_por_id,
    obtener_coleccion_por_temporada_nombre,
)
from app.modules.administracion.repositories.temporada_repository import obtener_temporada_por_id
from app.modules.administracion.schemas.catalogo.coleccion_request import (
    ActualizarColeccionRequest,
    CrearColeccionRequest,
)
from app.modules.administracion.schemas.catalogo.coleccion_response import ColeccionDetalleResponse
from app.modules.administracion.schemas.catalogo.catalogo_response import MensajeResponse

def construir_coleccion_response(row: dict[str, object]) -> ColeccionDetalleResponse:
    return ColeccionDetalleResponse(
        id=int(row["id"]),
        temporada_id=int(row["temporada_id"]),
        temporada_nombre=str(row["temporada_nombre"]),
        nombre=str(row["nombre"]),
        descripcion=str(row["descripcion"]) if row["descripcion"] else None,
        activo=bool(row["activo"]),
        fecha_creacion=row["fecha_creacion"]
    )

def obtener_colecciones() -> list[ColeccionDetalleResponse]:
    colecciones = listar_colecciones()
    return [construir_coleccion_response(c) for c in colecciones]

def obtener_coleccion(coleccion_id: int) -> ColeccionDetalleResponse:
    coleccion = obtener_coleccion_por_id(coleccion_id)
    if coleccion is None:
        raise HTTPException(status_code=404, detail="Colección no encontrada.")
    return construir_coleccion_response(coleccion)

def registrar_coleccion(
    request: CrearColeccionRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> ColeccionDetalleResponse:
    temporada = obtener_temporada_por_id(request.temporada_id)
    if temporada is None:
        raise HTTPException(status_code=400, detail="La temporada seleccionada no existe.")
    if not temporada["activo"]:
        raise HTTPException(status_code=400, detail="La temporada seleccionada está inactiva.")

    if obtener_coleccion_por_temporada_nombre(request.temporada_id, request.nombre) is not None:
        raise HTTPException(
            status_code=409,
            detail="Ya existe una colección con ese nombre en esta temporada.",
        )
    coleccion = crear_coleccion(
        temporada_id=request.temporada_id,
        nombre=request.nombre.strip(),
        descripcion=request.descripcion,
    )
    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="CREAR",
        modulo="COLECCIONES",
        resultado="EXITOSO",
        descripcion=f"Coleccion creada: {request.nombre.strip()}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return obtener_coleccion(int(coleccion["id"]))

def editar_coleccion(
    coleccion_id: int,
    request: ActualizarColeccionRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> ColeccionDetalleResponse:
    actual = obtener_coleccion_por_id(coleccion_id)
    if actual is None:
        raise HTTPException(status_code=404, detail="Colección no encontrada.")

    if actual["temporada_id"] != request.temporada_id:
        temporada = obtener_temporada_por_id(request.temporada_id)
        if temporada is None:
            raise HTTPException(status_code=400, detail="La nueva temporada seleccionada no existe.")
        if not temporada["activo"]:
            raise HTTPException(status_code=400, detail="La nueva temporada seleccionada está inactiva.")

    existente = obtener_coleccion_por_temporada_nombre(request.temporada_id, request.nombre)
    if existente is not None and int(existente["id"]) != coleccion_id:
        raise HTTPException(
            status_code=409,
            detail="Ya existe otra colección con ese nombre en esta temporada.",
        )

    coleccion = actualizar_coleccion(
        coleccion_id=coleccion_id,
        temporada_id=request.temporada_id,
        nombre=request.nombre.strip(),
        descripcion=request.descripcion,
    )
    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="ACTUALIZAR",
        modulo="COLECCIONES",
        resultado="EXITOSO",
        descripcion=f"Coleccion actualizada: id={coleccion_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return obtener_coleccion(int(coleccion["id"]))

def eliminar_coleccion(
    coleccion_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    actual = obtener_coleccion_por_id(coleccion_id)
    if actual is None:
        raise HTTPException(status_code=404, detail="Colección no encontrada.")

    if not actual["activo"]:
        raise HTTPException(status_code=400, detail="La colección ya está inactiva.")

    cambiar_estado_coleccion(coleccion_id, False)
    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="DESACTIVAR",
        modulo="COLECCIONES",
        resultado="EXITOSO",
        descripcion=f"Coleccion desactivada: id={coleccion_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return MensajeResponse(mensaje="Colección desactivada exitosamente.")

def reactivar_coleccion(
    coleccion_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> ColeccionDetalleResponse:
    actual = obtener_coleccion_por_id(coleccion_id)
    if actual is None:
        raise HTTPException(status_code=404, detail="Colección no encontrada.")

    if actual["activo"]:
        raise HTTPException(status_code=400, detail="La colección ya está activa.")

    coleccion = cambiar_estado_coleccion(coleccion_id, True)
    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="ACTIVAR",
        modulo="COLECCIONES",
        resultado="EXITOSO",
        descripcion=f"Coleccion activada: id={coleccion_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return obtener_coleccion(int(coleccion["id"]))
