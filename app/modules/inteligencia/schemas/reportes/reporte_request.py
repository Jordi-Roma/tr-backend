from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from email.headerregistry import Address
from zoneinfo import ZoneInfoNotFoundError
from app.modules.inteligencia.services.programacion_reporte import validar_calendario

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
    origen: Literal['TEXTO','VOZ'] = 'TEXTO'


class CrearReporteProgramadoRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
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
    zona_horaria: str = Field(default='America/La_Paz',max_length=80)
    periodo: Literal['SEGUN_FRECUENCIA','DIA_ANTERIOR','SEMANA_ANTERIOR','MES_ANTERIOR'] = 'SEGUN_FRECUENCIA'
    filtros: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode='after')
    def validar_programacion(self):
        try:
            validar_calendario(self.frecuencia,self.hora,self.dia,self.zona_horaria)
            direccion=Address(addr_spec=self.destinatario_email)
            if not direccion.username or not direccion.domain or '\n' in self.destinatario_email or '\r' in self.destinatario_email:
                raise ValueError('Correo destinatario inválido.')
        except (ZoneInfoNotFoundError,IndexError) as error:
            raise ValueError('Zona horaria o correo inválido.') from error
        if set(self.filtros)-{'agrupacion','estado','metodo_pago','proveedor_pago','tipo_entrega','rol','activo'}:
            raise ValueError('Filtros de programación desconocidos.')
        ReporteRequest(tipo=self.tipo,fecha_desde=date(2026,1,1),fecha_hasta=date(2026,1,1),**self.filtros)
        return self


class ActualizarEstadoProgramadoRequest(BaseModel):
    activo: bool
