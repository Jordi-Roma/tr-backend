from pydantic import BaseModel, Field, field_validator, model_validator


class DevolucionItemRequest(BaseModel):
    venta_detalle_id: int = Field(gt=0)
    cantidad: int = Field(gt=0)


class CrearDevolucionRequest(BaseModel):
    motivo: str = Field(min_length=5, max_length=500)
    observacion: str | None = Field(default=None, max_length=1000)
    items: list[DevolucionItemRequest] = Field(min_length=1, max_length=50)

    @field_validator("items")
    @classmethod
    def validar_lineas_unicas(cls, items: list[DevolucionItemRequest]) -> list[DevolucionItemRequest]:
        ids = [item.venta_detalle_id for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError("No repitas una misma línea de venta.")
        return items


class RevisarDevolucionRequest(BaseModel):
    aprobar: bool
    observacion: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validar_motivo_rechazo(self):
        if not self.aprobar and not (self.observacion or "").strip():
            raise ValueError("Al rechazar una devolución, indica el motivo.")
        return self


class DevolucionRecepcionItemRequest(BaseModel):
    detalle_id: int = Field(gt=0)
    cantidad_aceptada: int = Field(ge=0)
    observacion: str | None = Field(default=None, max_length=500)


class RegistrarRecepcionDevolucionRequest(BaseModel):
    items: list[DevolucionRecepcionItemRequest] = Field(min_length=1, max_length=50)

    @field_validator("items")
    @classmethod
    def validar_detalles_unicos(cls, items: list[DevolucionRecepcionItemRequest]) -> list[DevolucionRecepcionItemRequest]:
        ids = [item.detalle_id for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError("No repitas un mismo artículo de la devolución.")
        return items


class RegistrarReembolsoManualRequest(BaseModel):
    referencia: str = Field(min_length=3, max_length=255)
    metodo: str = Field(pattern="^(EFECTIVO|QR|OTRO)$")
    observacion: str | None = Field(default=None, max_length=1000)
