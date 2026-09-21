from fastapi import HTTPException
from app.modules.autenticacion.repositories.bitacora_repository import registrar_bitacora
from app.modules.administracion.repositories.temporada_repository import (
    actualizar_temporada,
    cambiar_estado_temporada,
    crear_temporada,
    listar_temporadas,
    obtener_temporada_por_id,
    obtener_temporada_por_nombre_anio,
)
from app.modules.administracion.schemas.catalogo.temporada_request import (
    ActualizarTemporadaRequest,
    CrearTemporadaRequest,
)
from app.modules.administracion.schemas.catalogo.temporada_response import TemporadaResponse
from app.modules.administracion.schemas.catalogo.catalogo_response import MensajeResponse

def construir_temporada_response(row: dict[str, object]) -> TemporadaResponse:
    return TemporadaResponse(
        id=int(row["id"]),
        nombre=str(row["nombre"]),
        anio=int(row["anio"]),
        activo=bool(row["activo"]),
        fecha_creacion=row["fecha_creacion"]
    )

def obtener_temporadas() -> list[TemporadaResponse]:
    temporadas = listar_temporadas()
    return [construir_temporada_response(t) for t in temporadas]

def obtener_temporada(temporada_id: int) -> TemporadaResponse:
    temporada = obtener_temporada_por_id(temporada_id)
    if temporada is None:
        raise HTTPException(status_code=404, detail="Temporada no encontrada.")
    return construir_temporada_response(temporada)

def registrar_temporada(
    request: CrearTemporadaRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> TemporadaResponse:
    if obtener_temporada_por_nombre_anio(request.nombre, request.anio) is not None:
        raise HTTPException(
            status_code=409,
            detail="Ya existe una temporada con ese nombre y año.",
        )
    temporada = crear_temporada(
        nombre=request.nombre.strip(),
        anio=request.anio,
    )
    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="CREAR",
        modulo="TEMPORADAS",
        resultado="EXITOSO",
        descripcion=f"Temporada creada: {request.nombre.strip()} {request.anio}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return construir_temporada_response(temporada)

def editar_temporada(
    temporada_id: int,
    request: ActualizarTemporadaRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> TemporadaResponse:
    actual = obtener_temporada_por_id(temporada_id)
    if actual is None:
        raise HTTPException(status_code=404, detail="Temporada no encontrada.")

    existente = obtener_temporada_por_nombre_anio(request.nombre, request.anio)
    if existente is not None and int(existente["id"]) != temporada_id:
        raise HTTPException(
            status_code=409,
            detail="Ya existe otra temporada con ese nombre y año.",
        )

    temporada = actualizar_temporada(
        temporada_id=temporada_id,
        nombre=request.nombre.strip(),
        anio=request.anio,
    )
    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="ACTUALIZAR",
        modulo="TEMPORADAS",
        resultado="EXITOSO",
        descripcion=f"Temporada actualizada: id={temporada_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return construir_temporada_response(temporada)

def eliminar_temporada(
    temporada_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    actual = obtener_temporada_por_id(temporada_id)
    if actual is None:
        raise HTTPException(status_code=404, detail="Temporada no encontrada.")

    if not actual["activo"]:
        raise HTTPException(status_code=400, detail="La temporada ya está inactiva.")

    cambiar_estado_temporada(temporada_id, False)
    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="DESACTIVAR",
        modulo="TEMPORADAS",
        resultado="EXITOSO",
        descripcion=f"Temporada desactivada: id={temporada_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return MensajeResponse(mensaje="Temporada desactivada exitosamente.")

def reactivar_temporada(
    temporada_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> TemporadaResponse:
    actual = obtener_temporada_por_id(temporada_id)
    if actual is None:
        raise HTTPException(status_code=404, detail="Temporada no encontrada.")

    if actual["activo"]:
        raise HTTPException(status_code=400, detail="La temporada ya está activa.")

    temporada = cambiar_estado_temporada(temporada_id, True)
    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="ACTIVAR",
        modulo="TEMPORADAS",
        resultado="EXITOSO",
        descripcion=f"Temporada activada: id={temporada_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return construir_temporada_response(temporada)
