from app.modules.administracion.repositories.clasificacion_repository import escribir_clasificacion
from fastapi import HTTPException
from app.core.contexto_empresa import exigir_empresa_id
from app.modules.administracion.repositories.coleccion_repository import listar_colecciones, obtener_coleccion_por_id
from app.modules.administracion.schemas.catalogo.coleccion_request import ActualizarColeccionRequest, CrearColeccionRequest
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

def obtener_colecciones(usuario_actual: dict[str, object]) -> list[ColeccionDetalleResponse]:
    colecciones = listar_colecciones(exigir_empresa_id(usuario_actual))
    return [construir_coleccion_response(c) for c in colecciones]

def obtener_coleccion(coleccion_id: int, usuario_actual: dict[str, object]) -> ColeccionDetalleResponse:
    coleccion = obtener_coleccion_por_id(coleccion_id, exigir_empresa_id(usuario_actual))
    if coleccion is None:
        raise HTTPException(status_code=404, detail="Colección no encontrada.")
    return construir_coleccion_response(coleccion)

def registrar_coleccion(
    request: CrearColeccionRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> ColeccionDetalleResponse:
    fila = escribir_clasificacion('coleccion', usuario_actual, registro_id=None, ip=direccion_ip, ua=user_agent, datos=request.model_dump())
    return construir_coleccion_response(fila)

def editar_coleccion(
    coleccion_id: int,
    request: ActualizarColeccionRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> ColeccionDetalleResponse:
    fila = escribir_clasificacion('coleccion', usuario_actual, registro_id=coleccion_id, ip=direccion_ip, ua=user_agent, datos=request.model_dump())
    return construir_coleccion_response(fila)

def eliminar_coleccion(
    coleccion_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    fila = escribir_clasificacion('coleccion', usuario_actual, registro_id=coleccion_id, ip=direccion_ip, ua=user_agent, activo=False)
    return MensajeResponse(mensaje="Clasificación desactivada correctamente.")

def reactivar_coleccion(
    coleccion_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> ColeccionDetalleResponse:
    fila = escribir_clasificacion('coleccion', usuario_actual, registro_id=coleccion_id, ip=direccion_ip, ua=user_agent, activo=True)
    return construir_coleccion_response(fila)
