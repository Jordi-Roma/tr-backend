from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class OperacionRequest(BaseModel):
    clave_operacion: UUID | None = None


class InventarioResponse(BaseModel):
    id: int
    sucursal_id: int
    sucursal: str
    ciudad: str
    producto_variante_id: int
    producto_id: int
    producto: str
    categoria: str
    talla: str
    color: str
    stock_disponible: int
    stock_reservado: int
    stock_real: int
    stock_minimo: int
    bajo_stock: bool


class ActualizarStockMinimoRequest(BaseModel):
    stock_minimo: int = Field(ge=0)


class MovimientoInventarioRequest(OperacionRequest):
    sucursal_id: int
    producto_variante_id: int
    tipo: str
    cantidad: int = Field(ge=1)
    motivo: str | None = None
    proveedor_id: int | None = None


class MovimientoInventarioResponse(BaseModel):
    id: int
    sucursal_id: int
    sucursal: str
    ciudad: str
    producto_variante_id: int
    producto_id: int
    producto: str
    talla: str
    color: str
    tipo: str
    cantidad: int
    stock_anterior: int
    stock_nuevo: int
    motivo: str | None = None
    proveedor_id: int | None = None
    proveedor: str | None = None
    referencia_tipo: str | None = None
    referencia_id: int | None = None
    fecha_movimiento: datetime


class TransferenciaItemRequest(BaseModel):
    producto_variante_id: int
    cantidad: int = Field(ge=1)


class CrearTransferenciaRequest(OperacionRequest):
    sucursal_origen_id: int
    sucursal_destino_id: int
    observacion: str | None = None
    items: list[TransferenciaItemRequest] = Field(min_length=1, max_length=100)

    @field_validator('items')
    @classmethod
    def sin_variantes_repetidas(cls, items):
        ids = [i.producto_variante_id for i in items]
        if len(ids) != len(set(ids)):
            raise ValueError('No repitas una variante en la transferencia.')
        return items


class TransferenciaDetalleResponse(BaseModel):
    id: int
    producto_variante_id: int
    producto_id: int
    producto: str
    talla: str
    color: str
    cantidad: int


class TransferenciaResponse(BaseModel):
    id: int
    sucursal_origen_id: int
    sucursal_origen: str
    sucursal_destino_id: int
    sucursal_destino: str
    estado: str
    observacion: str | None = None
    fecha_transferencia: datetime
    detalles: list[TransferenciaDetalleResponse]


class VentaItemRequest(BaseModel):
    producto_variante_id: int
    cantidad: int = Field(ge=1)
    descuento: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)


class CrearVentaPresencialRequest(OperacionRequest):
    sucursal_id: int
    cliente_id: int | None = None
    metodo_pago: str = Field(pattern='^(EFECTIVO|QR|TARJETA|TRANSFERENCIA)$')
    observacion: str | None = None
    items: list[VentaItemRequest] = Field(min_length=1, max_length=100)

    @field_validator('items')
    @classmethod
    def sin_variantes_repetidas(cls, items):
        ids = [i.producto_variante_id for i in items]
        if len(ids) != len(set(ids)):
            raise ValueError('No repitas una variante en la venta; agrupa su cantidad.')
        return items


class VentaDetalleResponse(BaseModel):
    id: int
    producto_variante_id: int
    producto_id: int
    producto: str
    talla: str
    color: str
    cantidad: int
    precio_unitario: Decimal
    descuento: Decimal
    subtotal: Decimal


class VentaPresencialResponse(BaseModel):
    id: int
    codigo: str
    sucursal_id: int
    sucursal: str
    estado: str
    subtotal: Decimal
    descuento: Decimal
    total: Decimal
    metodo_pago: str | None = None
    observacion: str | None = None
    fecha_venta: datetime
    detalles: list[VentaDetalleResponse]
