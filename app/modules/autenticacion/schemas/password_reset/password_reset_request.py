from pydantic import BaseModel, Field, field_validator

from app.core.contexto_empresa import normalizar_codigo_empresa


class SolicitarPasswordResetRequest(BaseModel):
    identificador: str = Field(min_length=1, max_length=120)
    empresa_codigo: str | None = None

    @field_validator("empresa_codigo")
    @classmethod
    def validar_empresa_codigo(cls, valor: str | None) -> str | None:
        return normalizar_codigo_empresa(valor) if valor is not None else None

    @field_validator("identificador")
    @classmethod
    def validar_identificador(cls, valor: str) -> str:
        return valor.strip().lower()


class ConfirmarPasswordResetRequest(BaseModel):
    identificador: str = Field(min_length=1, max_length=120)
    empresa_codigo: str | None = None
    codigo: str = Field(min_length=6, max_length=6)
    password_nuevo: str = Field(min_length=1)
    confirmar_password_nuevo: str = Field(min_length=1)

    @field_validator("empresa_codigo")
    @classmethod
    def validar_empresa_codigo(cls, valor: str | None) -> str | None:
        return normalizar_codigo_empresa(valor) if valor is not None else None

    @field_validator("identificador")
    @classmethod
    def validar_identificador(cls, valor: str) -> str:
        return valor.strip().lower()

    @field_validator("codigo")
    @classmethod
    def validar_codigo(cls, valor: str) -> str:
        codigo = valor.strip()
        if not codigo.isdigit():
            raise ValueError("El codigo debe tener 6 digitos.")
        return codigo
