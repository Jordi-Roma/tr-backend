import re
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ActualizarUsuarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: str = Field(min_length=1, max_length=100)
    apellido: str = Field(min_length=1, max_length=100)
    username: str = Field(min_length=4, max_length=80)
    correo: str = Field(min_length=3, max_length=320)

    @field_validator("nombre", "apellido", "username", "correo")
    @classmethod
    def texto(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Este campo es obligatorio.")
        return v

    @field_validator("username")
    @classmethod
    def usuario(cls, v):
        if not re.fullmatch(r"[a-zA-Z0-9_.-]{4,80}", v):
            raise ValueError(
                "Usuario inválido: usa de 4 a 80 letras, números, punto o guion."
            )
        return v.lower()

    @field_validator("correo")
    @classmethod
    def email(cls, v):
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", v):
            raise ValueError("Correo inválido.")
        return v.lower()


class CrearUsuarioAdminRequest(ActualizarUsuarioRequest):
    password: str = Field(min_length=8, max_length=256)
    rol_id: int = Field(gt=0)
    telefono: str | None = Field(default=None, max_length=30)


class PlantillaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: str | None = Field(default=None, min_length=1, max_length=80)
    descripcion: str | None = Field(default=None, max_length=255)
    activo: bool | None = None
    permiso_ids: list[int] | None = None
    confirmar_global: bool = False

    @field_validator("permiso_ids")
    @classmethod
    def ids(cls, v):
        if v is not None and (len(v) > 500 or any(i <= 0 for i in v)):
            raise ValueError("Permisos inválidos.")
        return sorted(set(v)) if v is not None else None
