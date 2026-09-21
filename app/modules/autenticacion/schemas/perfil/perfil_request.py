from pydantic import BaseModel, field_validator


class ActualizarPerfilRequest(BaseModel):
    nombre: str
    apellido: str
    telefono: str | None = None

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


class CrearDireccionRequest(BaseModel):
    ciudad_id: int
    direccion: str
    referencia: str | None = None
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
    ciudad_id: int
    direccion: str
    referencia: str | None = None
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
