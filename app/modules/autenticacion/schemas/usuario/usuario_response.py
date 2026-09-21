from pydantic import BaseModel


class UsuarioRegistroResponse(BaseModel):
    id: int
    nombre: str
    apellido: str
    username: str
    correo: str
    rol: str
    mensaje: str
