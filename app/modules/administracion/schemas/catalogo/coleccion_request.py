from pydantic import BaseModel, Field, field_validator
from typing import Literal

class CrearColeccionRequest(BaseModel):
    temporada_id: int = Field(gt=0)
    nombre: str = Field(max_length=150)
    descripcion: str | None = Field(default=None, max_length=255)

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, valor: str) -> str:
        nombre = valor.strip()
        if not nombre:
            raise ValueError("El nombre de la colección es obligatorio.")
        return nombre

    @field_validator("descripcion")
    @classmethod
    def validar_descripcion(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        descripcion = valor.strip()
        return descripcion or None

class ActualizarColeccionRequest(BaseModel):
    temporada_id: int = Field(gt=0)
    nombre: str = Field(max_length=150)
    descripcion: str | None = Field(default=None, max_length=255)

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, valor: str) -> str:
        nombre = valor.strip()
        if not nombre:
            raise ValueError("El nombre de la colección es obligatorio.")
        return nombre

    @field_validator("descripcion")
    @classmethod
    def validar_descripcion(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        descripcion = valor.strip()
        return descripcion or None
