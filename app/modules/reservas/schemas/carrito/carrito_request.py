from pydantic import BaseModel, Field


class AgregarCarritoItemRequest(BaseModel):
    producto_variante_id: int
    sucursal_id: int | None = None
    cantidad: int = Field(default=1, ge=1)


class ActualizarCarritoItemRequest(BaseModel):
    cantidad: int = Field(ge=1)
