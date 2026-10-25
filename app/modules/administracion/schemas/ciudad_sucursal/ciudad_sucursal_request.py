from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class CrearCiudadRequest(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    departamento: str | None = Field(default=None, max_length=120)

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, valor: str) -> str:
        nombre = valor.strip()

        if len(nombre) < 2:
            raise ValueError("El nombre de la ciudad es obligatorio.")

        return nombre

    @field_validator("departamento")
    @classmethod
    def validar_departamento(cls, valor: str | None) -> str | None:
        if valor is None:
            return None

        departamento = valor.strip()
        return departamento or None


class ActualizarCiudadRequest(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    departamento: str | None = Field(default=None, max_length=120)

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, valor: str) -> str:
        nombre = valor.strip()

        if len(nombre) < 2:
            raise ValueError("El nombre de la ciudad es obligatorio.")

        return nombre

    @field_validator("departamento")
    @classmethod
    def validar_departamento(cls, valor: str | None) -> str | None:
        if valor is None:
            return None

        departamento = valor.strip()
        return departamento or None


class CrearSucursalRequest(BaseModel):
    ciudad_id: int = Field(gt=0)
    nombre: str = Field(min_length=2, max_length=150)
    direccion: str = Field(min_length=1, max_length=255)
    telefono: str | None = Field(default=None, max_length=30)
    latitud: Decimal | None = None
    longitud: Decimal | None = None

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, valor: str) -> str:
        nombre = valor.strip()

        if len(nombre) < 2:
            raise ValueError("El nombre de la sucursal es obligatorio.")

        return nombre

    @field_validator("direccion")
    @classmethod
    def validar_direccion(cls, valor: str) -> str:
        direccion = valor.strip()

        if not direccion:
            raise ValueError("La direccion de la sucursal es obligatoria.")

        return direccion

    @field_validator("telefono")
    @classmethod
    def validar_telefono(cls, valor: str | None) -> str | None:
        if valor is None:
            return None

        telefono = valor.strip()
        return telefono or None

    @field_validator("latitud")
    @classmethod
    def validar_latitud(cls, valor: Decimal | None) -> Decimal | None:
        if valor is None:
            return None
        if valor < Decimal("-90") or valor > Decimal("90"):
            raise ValueError("La latitud no es valida.")
        return valor

    @field_validator("longitud")
    @classmethod
    def validar_longitud(cls, valor: Decimal | None) -> Decimal | None:
        if valor is None:
            return None
        if valor < Decimal("-180") or valor > Decimal("180"):
            raise ValueError("La longitud no es valida.")
        return valor


class ActualizarSucursalRequest(BaseModel):
    ciudad_id: int = Field(gt=0)
    nombre: str = Field(min_length=2, max_length=150)
    direccion: str = Field(min_length=1, max_length=255)
    telefono: str | None = Field(default=None, max_length=30)
    latitud: Decimal | None = None
    longitud: Decimal | None = None

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, valor: str) -> str:
        nombre = valor.strip()

        if len(nombre) < 2:
            raise ValueError("El nombre de la sucursal es obligatorio.")

        return nombre

    @field_validator("direccion")
    @classmethod
    def validar_direccion(cls, valor: str) -> str:
        direccion = valor.strip()

        if not direccion:
            raise ValueError("La direccion de la sucursal es obligatoria.")

        return direccion

    @field_validator("telefono")
    @classmethod
    def validar_telefono(cls, valor: str | None) -> str | None:
        if valor is None:
            return None

        telefono = valor.strip()
        return telefono or None

    @field_validator("latitud")
    @classmethod
    def validar_latitud(cls, valor: Decimal | None) -> Decimal | None:
        if valor is None:
            return None
        if valor < Decimal("-90") or valor > Decimal("90"):
            raise ValueError("La latitud no es valida.")
        return valor

    @field_validator("longitud")
    @classmethod
    def validar_longitud(cls, valor: Decimal | None) -> Decimal | None:
        if valor is None:
            return None
        if valor < Decimal("-180") or valor > Decimal("180"):
            raise ValueError("La longitud no es valida.")
        return valor
