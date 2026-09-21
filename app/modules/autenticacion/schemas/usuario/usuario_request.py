import re

from pydantic import BaseModel, field_validator


class UsuarioRegistroRequest(BaseModel):
    nombre: str
    apellido: str
    username: str
    correo: str
    password: str
    telefono: str | None = None

    @field_validator("nombre", "apellido", "password")
    @classmethod
    def validar_texto_obligatorio(cls, valor: str) -> str:
        valor_limpio = valor.strip()

        if not valor_limpio:
            raise ValueError("Este campo es obligatorio.")

        return valor_limpio

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

    @field_validator("telefono")
    @classmethod
    def validar_telefono(cls, valor: str | None) -> str | None:
        if valor is None:
            return None

        telefono = valor.strip()
        return telefono or None
