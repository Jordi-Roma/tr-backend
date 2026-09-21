from decimal import Decimal
from pydantic import BaseModel, field_validator
from datetime import datetime

class CrearVarianteRequest(BaseModel):
    producto_id: int
    talla_id: int | None = None
    color_id: int | None = None
    sku: str
    ancho_cm: float | None = None
    largo_cm: float | None = None
    
    @field_validator("sku")
    @classmethod
    def validar_sku(cls, valor: str) -> str:
        sku = valor.strip()
        if not sku:
            raise ValueError("El SKU no puede estar vacío.")
        return sku

class ActualizarVarianteRequest(BaseModel):
    talla_id: int | None = None
    color_id: int | None = None
    sku: str
    ancho_cm: float | None = None
    largo_cm: float | None = None

    @field_validator("sku")
    @classmethod
    def validar_sku(cls, valor: str) -> str:
        sku = valor.strip()
        if not sku:
            raise ValueError("El SKU no puede estar vacío.")
        return sku

class AsignarPrecioRequest(BaseModel):
    monto: Decimal
    fecha_inicio: datetime | None = None
    fecha_fin: datetime | None = None
    
    @field_validator("monto")
    @classmethod
    def validar_monto(cls, valor: Decimal) -> Decimal:
        if valor <= 0:
            raise ValueError("El precio debe ser mayor a 0.")
        return valor
