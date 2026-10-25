import re

from pydantic import BaseModel, Field, field_validator


class AsignarUsuarioEmpleadoRequest(BaseModel):
    usuario_id: int = Field(gt=0)
    sucursal_id: int = Field(gt=0)
    codigo_empleado: str = Field(min_length=1, max_length=40)
    cargo: str = Field(min_length=1, max_length=80)
    rol: str = Field(min_length=1, max_length=80)

    @field_validator("codigo_empleado", "cargo", "rol")
    @classmethod
    def validar_texto_obligatorio(cls, valor: str) -> str:
        texto = valor.strip()

        if not texto:
            raise ValueError("Este campo es obligatorio.")

        return texto


class CrearUsuarioEmpleadoRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    apellido: str = Field(min_length=1, max_length=100)
    username: str = Field(min_length=1, max_length=80)
    correo: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=8, max_length=256)
    sucursal_id: int = Field(gt=0)
    codigo_empleado: str = Field(min_length=1, max_length=40)
    cargo: str = Field(min_length=1, max_length=80)
    rol: str = Field(min_length=1, max_length=80)

    @field_validator("nombre", "apellido", "codigo_empleado", "cargo", "rol")
    @classmethod
    def validar_texto_obligatorio(cls, valor: str) -> str:
        texto = valor.strip()

        if not texto:
            raise ValueError("Este campo es obligatorio.")

        return texto

    @field_validator("username")
    @classmethod
    def validar_username(cls, valor: str) -> str:
        username = valor.strip().lower()

        if not username:
            raise ValueError("El username es obligatorio.")

        if len(username) < 4:
            raise ValueError("El username debe tener al menos 4 caracteres.")

        if " " in username:
            raise ValueError("El username no debe contener espacios.")

        if re.fullmatch(r"[a-z0-9_.]+", username) is None:
            raise ValueError(
                "El username solo puede tener letras, numeros, guion bajo y punto."
            )

        return username

    @field_validator("correo")
    @classmethod
    def validar_correo(cls, valor: str) -> str:
        correo = valor.strip().lower()

        if "@" not in correo or "." not in correo.split("@")[-1]:
            raise ValueError("El correo no tiene un formato valido.")

        return correo


class ActualizarEmpleadoRequest(BaseModel):
    sucursal_id: int = Field(gt=0)
    codigo_empleado: str = Field(min_length=1, max_length=40)
    cargo: str = Field(min_length=1, max_length=80)
    rol: str = Field(min_length=1, max_length=80)

    @field_validator("codigo_empleado", "cargo", "rol")
    @classmethod
    def validar_texto_obligatorio(cls, valor: str) -> str:
        texto = valor.strip()

        if not texto:
            raise ValueError("Este campo es obligatorio.")

        return texto


class ActivarEmpleadoRequest(BaseModel):
    rol: str = Field(min_length=1, max_length=80)

    @field_validator("rol")
    @classmethod
    def validar_rol(cls, valor: str) -> str:
        texto = valor.strip()

        if not texto:
            raise ValueError("El rol es obligatorio.")

        return texto
