from datetime import datetime

from pydantic import BaseModel


class CategoriaResponse(BaseModel):
    id: int
    categoria_padre_id: int | None = None
    categoria_padre_nombre: str | None = None
    nombre: str
    descripcion: str | None
    activo: bool
    fecha_creacion: datetime


class TallaResponse(BaseModel):
    id: int
    nombre: str
    descripcion: str | None
    tipo_prenda: str = "SUPERIOR"
    ancho_cm: float | None = None
    largo_cm: float | None = None
    activo: bool
    fecha_creacion: datetime


class ColorResponse(BaseModel):
    id: int
    nombre: str
    codigo_hex: str | None
    activo: bool
    fecha_creacion: datetime


class MarcaResponse(BaseModel):
    id: int
    nombre: str
    descripcion: str | None
    activo: bool
    fecha_creacion: datetime


class MensajeResponse(BaseModel):
    mensaje: str
