from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

TipoReporte = Literal[
    "VENTAS",
    "PRODUCTOS_MAS_VENDIDOS",
    "INVENTARIO",
    "RESERVAS",
    "MOVIMIENTOS",
    "TRANSFERENCIAS",
    "PAGOS",
    "DELIVERIES",
    "USUARIOS",
]


class ReporteRequest(BaseModel):
    tipo: TipoReporte
    fecha_desde: date
    fecha_hasta: date
    sucursal_id: int | None = Field(default=None, gt=0)
    agrupacion: Literal["DIA", "MES"] = "DIA"
    solo_bajo_stock: bool = False
    estado: str | None = Field(default=None, max_length=40)
    metodo_pago: str | None = Field(default=None, max_length=40)
    proveedor_pago: str | None = Field(default=None, max_length=40)
    tipo_entrega: Literal["RECOJO_SUCURSAL", "DELIVERY"] | None = None
    rol: str | None = Field(default=None, max_length=80)
    activo: bool | None = None

    @model_validator(mode="after")
    def validar_rango(self):
        if self.fecha_desde > self.fecha_hasta:
            raise ValueError("La fecha inicial no puede ser posterior a la final.")
        if (self.fecha_hasta - self.fecha_desde).days > 366:
            raise ValueError("El periodo maximo permitido es de 366 dias.")
        return self


class InterpretarRequest(BaseModel):
    texto: str = Field(min_length=3, max_length=500)


class CrearReporteProgramadoRequest(BaseModel):
    titulo: str = Field(min_length=3, max_length=150)
    tipo: TipoReporte
    frecuencia: Literal["DIARIA", "SEMANAL", "MENSUAL"]
    hora: str = Field(default="08:00", max_length=10)
    dia: str | None = Field(default=None, max_length=20)
    formato: Literal["PDF", "EXCEL"] = "PDF"
    destinatario_email: str = Field(min_length=5, max_length=200)
    sucursal_id: int | None = Field(default=None, gt=0)
    solo_bajo_stock: bool = False
    activo: bool = True


class ActualizarEstadoProgramadoRequest(BaseModel):
    activo: bool
