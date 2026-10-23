from pydantic import BaseModel


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    usuario_id: int
    nombre: str
    apellido: str
    username: str
    correo: str
    roles: list[str]
    empresa_id: int | None
    empresa_codigo: str | None
    mensaje: str


class LogoutResponse(BaseModel):
    mensaje: str
