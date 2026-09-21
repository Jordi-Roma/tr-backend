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
    mensaje: str


class LogoutResponse(BaseModel):
    mensaje: str
