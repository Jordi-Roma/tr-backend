from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel

class PrecioResponse(BaseModel):
    id: int
    variante_id: int
    monto: Decimal
    fecha_inicio: datetime
    fecha_fin: datetime | None
    activo: bool
    fecha_creacion: datetime

class VarianteResponse(BaseModel):
    id: int
    producto_id: int
    producto_nombre: str
    talla_id: int | None
    talla_nombre: str | None
    color_id: int | None
    color_nombre: str | None
    sku: str
    ancho_cm: float | None = None
    largo_cm: float | None = None
    activo: bool
    fecha_creacion: datetime
    precios: list[PrecioResponse]
