from app.modules.administracion.repositories import catalogo_comercial_repository as comercial
from fastapi import (
    HTTPException,
)
from app.core.contexto_empresa import (
    exigir_empresa_id,
)
from app.modules.administracion.repositories.variante_repository import (
    listar_variantes,
    obtener_variante_por_id,
)
from app.modules.administracion.schemas.variante.variante_request import (
    ActualizarVarianteRequest,
    CrearVarianteRequest,
    AsignarPrecioRequest,
)
from app.modules.administracion.schemas.variante.variante_response import (
    PrecioResponse,
    VarianteResponse,
)
from app.modules.administracion.schemas.catalogo.catalogo_response import (
    MensajeResponse,
)

def obtener_variantes(usuario_actual: dict[str, object], producto_id: int | None = None) -> list[VarianteResponse]:
    variantes = listar_variantes(exigir_empresa_id(usuario_actual), producto_id)
    return [construir_variante_response(v) for v in variantes]

def obtener_variante(variante_id: int, usuario_actual: dict[str, object]) -> VarianteResponse:
    variante = obtener_variante_por_id(variante_id, exigir_empresa_id(usuario_actual))
    if not variante:
        raise HTTPException(status_code=404, detail="Variante no encontrada.")
    return construir_variante_response(variante)

def registrar_variante(
    request: CrearVarianteRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> VarianteResponse:
    
    rid = comercial.guardar_variante(usuario_actual, request.model_dump(), ip=direccion_ip, ua=user_agent)
    return obtener_variante(rid, usuario_actual)

def editar_variante(
    variante_id: int,
    request: ActualizarVarianteRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> VarianteResponse:
    rid = comercial.guardar_variante(usuario_actual, request.model_dump(), variante_id, ip=direccion_ip, ua=user_agent)
    return obtener_variante(rid, usuario_actual)

def eliminar_variante(
    variante_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    comercial.estado_variante(usuario_actual, variante_id, False, ip=direccion_ip, ua=user_agent)
    return MensajeResponse(mensaje="Registro desactivado; su historial se conserva.")

def reactivar_variante(
    variante_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> VarianteResponse:
    comercial.estado_variante(usuario_actual, variante_id, True, ip=direccion_ip, ua=user_agent)
    return obtener_variante(variante_id, usuario_actual)

def registrar_precio(
    variante_id: int,
    request: AsignarPrecioRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> VarianteResponse:
    comercial.guardar_precio(usuario_actual, variante_id, request.model_dump(), direccion_ip, user_agent)
    return obtener_variante(variante_id, usuario_actual)

def construir_variante_response(variante: dict[str, object]) -> VarianteResponse:
    precios = [
        PrecioResponse(
            id=int(p["id"]),
            variante_id=int(p["variante_id"]),
            monto=p["monto"],
            fecha_inicio=p["fecha_inicio"],
            fecha_fin=p["fecha_fin"] if p["fecha_fin"] else None,
            activo=bool(p["activo"]),
            fecha_creacion=p["fecha_creacion"]
        )
        for p in variante["precios"]
    ]
    
    return VarianteResponse(
        id=int(variante["id"]),
        producto_id=int(variante["producto_id"]),
        producto_nombre=str(variante["producto_nombre"]),
        talla_id=int(variante["talla_id"]) if variante.get("talla_id") else None,
        talla_nombre=str(variante["talla_nombre"]) if variante.get("talla_nombre") else None,
        color_id=int(variante["color_id"]) if variante.get("color_id") else None,
        color_nombre=str(variante["color_nombre"]) if variante.get("color_nombre") else None,
        sku=str(variante["sku"]),
        ancho_cm=float(variante["ancho_cm"]) if variante.get("ancho_cm") is not None else None,
        largo_cm=float(variante["largo_cm"]) if variante.get("largo_cm") is not None else None,
        activo=bool(variante["activo"]),
        fecha_creacion=variante["fecha_creacion"],
        precios=precios
    )
