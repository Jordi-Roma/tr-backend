import re

from pydantic import BaseModel, Field, field_validator


class CrearProveedorRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=150)
    nit: str | None = Field(default=None, max_length=40)
    telefono: str | None = Field(default=None, max_length=30)
    correo: str | None = Field(default=None, max_length=320)
    direccion: str | None = Field(default=None, max_length=255)

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
    nombre: str = Field(min_length=1, max_length=150)
    telefono: str | None = Field(default=None, max_length=30)
    correo: str | None = Field(default=None, max_length=320)
    direccion: str | None = Field(default=None, max_length=255)

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


class VincularUsuarioProveedorRequest(BaseModel):
    usuario_id: int

    @field_validator("usuario_id")
    @classmethod
    def validar_usuario_id(cls, valor: int) -> int:
        if valor < 1:
            raise ValueError("El usuario no es valido.")
        return valor


from app.modules.autenticacion.schemas.usuario_admin.usuario_admin_request import ActualizarUsuarioRequest

class CrearCuentaProveedorRequest(ActualizarUsuarioRequest):
    password: str = Field(min_length=8, max_length=256)

class VincularProductoProveedorRequest(BaseModel):
    producto_id: int = Field(gt=0)
