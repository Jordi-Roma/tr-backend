from datetime import date

from pydantic import BaseModel, Field


class CrearReservaDesdeCarritoRequest(BaseModel):
    sucursal_id: int
    fecha_cita: date
    observacion: str | None = None


class CambiarEstadoReservaRequest(BaseModel):
    estado: str


class FinalizarReservaItemRequest(BaseModel):
    reserva_detalle_id: int
    cantidad: int = Field(ge=0)


class FinalizarReservaRequest(BaseModel):
    metodo_pago: str | None = "EFECTIVO"
    observacion: str | None = None
    items: list[FinalizarReservaItemRequest]


class PagarReservaRequest(FinalizarReservaRequest):
    pass
