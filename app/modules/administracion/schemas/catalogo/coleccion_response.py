from datetime import datetime
from pydantic import BaseModel

class ColeccionResponse(BaseModel):
    id: int
    temporada_id: int
    nombre: str
    descripcion: str | None = None
    activo: bool
    fecha_creacion: datetime

class ColeccionDetalleResponse(BaseModel):
    id: int
    temporada_id: int
    temporada_nombre: str
    nombre: str
    descripcion: str | None = None
    activo: bool
    fecha_creacion: datetime
