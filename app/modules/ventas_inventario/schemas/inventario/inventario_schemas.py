from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


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


class MovimientoInventarioRequest(BaseModel):
    sucursal_id: int
    producto_variante_id: int
    tipo: str
    cantidad: int = Field(ge=1)
    motivo: str | None = None


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
    referencia_tipo: str | None = None
    referencia_id: int | None = None
    fecha_movimiento: datetime


class TransferenciaItemRequest(BaseModel):
    producto_variante_id: int
    cantidad: int = Field(ge=1)


class CrearTransferenciaRequest(BaseModel):
    sucursal_origen_id: int
    sucursal_destino_id: int
    observacion: str | None = None
    items: list[TransferenciaItemRequest]


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
    descuento: Decimal = Field(default=Decimal("0.00"), ge=0)


class CrearVentaPresencialRequest(BaseModel):
    sucursal_id: int
    cliente_id: int | None = None
    metodo_pago: str | None = None
    observacion: str | None = None
    items: list[VentaItemRequest]


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
