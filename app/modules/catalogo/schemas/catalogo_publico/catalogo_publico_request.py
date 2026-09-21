from decimal import Decimal
from pydantic import BaseModel, Field


class CatalogoFiltros(BaseModel):
    q: str | None = None
    categoria_id: int | None = None
    talla_id: int | None = None
    color_id: int | None = None
    temporada_id: int | None = None
    coleccion_id: int | None = None
    sucursal_id: int | None = None
    precio_min: Decimal | None = None
    precio_max: Decimal | None = None
    orden: str = "relevancia"
    solo_disponibles: bool = False
    pagina: int = Field(default=1, ge=1)
    por_pagina: int = Field(default=12, ge=1, le=60)
