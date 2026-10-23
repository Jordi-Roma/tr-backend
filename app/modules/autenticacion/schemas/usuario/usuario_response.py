from pydantic import BaseModel


class UsuarioRegistroResponse(BaseModel):
    id: int
    nombre: str
    apellido: str
    username: str
    correo: str
    rol: str
    empresa_id: int
    empresa_codigo: str
    mensaje: str
