from decimal import Decimal
from pydantic import BaseModel, Field, model_validator


class CatalogoFiltros(BaseModel):
    q: str | None = None
    categoria_id: int | None = None
    talla_id: int | None = None
    color_id: int | None = None
    temporada_id: int | None = None
    coleccion_id: int | None = None
    sucursal_id: int | None = None
    precio_min: Decimal | None = Field(default=None,ge=0)
    precio_max: Decimal | None = Field(default=None,ge=0)
    orden: str = "relevancia"
    solo_disponibles: bool = False
    pagina: int = Field(default=1, ge=1)
    por_pagina: int = Field(default=12, ge=1, le=60)

    @model_validator(mode='after')
    def rango_precio(self):
        if self.precio_min is not None and self.precio_max is not None and self.precio_min>self.precio_max:
            raise ValueError('El precio mínimo no puede superar al máximo.')
        return self
