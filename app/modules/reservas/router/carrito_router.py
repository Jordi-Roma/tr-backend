from fastapi import APIRouter, Depends

from app.modules.autenticacion.dependencies.usuario_actual import obtener_usuario_actual
from app.modules.reservas.schemas.carrito.carrito_request import (
    ActualizarCarritoItemRequest,
    AgregarCarritoItemRequest,
)
from app.modules.reservas.schemas.carrito.carrito_response import CarritoResponse
from app.modules.reservas.services.carrito_service import (
    actualizar_item,
    agregar_item,
    eliminar_item,
    obtener_carrito_cliente,
    vaciar,
)

router = APIRouter(
    prefix="/api/v1/carrito",
    tags=["Carrito"],
)


@router.get("", response_model=CarritoResponse)
def obtener_carrito_endpoint(
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> CarritoResponse:
    return obtener_carrito_cliente(usuario_actual)


@router.post("/items", response_model=CarritoResponse)
def agregar_item_endpoint(
    request: AgregarCarritoItemRequest,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> CarritoResponse:
    return agregar_item(usuario_actual, request)


@router.put("/items/{item_id}", response_model=CarritoResponse)
def actualizar_item_endpoint(
    item_id: int,
    request: ActualizarCarritoItemRequest,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> CarritoResponse:
    return actualizar_item(usuario_actual, item_id, request)


@router.delete("/items/{item_id}", response_model=CarritoResponse)
def eliminar_item_endpoint(
    item_id: int,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> CarritoResponse:
    return eliminar_item(usuario_actual, item_id)


@router.delete("", response_model=CarritoResponse)
def vaciar_carrito_endpoint(
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> CarritoResponse:
    return vaciar(usuario_actual)
