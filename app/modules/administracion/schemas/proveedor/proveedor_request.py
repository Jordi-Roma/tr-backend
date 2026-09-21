import re

from pydantic import BaseModel, field_validator


class CrearProveedorRequest(BaseModel):
    nombre: str
    nit: str | None = None
    telefono: str | None = None
    correo: str | None = None
    direccion: str | None = None

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, valor: str) -> str:
        nombre = valor.strip()

        if not nombre:
            raise ValueError("El nombre del proveedor es obligatorio.")

        return nombre

    @field_validator("nit")
    @classmethod
    def validar_nit(cls, valor: str | None) -> str | None:
        if valor is None:
            return None

        nit = valor.strip()
        return nit or None

    @field_validator("telefono")
    @classmethod
    def validar_telefono(cls, valor: str | None) -> str | None:
        if valor is None:
            return None

        telefono = valor.strip()
        return telefono or None

    @field_validator("correo")
    @classmethod
    def validar_correo(cls, valor: str | None) -> str | None:
        if valor is None:
            return None

        correo = valor.strip().lower()

        if not correo:
            return None

        if "@" not in correo or "." not in correo.split("@")[-1]:
            raise ValueError("El correo no tiene un formato valido.")

        return correo

    @field_validator("direccion")
    @classmethod
    def validar_direccion(cls, valor: str | None) -> str | None:
        if valor is None:
            return None

        direccion = valor.strip()
        return direccion or None


class ActualizarProveedorRequest(BaseModel):
    nombre: str
    telefono: str | None = None
    correo: str | None = None
    direccion: str | None = None

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, valor: str) -> str:
        nombre = valor.strip()

        if not nombre:
            raise ValueError("El nombre del proveedor es obligatorio.")

        return nombre

    @field_validator("telefono")
    @classmethod
    def validar_telefono(cls, valor: str | None) -> str | None:
        if valor is None:
            return None

        telefono = valor.strip()
        return telefono or None

    @field_validator("correo")
    @classmethod
    def validar_correo(cls, valor: str | None) -> str | None:
        if valor is None:
            return None

        correo = valor.strip().lower()

        if not correo:
            return None

        if "@" not in correo or "." not in correo.split("@")[-1]:
            raise ValueError("El correo no tiene un formato valido.")

        return correo

    @field_validator("direccion")
    @classmethod
    def validar_direccion(cls, valor: str | None) -> str | None:
        if valor is None:
            return None

        direccion = valor.strip()
        return direccion or None
