from pydantic import BaseModel, field_validator

from app.core.contexto_empresa import normalizar_codigo_empresa


class LoginRequest(BaseModel):
    identificador: str
    password: str
    empresa_codigo: str | None = None

    @field_validator("identificador", "password")
    @classmethod
    def validar_texto_obligatorio(cls, valor: str) -> str:
        valor_limpio = valor.strip()

        if not valor_limpio:
            raise ValueError("Este campo es obligatorio.")

        return valor_limpio

    @field_validator("empresa_codigo")
    @classmethod
    def validar_empresa_codigo(cls, valor: str | None) -> str | None:
        return normalizar_codigo_empresa(valor) if valor is not None else None
