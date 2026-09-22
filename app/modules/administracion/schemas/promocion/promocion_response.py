from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class PromocionProductoResponse(BaseModel):
    id: int
    nombre: str


class PromocionSucursalResponse(BaseModel):
    id: int
    nombre: str
    ciudad: str


class PromocionResponse(BaseModel):
    id: int
    nombre: str
    descripcion: str | None
    tipo_descuento: str
    valor: Decimal
    fecha_inicio: date
    fecha_fin: date
    activo: bool
    fecha_creacion: datetime
    productos: list[PromocionProductoResponse]
    sucursales: list[PromocionSucursalResponse]
