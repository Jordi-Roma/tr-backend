from pydantic import BaseModel, field_validator

class CrearColeccionRequest(BaseModel):
    temporada_id: int
    nombre: str
    descripcion: str | None = None

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
    temporada_id: int
    nombre: str
    descripcion: str | None = None

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
