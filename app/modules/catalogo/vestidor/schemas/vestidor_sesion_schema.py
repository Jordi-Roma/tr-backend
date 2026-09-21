from datetime import datetime
from pydantic import BaseModel


class CrearSesionVestidorRequest(BaseModel):
    cliente_id: int | None = None
    producto_id: int
    variante_id: int | None = None
    origen: str = "MOVIL_AR"


class SesionVestidorResponse(BaseModel):
    id: int
    cliente_id: int | None = None
    producto_id: int
    variante_id: int | None = None
    fecha: datetime
    origen: str
