from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FiltrosAnalitica(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origen: Literal["OFICIAL", "DEMOSTRACION"] = "OFICIAL"
    sucursal_id: int | None = Field(default=None, gt=0)
    producto_id: str | None = Field(default=None, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    corte_desde: date | None = None
    corte_hasta: date | None = None
    pagina: int = Field(default=1, ge=1, le=100000)
    tamano: int = Field(default=25, ge=1, le=100)

    @model_validator(mode="after")
    def validar_periodo(self):
        if self.corte_desde and self.corte_hasta and self.corte_desde > self.corte_hasta:
            raise ValueError("La fecha inicial no puede ser posterior a la final.")
        return self


class FiltrosSegmentacion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origen: Literal["OFICIAL", "DEMOSTRACION"] = "OFICIAL"
    grupo: int | None = Field(default=None, ge=1, le=6)
    pagina: int = Field(default=1, ge=1, le=100000)
    tamano: int = Field(default=25, ge=1, le=100)


class ExportarAnaliticaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tipo: Literal["PREDICCIONES", "SEGMENTOS"]
    origen: Literal["OFICIAL", "DEMOSTRACION"] = "OFICIAL"
    sucursal_id: int | None = Field(default=None, gt=0)
    producto_id: str | None = Field(default=None, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    corte_desde: date | None = None
    corte_hasta: date | None = None
    grupo: int | None = Field(default=None, ge=1, le=6)

    @model_validator(mode="after")
    def coherencia(self):
        if self.tipo == "SEGMENTOS" and any(v is not None for v in
                (self.sucursal_id, self.producto_id, self.corte_desde, self.corte_hasta)):
            raise ValueError("Los segmentos son de empresa y no admiten filtros de predicción.")
        if self.tipo == "PREDICCIONES" and self.grupo is not None:
            raise ValueError("El grupo solo corresponde a segmentación.")
        if self.corte_desde and self.corte_hasta and self.corte_desde > self.corte_hasta:
            raise ValueError("Revisa las fechas de corte.")
        return self


class InterpretarAnaliticaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    texto: str = Field(min_length=3, max_length=1200)
    origen: Literal["OFICIAL", "DEMOSTRACION"] = "OFICIAL"
    origen_entrada: Literal["TEXTO", "VOZ"] = "TEXTO"
