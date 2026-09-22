from datetime import date
from decimal import Decimal

from pydantic import BaseModel, field_validator, model_validator


class PromocionRequest(BaseModel):
    nombre: str
    descripcion: str | None = None
    tipo_descuento: str
    valor: Decimal
    fecha_inicio: date
    fecha_fin: date
    producto_ids: list[int]
    sucursal_ids: list[int] = []

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, valor: str) -> str:
        nombre = valor.strip()
        if not nombre:
            raise ValueError("El nombre de la promocion es obligatorio.")
        return nombre

    @field_validator("descripcion")
    @classmethod
    def validar_descripcion(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        descripcion = valor.strip()
        return descripcion or None

    @field_validator("tipo_descuento")
    @classmethod
    def validar_tipo_descuento(cls, valor: str) -> str:
        tipo = valor.strip().upper()
        if tipo not in {"PORCENTAJE", "MONTO_FIJO"}:
            raise ValueError("El tipo de descuento no es valido.")
        return tipo

    @field_validator("producto_ids")
    @classmethod
    def validar_productos(cls, valor: list[int]) -> list[int]:
        producto_ids = sorted(set(valor))
        if not producto_ids:
            raise ValueError("Debes seleccionar al menos un producto.")
        if any(producto_id < 1 for producto_id in producto_ids):
            raise ValueError("Hay productos no validos.")
        return producto_ids

    @field_validator("sucursal_ids")
    @classmethod
    def validar_sucursales(cls, valor: list[int]) -> list[int]:
        sucursal_ids = sorted(set(valor))
        if any(sucursal_id < 1 for sucursal_id in sucursal_ids):
            raise ValueError("Hay sucursales no validas.")
        return sucursal_ids

    @model_validator(mode="after")
    def validar_promocion(self) -> "PromocionRequest":
        if self.fecha_fin < self.fecha_inicio:
            raise ValueError("La fecha fin no puede ser menor a la fecha inicio.")

        if self.tipo_descuento == "PORCENTAJE" and not (self.valor > 0 and self.valor <= 100):
            raise ValueError("El porcentaje debe ser mayor a 0 y menor o igual a 100.")

        if self.tipo_descuento == "MONTO_FIJO" and self.valor < 0:
            raise ValueError("El monto fijo no puede ser negativo.")

        return self
