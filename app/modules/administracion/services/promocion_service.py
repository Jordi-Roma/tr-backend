from fastapi import HTTPException
from app.core.contexto_empresa import exigir_empresa_id

from app.modules.administracion.repositories.producto_repository import obtener_producto_por_id
from app.modules.administracion.repositories.promocion_repository import (
    actualizar_promocion,
    cambiar_estado_promocion,
    crear_promocion,
    listar_promociones,
    obtener_promocion_por_id,
)
from app.modules.administracion.schemas.promocion.promocion_request import PromocionRequest
from app.modules.administracion.schemas.promocion.promocion_response import PromocionResponse


def obtener_promociones(usuario_actual: dict[str, object]) -> list[PromocionResponse]:
    return [PromocionResponse(**promocion) for promocion in listar_promociones(exigir_empresa_id(usuario_actual))]


def obtener_promocion(promocion_id: int, usuario_actual: dict[str, object]) -> PromocionResponse:
    promocion = obtener_promocion_por_id(promocion_id, exigir_empresa_id(usuario_actual))
    if promocion is None:
        raise HTTPException(status_code=404, detail="Promocion no encontrada.")
    return PromocionResponse(**promocion)


def registrar_promocion(request: PromocionRequest, usuario_actual: dict[str, object]) -> PromocionResponse:
    empresa_id = exigir_empresa_id(usuario_actual)
    validar_productos_existentes(request.producto_ids, empresa_id)
    try:
        promocion = crear_promocion(
        request.nombre,
        request.descripcion,
        request.tipo_descuento,
        request.valor,
        request.fecha_inicio,
        request.fecha_fin,
        request.producto_ids,
        request.sucursal_ids,
        empresa_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return PromocionResponse(**promocion)


def editar_promocion(promocion_id: int, request: PromocionRequest, usuario_actual: dict[str, object]) -> PromocionResponse:
    empresa_id = exigir_empresa_id(usuario_actual)
    if obtener_promocion_por_id(promocion_id, empresa_id) is None:
        raise HTTPException(status_code=404, detail="Promocion no encontrada.")

    validar_productos_existentes(request.producto_ids, empresa_id)
    try:
        promocion = actualizar_promocion(
        promocion_id,
        request.nombre,
        request.descripcion,
        request.tipo_descuento,
        request.valor,
        request.fecha_inicio,
        request.fecha_fin,
        request.producto_ids,
        request.sucursal_ids,
        empresa_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if promocion is None:
        raise HTTPException(status_code=404, detail="Promocion no encontrada.")
    return PromocionResponse(**promocion)


def desactivar_promocion(promocion_id: int, usuario_actual: dict[str, object]) -> PromocionResponse:
    promocion = cambiar_estado_promocion(promocion_id, False, exigir_empresa_id(usuario_actual))
    if promocion is None:
        raise HTTPException(status_code=404, detail="Promocion no encontrada.")
    return PromocionResponse(**promocion)


def activar_promocion(promocion_id: int, usuario_actual: dict[str, object]) -> PromocionResponse:
    promocion = cambiar_estado_promocion(promocion_id, True, exigir_empresa_id(usuario_actual))
    if promocion is None:
        raise HTTPException(status_code=404, detail="Promocion no encontrada.")
    return PromocionResponse(**promocion)


def validar_productos_existentes(producto_ids: list[int], empresa_id: int) -> None:
    for producto_id in producto_ids:
        producto = obtener_producto_por_id(producto_id, empresa_id)
        if producto is None:
            raise HTTPException(status_code=404, detail=f"Producto {producto_id} no encontrado.")
