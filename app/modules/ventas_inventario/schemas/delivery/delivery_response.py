from decimal import Decimal

from pydantic import BaseModel


class DeliverySucursalResponse(BaseModel):
    id: int
    nombre: str
    ciudad: str | None = None
    direccion: str | None = None
    latitud: Decimal | None = None
    longitud: Decimal | None = None


class DeliveryCotizacionResponse(BaseModel):
    sucursal_id: int
    distancia_km: Decimal
    tiempo_estimado_min: int
    costo_delivery: Decimal
    disponible: bool
    mensaje: str | None = None


class DeliveryItemResponse(BaseModel):
    id: int
    venta_id: int
    venta_codigo: str | None = None
    cliente_id: int | None = None
    cliente_nombre: str | None = None
    cliente_correo: str | None = None
    sucursal_id: int
    sucursal_nombre: str | None = None
    direccion_entrega: str
    referencia: str | None = None
    distancia_km: Decimal | None = None
    tiempo_estimado_min: int | None = None
    costo_delivery: Decimal
    estado: str
    total_venta: Decimal | None = None
    fecha_creacion: str
    fecha_entrega: str | None = None


class DeliveryDetalleResponse(DeliveryItemResponse):
    sucursal_direccion: str | None = None
    sucursal_latitud: Decimal | None = None
    sucursal_longitud: Decimal | None = None
    latitud_entrega: Decimal
    longitud_entrega: Decimal
    observacion: str | None = None


class DeliveryEstadoResponse(BaseModel):
    mensaje: str
    delivery: DeliveryDetalleResponse
