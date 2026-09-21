from pydantic import BaseModel, field_validator


class CrearRolRequest(BaseModel):
    nombre: str
    descripcion: str | None = None

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, valor: str) -> str:
        nombre = valor.strip().upper()

        if not nombre:
            raise ValueError("El nombre del rol es obligatorio.")

        return nombre

    @field_validator("descripcion")
    @classmethod
    def validar_descripcion(cls, valor: str | None) -> str | None:
        if valor is None:
            return None

        descripcion = valor.strip()
        return descripcion or None


class ActualizarRolRequest(BaseModel):
    nombre: str
    descripcion: str | None = None

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, valor: str) -> str:
        nombre = valor.strip().upper()

        if not nombre:
            raise ValueError("El nombre del rol es obligatorio.")

        return nombre

    @field_validator("descripcion")
    @classmethod
    def validar_descripcion(cls, valor: str | None) -> str | None:
        if valor is None:
            return None

        descripcion = valor.strip()
        return descripcion or None


class CrearPermisoRequest(BaseModel):
    nombre: str
    modulo: str
    accion: str
    descripcion: str | None = None

    @field_validator("nombre")
    @classmethod
    def validar_nombre_permiso(cls, valor: str) -> str:
        texto = valor.strip()

        if not texto:
            raise ValueError("Este campo es obligatorio.")

        return texto

    @field_validator("modulo")
    @classmethod
    def validar_modulo_permiso(cls, valor: str) -> str:
        texto = valor.strip().upper().replace(" ", "_")

        if not texto:
            raise ValueError("Este campo es obligatorio.")

        return texto

    @field_validator("accion")
    @classmethod
    def validar_accion_permiso(cls, valor: str) -> str:
        texto = valor.strip().lower()

        if not texto:
            raise ValueError("Este campo es obligatorio.")

        return texto

    @field_validator("descripcion")
    @classmethod
    def validar_descripcion(cls, valor: str | None) -> str | None:
        if valor is None:
            return None

        descripcion = valor.strip()
        return descripcion or None


class ActualizarPermisosRolRequest(BaseModel):
    permiso_ids: list[int]

    @field_validator("permiso_ids")
    @classmethod
    def validar_permiso_ids(cls, valor: list[int]) -> list[int]:
        if any(permiso_id <= 0 for permiso_id in valor):
            raise ValueError("Los permisos deben tener identificadores validos.")

        return sorted(set(valor))
