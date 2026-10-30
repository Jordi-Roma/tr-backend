import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.contexto_empresa import normalizar_codigo_empresa
from app.core.security import validar_password_seguro


class RegistroEmpresaRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    correo: str = Field(min_length=3, max_length=150)
    clave_solicitud: UUID
    empresa_codigo: str = Field(min_length=2, max_length=40)
    empresa_nombre: str = Field(min_length=2, max_length=150)
    plan_id: int = Field(gt=0)
    nombre: str = Field(min_length=1, max_length=120)
    apellido: str = Field(min_length=1, max_length=120)
    username: str = Field(min_length=4, max_length=80, pattern=r'^[a-zA-Z0-9_.]+$')
    password: str = Field(min_length=8, max_length=72)
    confirmar_password: str = Field(min_length=8, max_length=72)

    @field_validator('correo', 'empresa_codigo', 'empresa_nombre', 'nombre', 'apellido', 'username', mode='before')
    @classmethod
    def limpiar_texto(cls, valor):
        return valor.strip() if isinstance(valor, str) else valor

    @field_validator('correo')
    @classmethod
    def correo_valido(cls, valor: str) -> str:
        valor = valor.lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', valor):
            raise ValueError('Ingresa un correo válido.')
        return valor

    @field_validator('empresa_codigo')
    @classmethod
    def codigo_empresa(cls, valor: str) -> str:
        return normalizar_codigo_empresa(valor)

    @field_validator('username')
    @classmethod
    def identidad(cls, valor: str) -> str:
        return valor.lower()

    @field_validator('password')
    @classmethod
    def password_seguro(cls, valor: str) -> str:
        validar_password_seguro(valor)
        if len(valor.encode('utf-8')) > 72:
            raise ValueError('La contraseña supera el tamaño admitido.')
        return valor

    @model_validator(mode='after')
    def contrasenas_coinciden(self):
        if self.password != self.confirmar_password:
            raise ValueError('Las contraseñas no coinciden.')
        return self
