import re

from pydantic import BaseModel, Field, field_validator
from typing import Literal


# ── CATEGORÍA ──────────────────────────────────────────────────────────────

class CrearCategoriaRequest(BaseModel):
    categoria_padre_id: int | None = Field(default=None, gt=0)
    nombre: str = Field(max_length=120)
    descripcion: str | None = Field(default=None, max_length=255)

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, valor: str) -> str:
        nombre = valor.strip()

        if not nombre:
            raise ValueError("El nombre de la categoría es obligatorio.")

        return nombre

    @field_validator("descripcion")
    @classmethod
    def validar_descripcion(cls, valor: str | None) -> str | None:
        if valor is None:
            return None

        descripcion = valor.strip()
        return descripcion or None


class ActualizarCategoriaRequest(BaseModel):
    categoria_padre_id: int | None = Field(default=None, gt=0)
    nombre: str = Field(max_length=120)
    descripcion: str | None = Field(default=None, max_length=255)

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, valor: str) -> str:
        nombre = valor.strip()

        if not nombre:
            raise ValueError("El nombre de la categoría es obligatorio.")

        return nombre

    @field_validator("descripcion")
    @classmethod
    def validar_descripcion(cls, valor: str | None) -> str | None:
        if valor is None:
            return None

        descripcion = valor.strip()
        return descripcion or None


# ── TALLA ──────────────────────────────────────────────────────────────────

class CrearTallaRequest(BaseModel):
    nombre: str = Field(max_length=30)
    descripcion: str | None = Field(default=None, max_length=120)
    tipo_prenda: Literal["SUPERIOR", "INFERIOR", "VESTIDO"] = "SUPERIOR"
    ancho_cm: float | None = Field(default=None, ge=0.01, le=9999.99, allow_inf_nan=False)
    largo_cm: float | None = Field(default=None, ge=0.01, le=9999.99, allow_inf_nan=False)

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, valor: str) -> str:
        nombre = valor.strip()

        if not nombre:
            raise ValueError("El nombre de la talla es obligatorio.")

        return nombre

    @field_validator("descripcion")
    @classmethod
    def validar_descripcion(cls, valor: str | None) -> str | None:
        if valor is None:
            return None

        descripcion = valor.strip()
        return descripcion or None


class ActualizarTallaRequest(BaseModel):
    nombre: str = Field(max_length=30)
    descripcion: str | None = Field(default=None, max_length=120)
    tipo_prenda: Literal["SUPERIOR", "INFERIOR", "VESTIDO"] = "SUPERIOR"
    ancho_cm: float | None = Field(default=None, ge=0.01, le=9999.99, allow_inf_nan=False)
    largo_cm: float | None = Field(default=None, ge=0.01, le=9999.99, allow_inf_nan=False)

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, valor: str) -> str:
        nombre = valor.strip()

        if not nombre:
            raise ValueError("El nombre de la talla es obligatorio.")

        return nombre

    @field_validator("descripcion")
    @classmethod
    def validar_descripcion(cls, valor: str | None) -> str | None:
        if valor is None:
            return None

        descripcion = valor.strip()
        return descripcion or None


# ── COLOR ──────────────────────────────────────────────────────────────────

class CrearColorRequest(BaseModel):
    nombre: str = Field(max_length=80)
    codigo_hex: str | None = None

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, valor: str) -> str:
        nombre = valor.strip()

        if not nombre:
            raise ValueError("El nombre del color es obligatorio.")

        return nombre

    @field_validator("codigo_hex")
    @classmethod
    def validar_codigo_hex(cls, valor: str | None) -> str | None:
        if valor is None:
            return None

        hex_val = valor.strip()

        if not hex_val:
            return None

        if not re.fullmatch(r"^#[0-9A-Fa-f]{6}$", hex_val):
            raise ValueError(
                "El código hexadecimal debe tener el formato #RRGGBB (ej: #FF5733)."
            )

        return hex_val


class ActualizarColorRequest(BaseModel):
    nombre: str = Field(max_length=80)
    codigo_hex: str | None = None

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, valor: str) -> str:
        nombre = valor.strip()

        if not nombre:
            raise ValueError("El nombre del color es obligatorio.")

        return nombre

    @field_validator("codigo_hex")
    @classmethod
    def validar_codigo_hex(cls, valor: str | None) -> str | None:
        if valor is None:
            return None

        hex_val = valor.strip()

        if not hex_val:
            return None

        if not re.fullmatch(r"^#[0-9A-Fa-f]{6}$", hex_val):
            raise ValueError(
                "El código hexadecimal debe tener el formato #RRGGBB (ej: #FF5733)."
            )

        return hex_val


# ── MARCA ──────────────────────────────────────────────────────────────────

class CrearMarcaRequest(BaseModel):
    nombre: str = Field(max_length=120)
    descripcion: str | None = Field(default=None, max_length=255)

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, valor: str) -> str:
        nombre = valor.strip()

        if not nombre:
            raise ValueError("El nombre de la marca es obligatorio.")

        return nombre

    @field_validator("descripcion")
    @classmethod
    def validar_descripcion(cls, valor: str | None) -> str | None:
        if valor is None:
            return None

        descripcion = valor.strip()
        return descripcion or None


class ActualizarMarcaRequest(BaseModel):
    nombre: str = Field(max_length=120)
    descripcion: str | None = Field(default=None, max_length=255)

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, valor: str) -> str:
        nombre = valor.strip()

        if not nombre:
            raise ValueError("El nombre de la marca es obligatorio.")

        return nombre

    @field_validator("descripcion")
    @classmethod
    def validar_descripcion(cls, valor: str | None) -> str | None:
        if valor is None:
            return None

        descripcion = valor.strip()
        return descripcion or None
