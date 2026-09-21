from datetime import datetime
from pydantic import BaseModel

class TemporadaResponse(BaseModel):
    id: int
    nombre: str
    anio: int
    activo: bool
    fecha_creacion: datetime
