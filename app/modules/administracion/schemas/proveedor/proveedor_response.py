from datetime import datetime

from pydantic import BaseModel


class ProveedorResponse(BaseModel):
    id: int
    nombre: str
    nit: str | None
    telefono: str | None
    correo: str | None
    direccion: str | None
    activo: bool
    fecha_creacion: datetime


class MensajeResponse(BaseModel):
    mensaje: str
