from fastapi import APIRouter, Depends, Query

from app.modules.autenticacion.dependencies.usuario_actual import obtener_usuario_actual
from app.modules.ventas_inventario.schemas.delivery.delivery_request import (
    DeliveryCotizarRequest,
    DeliveryEstadoRequest,
    DeliveryGeocodificarResponse,
    DeliverySolicitarRequest,
)
from app.modules.ventas_inventario.schemas.delivery.delivery_response import (
    DeliveryCotizacionResponse,
    DeliveryDetalleResponse,
    DeliveryEstadoResponse,
    DeliveryItemResponse,
)
from app.modules.ventas_inventario.services.delivery_service import (
    actualizar_estado_delivery_service,
    cotizar_delivery_service,
    crear_delivery_service,
    geocodificar_delivery_service,
    listar_deliveries_service,
    listar_mis_deliveries_service,
    obtener_delivery_service,
    obtener_mi_delivery_service,
)

router = APIRouter(prefix="/api/v1/delivery", tags=["Delivery"])


@router.post("/cotizar", response_model=DeliveryCotizacionResponse)
def cotizar_delivery(request: DeliveryCotizarRequest) -> DeliveryCotizacionResponse:
    return cotizar_delivery_service(request)


@router.get("/geocodificar", response_model=DeliveryGeocodificarResponse)
def geocodificar_delivery(direccion: str = Query(min_length=5)) -> DeliveryGeocodificarResponse:
    return geocodificar_delivery_service(direccion)


@router.post("/solicitar", response_model=DeliveryDetalleResponse)
def solicitar_delivery(
    request: DeliverySolicitarRequest,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> DeliveryDetalleResponse:
    return crear_delivery_service(usuario_actual, request)


@router.get("/mis-deliveries", response_model=list[DeliveryItemResponse])
def listar_mis_deliveries(
    estado: str | None = None,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> list[DeliveryItemResponse]:
    return listar_mis_deliveries_service(usuario_actual, estado)


@router.get("/mis-deliveries/{delivery_id}", response_model=DeliveryDetalleResponse)
def obtener_mi_delivery(
    delivery_id: int,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> DeliveryDetalleResponse:
    return obtener_mi_delivery_service(usuario_actual, delivery_id)


@router.get("", response_model=list[DeliveryItemResponse])
def listar_deliveries(
    estado: str | None = None,
    cliente: str | None = None,
    sucursal_id: int | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> list[DeliveryItemResponse]:
    return listar_deliveries_service(usuario_actual, estado, cliente, sucursal_id, fecha_desde, fecha_hasta)


@router.get("/{delivery_id}", response_model=DeliveryDetalleResponse)
def obtener_delivery(
    delivery_id: int,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> DeliveryDetalleResponse:
    return obtener_delivery_service(usuario_actual, delivery_id)


@router.patch("/{delivery_id}/estado", response_model=DeliveryEstadoResponse)
def actualizar_estado_delivery(
    delivery_id: int,
    request: DeliveryEstadoRequest,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> DeliveryEstadoResponse:
    return actualizar_estado_delivery_service(usuario_actual, delivery_id, request)
