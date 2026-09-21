from fastapi import HTTPException
from app.modules.autenticacion.repositories.bitacora_repository import registrar_bitacora
from app.modules.administracion.repositories.variante_repository import (
    actualizar_variante,
    asignar_precio,
    crear_variante,
    desactivar_variante,
    activar_variante,
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
from app.modules.administracion.schemas.catalogo.catalogo_response import MensajeResponse
from app.modules.administracion.repositories.producto_repository import obtener_producto_por_id

def obtener_variantes(producto_id: int | None = None) -> list[VarianteResponse]:
    variantes = listar_variantes(producto_id)
    return [construir_variante_response(v) for v in variantes]

def obtener_variante(variante_id: int) -> VarianteResponse:
    variante = obtener_variante_por_id(variante_id)
    if not variante:
        raise HTTPException(status_code=404, detail="Variante no encontrada.")
    return construir_variante_response(variante)

def registrar_variante(
    request: CrearVarianteRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> VarianteResponse:
    
    producto = obtener_producto_por_id(request.producto_id)
    if not producto:
        raise HTTPException(status_code=404, detail="El producto asociado no existe.")
        
    variante_id = crear_variante(
        producto_id=request.producto_id,
        talla_id=request.talla_id,
        color_id=request.color_id,
        sku=request.sku.strip(),
        ancho_cm=request.ancho_cm,
        largo_cm=request.largo_cm
    )

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="CREAR",
        modulo="VARIANTES",
        resultado="EXITOSO",
        descripcion=f"Variante creada: SKU={request.sku.strip()}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return obtener_variante(variante_id)

def editar_variante(
    variante_id: int,
    request: ActualizarVarianteRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> VarianteResponse:
    actual = obtener_variante_por_id(variante_id)
    if not actual:
        raise HTTPException(status_code=404, detail="Variante no encontrada.")

    actualizado = actualizar_variante(
        variante_id=variante_id,
        talla_id=request.talla_id,
        color_id=request.color_id,
        sku=request.sku.strip(),
        ancho_cm=request.ancho_cm,
        largo_cm=request.largo_cm
    )

    if not actualizado:
        raise HTTPException(status_code=404, detail="Variante no encontrada.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="ACTUALIZAR",
        modulo="VARIANTES",
        resultado="EXITOSO",
        descripcion=f"Variante actualizada: id={variante_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return obtener_variante(variante_id)

def eliminar_variante(
    variante_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    actual = obtener_variante_por_id(variante_id)
    if not actual or not actual["activo"]:
        raise HTTPException(status_code=404, detail="Variante no encontrada o ya desactivada.")

    if not desactivar_variante(variante_id):
        raise HTTPException(status_code=404, detail="No se pudo desactivar la variante.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="DESACTIVAR",
        modulo="VARIANTES",
        resultado="EXITOSO",
        descripcion=f"Variante desactivada: id={variante_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return MensajeResponse(mensaje="Variante desactivada correctamente.")

def reactivar_variante(
    variante_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> VarianteResponse:
    actual = obtener_variante_por_id(variante_id)
    if not actual:
        raise HTTPException(status_code=404, detail="Variante no encontrada.")

    if not activar_variante(variante_id):
        raise HTTPException(status_code=404, detail="No se pudo reactivar la variante.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="ACTIVAR",
        modulo="VARIANTES",
        resultado="EXITOSO",
        descripcion=f"Variante activada: id={variante_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return obtener_variante(variante_id)

def registrar_precio(
    variante_id: int,
    request: AsignarPrecioRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> VarianteResponse:
    actual = obtener_variante_por_id(variante_id)
    if not actual:
        raise HTTPException(status_code=404, detail="Variante no encontrada.")

    asignar_precio(
        variante_id=variante_id,
        monto=request.monto,
        fecha_inicio=request.fecha_inicio,
        fecha_fin=request.fecha_fin
    )

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="ASIGNAR_PRECIO",
        modulo="VARIANTES",
        resultado="EXITOSO",
        descripcion=f"Precio asignado a variante id={variante_id}: monto={request.monto}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return obtener_variante(variante_id)

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
