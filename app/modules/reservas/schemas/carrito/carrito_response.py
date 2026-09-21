from decimal import Decimal

from pydantic import BaseModel


class CarritoItemResponse(BaseModel):
    id: int
    producto_variante_id: int
    producto_id: int
    producto: str
    categoria: str
    talla: str
    color: str
    sucursal_id: int | None = None
    sucursal: str | None = None
    ciudad: str | None = None
    cantidad: int
    precio_unitario: Decimal
    subtotal: Decimal
    stock_disponible: int


class CarritoSucursalDisponibleResponse(BaseModel):
    id: int
    nombre: str
    ciudad: str
    latitud: Decimal | None = None
    longitud: Decimal | None = None


class CarritoResponse(BaseModel):
    id: int
    items: list[CarritoItemResponse]
    total: Decimal
    sucursales_disponibles: list[CarritoSucursalDisponibleResponse] = []


class MensajeResponse(BaseModel):
    mensaje: str
