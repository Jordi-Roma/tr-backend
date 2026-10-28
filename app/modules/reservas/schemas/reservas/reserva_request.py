from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class CrearReservaDesdeCarritoRequest(BaseModel):
    sucursal_id: int = Field(gt=0)
    fecha_cita: date
    observacion: str | None = Field(default=None, max_length=1000)
    clave_operacion: UUID | None = None


class CambiarEstadoReservaRequest(BaseModel):
    estado: str


class FinalizarReservaItemRequest(BaseModel):
    reserva_detalle_id: int
    cantidad: int = Field(ge=0)


class FinalizarReservaRequest(BaseModel):
    metodo_pago: str = Field(default="EFECTIVO", pattern="^(EFECTIVO|QR|TARJETA|TRANSFERENCIA|STRIPE)$")
    observacion: str | None = None
    items: list[FinalizarReservaItemRequest] = Field(min_length=1, max_length=100)

    @field_validator('items')
    @classmethod
    def sin_repetidos(cls, items):
        ids = [item.reserva_detalle_id for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError('No repitas una misma línea de reserva.')
        return items


class PagarReservaRequest(FinalizarReservaRequest):
    pass
