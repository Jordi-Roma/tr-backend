from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator, model_validator


class VarianteDatos(BaseModel):
    talla_id: int | None = Field(default=None, gt=0)
    color_id: int | None = Field(default=None, gt=0)
    sku: str = Field(min_length=1, max_length=80)
    ancho_cm: float | None = Field(default=None, ge=0.01, le=9999.99, allow_inf_nan=False)
    largo_cm: float | None = Field(default=None, ge=0.01, le=9999.99, allow_inf_nan=False)

    @field_validator('sku')
    @classmethod
    def validar_sku(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError('El SKU no puede estar vacío.')
        return valor.strip()


class CrearVarianteRequest(VarianteDatos):
    producto_id: int = Field(gt=0)


class ActualizarVarianteRequest(VarianteDatos):
    pass


class AsignarPrecioRequest(BaseModel):
    monto: Decimal = Field(gt=0, max_digits=12, decimal_places=2, allow_inf_nan=False)
    fecha_inicio: datetime | None = None
    fecha_fin: datetime | None = None

    @model_validator(mode='after')
    def validar_fechas(self):
        if self.fecha_inicio and self.fecha_fin and self.fecha_fin.date() < self.fecha_inicio.date():
            raise ValueError('La fecha fin no puede ser anterior a la fecha inicio.')
        return self


class VarianteInicialRequest(VarianteDatos):
    precio: AsignarPrecioRequest | None = None
