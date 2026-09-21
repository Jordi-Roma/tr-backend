from fastapi import HTTPException, status

from app.modules.reservas.repositories.carrito_repository import (
    actualizar_item_carrito,
    agregar_item_carrito,
    eliminar_item_carrito,
    obtener_carrito,
    obtener_cliente_id_por_usuario,
    vaciar_carrito,
)
from app.modules.reservas.schemas.carrito.carrito_request import (
    ActualizarCarritoItemRequest,
    AgregarCarritoItemRequest,
)
from app.modules.reservas.schemas.carrito.carrito_response import CarritoResponse


def obtener_carrito_cliente(usuario_actual: dict[str, object]) -> CarritoResponse:
    cliente_id = _obtener_cliente_id(usuario_actual)
    return CarritoResponse(**obtener_carrito(cliente_id))


def agregar_item(
    usuario_actual: dict[str, object],
    request: AgregarCarritoItemRequest,
) -> CarritoResponse:
    cliente_id = _obtener_cliente_id(usuario_actual)

    try:
        carrito = agregar_item_carrito(
            cliente_id,
            request.producto_variante_id,
            request.sucursal_id,
            request.cantidad,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    return CarritoResponse(**carrito)


def actualizar_item(
    usuario_actual: dict[str, object],
    item_id: int,
    request: ActualizarCarritoItemRequest,
) -> CarritoResponse:
    cliente_id = _obtener_cliente_id(usuario_actual)

    try:
        carrito = actualizar_item_carrito(cliente_id, item_id, request.cantidad)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    if carrito is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item de carrito no encontrado.",
        )

    return CarritoResponse(**carrito)


def eliminar_item(usuario_actual: dict[str, object], item_id: int) -> CarritoResponse:
    cliente_id = _obtener_cliente_id(usuario_actual)
    carrito = eliminar_item_carrito(cliente_id, item_id)

    if carrito is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item de carrito no encontrado.",
        )

    return CarritoResponse(**carrito)


def vaciar(usuario_actual: dict[str, object]) -> CarritoResponse:
    cliente_id = _obtener_cliente_id(usuario_actual)
    return CarritoResponse(**vaciar_carrito(cliente_id))


def _obtener_cliente_id(usuario_actual: dict[str, object]) -> int:
    usuario_id = int(usuario_actual["id"])
    cliente_id = obtener_cliente_id_por_usuario(usuario_id)

    if cliente_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario no tiene cliente asociado.",
        )

    return cliente_id
