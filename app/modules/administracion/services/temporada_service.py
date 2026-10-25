from app.modules.administracion.repositories.clasificacion_repository import escribir_clasificacion
from fastapi import HTTPException
from app.core.contexto_empresa import exigir_empresa_id
from app.modules.administracion.repositories.temporada_repository import listar_temporadas, obtener_temporada_por_id
from app.modules.administracion.schemas.catalogo.temporada_request import ActualizarTemporadaRequest, CrearTemporadaRequest
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

def obtener_temporadas(usuario_actual: dict[str, object]) -> list[TemporadaResponse]:
    temporadas = listar_temporadas(exigir_empresa_id(usuario_actual))
    return [construir_temporada_response(t) for t in temporadas]

def obtener_temporada(temporada_id: int, usuario_actual: dict[str, object]) -> TemporadaResponse:
    temporada = obtener_temporada_por_id(temporada_id, exigir_empresa_id(usuario_actual))
    if temporada is None:
        raise HTTPException(status_code=404, detail="Temporada no encontrada.")
    return construir_temporada_response(temporada)

def registrar_temporada(
    request: CrearTemporadaRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> TemporadaResponse:
    fila = escribir_clasificacion('temporada', usuario_actual, registro_id=None, ip=direccion_ip, ua=user_agent, datos=request.model_dump())
    return construir_temporada_response(fila)

def editar_temporada(
    temporada_id: int,
    request: ActualizarTemporadaRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> TemporadaResponse:
    fila = escribir_clasificacion('temporada', usuario_actual, registro_id=temporada_id, ip=direccion_ip, ua=user_agent, datos=request.model_dump())
    return construir_temporada_response(fila)

def eliminar_temporada(
    temporada_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    fila = escribir_clasificacion('temporada', usuario_actual, registro_id=temporada_id, ip=direccion_ip, ua=user_agent, activo=False)
    return MensajeResponse(mensaje="Clasificación desactivada correctamente.")

def reactivar_temporada(
    temporada_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> TemporadaResponse:
    fila = escribir_clasificacion('temporada', usuario_actual, registro_id=temporada_id, ip=direccion_ip, ua=user_agent, activo=True)
    return construir_temporada_response(fila)
