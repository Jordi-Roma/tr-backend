from pydantic import BaseModel


class UsuarioAdminResponse(BaseModel):
    id: int
    nombre: str
    apellido: str
    username: str
    correo: str
    activo: bool
    roles: list[str]
    es_cliente: bool
    es_empleado: bool


class MensajeResponse(BaseModel):
    mensaje: str
