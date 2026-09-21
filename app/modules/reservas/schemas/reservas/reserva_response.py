from decimal import Decimal
from datetime import date, datetime

from pydantic import BaseModel


class ReservaDetalleResponse(BaseModel):
    id: int
    producto_variante_id: int
    producto_id: int
    producto: str
    categoria: str
    talla: str
    color: str
    cantidad: int
    precio_unitario: Decimal
    subtotal: Decimal


class ReservaResponse(BaseModel):
    id: int
    codigo: str
    cliente_id: int
    cliente: str | None = None
    sucursal_id: int
    sucursal: str
    ciudad: str
    estado: str
    total: Decimal
    monto_reserva: Decimal = Decimal("0.00")
    monto_aplicado: Decimal = Decimal("0.00")
    anticipo_pagado: bool = False
    anticipo_orden_id: int | None = None
    venta_id: int | None = None
    fecha_cita: date | None = None
    fecha_reserva: datetime
    fecha_expiracion: datetime | None = None
    observacion: str | None = None
    detalles: list[ReservaDetalleResponse]


class ReservaPagoResponse(BaseModel):
    reserva: ReservaResponse
    requiere_checkout: bool = False
    orden_id: int | None = None
    venta_id: int | None = None
    checkout_url: str | None = None
    mensaje: str | None = None
