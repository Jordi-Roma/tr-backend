import re
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ActualizarPerfilRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: str = Field(min_length=1, max_length=100)
    apellido: str = Field(min_length=1, max_length=100)
    telefono: str | None = Field(default=None, max_length=30)
    username: str | None = None
    correo: str | None = None
    password_actual: str | None = None

    @field_validator("username")
    @classmethod
    def validar_username(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        valor = valor.strip().lower()
        if not re.fullmatch(r"[a-z0-9_.-]{4,80}", valor):
            raise ValueError("El usuario debe tener entre 4 y 80 letras, números, punto o guion.")
        return valor

    @field_validator("correo")
    @classmethod
    def validar_correo(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        valor = valor.strip().lower()
        if len(valor) > 320 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", valor):
            raise ValueError("El correo no tiene un formato válido.")
        return valor

    @field_validator("nombre", "apellido")
    @classmethod
    def validar_texto_obligatorio(cls, valor: str) -> str:
        valor_limpio = valor.strip()

        if not valor_limpio:
            raise ValueError("Este campo es obligatorio.")

        return valor_limpio

    @field_validator("telefono")
    @classmethod
    def validar_telefono(cls, valor: str | None) -> str | None:
        if valor is None:
            return None

        telefono = valor.strip()
        return telefono or None


class CambiarPasswordRequest(BaseModel):
    password_actual: str
    password_nuevo: str
    confirmar_password_nuevo: str

    @field_validator("password_actual", "password_nuevo", "confirmar_password_nuevo")
    @classmethod
    def validar_password_obligatorio(cls, valor: str) -> str:
        if not valor:
            raise ValueError("Este campo es obligatorio.")

        return valor


class DesactivarCuentaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password_actual: str = Field(min_length=1)
    confirmacion: str


class CrearDireccionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ciudad_id: int
    direccion: str = Field(min_length=1, max_length=255)
    referencia: str | None = Field(default=None, max_length=255)
    es_principal: bool = False

    @field_validator("direccion")
    @classmethod
    def validar_direccion(cls, valor: str) -> str:
        direccion = valor.strip()

        if not direccion:
            raise ValueError("La direccion es obligatoria.")

        return direccion

    @field_validator("referencia")
    @classmethod
    def validar_referencia(cls, valor: str | None) -> str | None:
        if valor is None:
            return None

        referencia = valor.strip()
        return referencia or None


class ActualizarDireccionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ciudad_id: int
    direccion: str = Field(min_length=1, max_length=255)
    referencia: str | None = Field(default=None, max_length=255)
    es_principal: bool = False

    @field_validator("direccion")
    @classmethod
    def validar_direccion(cls, valor: str) -> str:
        direccion = valor.strip()

        if not direccion:
            raise ValueError("La direccion es obligatoria.")

        return direccion

    @field_validator("referencia")
    @classmethod
    def validar_referencia(cls, valor: str | None) -> str | None:
        if valor is None:
            return None

        referencia = valor.strip()
        return referencia or None
