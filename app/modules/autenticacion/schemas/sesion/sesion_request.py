from pydantic import BaseModel, field_validator


class LoginRequest(BaseModel):
    identificador: str
    password: str

    @field_validator("identificador", "password")
    @classmethod
    def validar_texto_obligatorio(cls, valor: str) -> str:
        valor_limpio = valor.strip()

        if not valor_limpio:
            raise ValueError("Este campo es obligatorio.")

        return valor_limpio
