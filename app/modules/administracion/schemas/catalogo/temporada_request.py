from pydantic import BaseModel, field_validator

class CrearTemporadaRequest(BaseModel):
    nombre: str
    anio: int

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, valor: str) -> str:
        nombre = valor.strip()
        if not nombre:
            raise ValueError("El nombre de la temporada es obligatorio.")
        return nombre

    @field_validator("anio")
    @classmethod
    def validar_anio(cls, valor: int) -> int:
        if valor < 2000 or valor > 2200:
            raise ValueError("El año debe estar entre 2000 y 2200.")
        return valor

class ActualizarTemporadaRequest(BaseModel):
    nombre: str
    anio: int

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, valor: str) -> str:
        nombre = valor.strip()
        if not nombre:
            raise ValueError("El nombre de la temporada es obligatorio.")
        return nombre

    @field_validator("anio")
    @classmethod
    def validar_anio(cls, valor: int) -> int:
        if valor < 2000 or valor > 2200:
            raise ValueError("El año debe estar entre 2000 y 2200.")
        return valor
