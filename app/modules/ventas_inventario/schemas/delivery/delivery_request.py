from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class DeliveryCotizarRequest(BaseModel):
    direccion_id: int | None = Field(default=None, gt=0)
    sucursal_id: int = Field(gt=0)
    direccion_entrega: str = Field(min_length=5, max_length=500)
    referencia: str | None = Field(default=None, max_length=500)
    latitud_entrega: Decimal = Field(ge=-90, le=90)
    longitud_entrega: Decimal = Field(ge=-180, le=180)


class DeliveryCheckoutRequest(DeliveryCotizarRequest):
    cotizacion_id: UUID | None = None
    distancia_km: Decimal | None = Field(default=None, ge=0)
    tiempo_estimado_min: int | None = Field(default=None, ge=0)
    costo_delivery: Decimal | None = Field(default=None, ge=0)


class DeliverySolicitarRequest(DeliveryCheckoutRequest):
    venta_id: int = Field(gt=0)


class DeliveryEstadoRequest(BaseModel):
    version: int = Field(ge=1)
    recepcion_confirmada: bool = False
    estado: str = Field(min_length=3, max_length=30)
    observacion: str | None = Field(default=None, max_length=500)


class DeliveryGeocodificarResponse(BaseModel):
    direccion: str
    latitud: Decimal
    longitud: Decimal


class DeliveryIncidenciaRequest(BaseModel):
    version: int = Field(ge=1)
    resolver: bool = False
    observacion: str = Field(min_length=5, max_length=500)
