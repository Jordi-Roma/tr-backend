from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ProveedorResponse(BaseModel):
    id: int
    nombre: str
    nit: str | None
    telefono: str | None
    correo: str | None
    direccion: str | None
    activo: bool
    fecha_creacion: datetime
    usuarios_ids: list[int] = []


class MensajeResponse(BaseModel):
    mensaje: str


class ProveedorPerfilResponse(BaseModel):
    id: int
    nombre: str
    nit: str | None = None
    telefono: str | None = None
    correo: str | None = None
    direccion: str | None = None
    activo: bool
    fecha_creacion: datetime


class ProveedorProductoResponse(BaseModel):
    producto_id: int
    nombre: str
    categoria: str
    marca: str | None = None
    material: str | None = None
    genero: str | None = None
    costo_referencia: Decimal | None = None
    activo: bool
    variantes: int


class ProveedorStockResponse(BaseModel):
    sucursal_id: int
    sucursal: str
    ciudad: str
    producto_id: int
    producto: str
    producto_variante_id: int
    sku: str
    talla: str
    color: str
    stock_disponible: int
    stock_reservado: int
    stock_real: int
    stock_minimo: int
    bajo_stock: bool


class ProveedorEntregaResponse(BaseModel):
    id: int
    fecha_movimiento: datetime
    sucursal: str
    ciudad: str
    producto_id: int
    producto: str
    producto_variante_id: int
    sku: str
    talla: str
    color: str
    cantidad: int
    stock_anterior: int
    stock_nuevo: int
    motivo: str | None = None
