from fastapi import HTTPException

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


def obtener_promociones() -> list[PromocionResponse]:
    return [PromocionResponse(**promocion) for promocion in listar_promociones()]


def obtener_promocion(promocion_id: int) -> PromocionResponse:
    promocion = obtener_promocion_por_id(promocion_id)
    if promocion is None:
        raise HTTPException(status_code=404, detail="Promocion no encontrada.")
    return PromocionResponse(**promocion)


def registrar_promocion(request: PromocionRequest) -> PromocionResponse:
    validar_productos_existentes(request.producto_ids)
    promocion = crear_promocion(
        request.nombre,
        request.descripcion,
        request.tipo_descuento,
        request.valor,
        request.fecha_inicio,
        request.fecha_fin,
        request.producto_ids,
        request.sucursal_ids,
    )
    return PromocionResponse(**promocion)


def editar_promocion(promocion_id: int, request: PromocionRequest) -> PromocionResponse:
    if obtener_promocion_por_id(promocion_id) is None:
        raise HTTPException(status_code=404, detail="Promocion no encontrada.")

    validar_productos_existentes(request.producto_ids)
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
    )
    if promocion is None:
        raise HTTPException(status_code=404, detail="Promocion no encontrada.")
    return PromocionResponse(**promocion)


def desactivar_promocion(promocion_id: int) -> PromocionResponse:
    promocion = cambiar_estado_promocion(promocion_id, False)
    if promocion is None:
        raise HTTPException(status_code=404, detail="Promocion no encontrada.")
    return PromocionResponse(**promocion)


def activar_promocion(promocion_id: int) -> PromocionResponse:
    promocion = cambiar_estado_promocion(promocion_id, True)
    if promocion is None:
        raise HTTPException(status_code=404, detail="Promocion no encontrada.")
    return PromocionResponse(**promocion)


def validar_productos_existentes(producto_ids: list[int]) -> None:
    for producto_id in producto_ids:
        producto = obtener_producto_por_id(producto_id)
        if producto is None:
            raise HTTPException(status_code=404, detail=f"Producto {producto_id} no encontrado.")
