from datetime import date

from pydantic import BaseModel


class EmpleadoResponse(BaseModel):
    empleado_id: int
    usuario_id: int
    nombre: str
    apellido: str
    username: str
    correo: str
    sucursal_id: int
    sucursal_nombre: str
    codigo_empleado: str
    cargo: str
    fecha_ingreso: date
    activo: bool
    roles: list[str]


class MensajeResponse(BaseModel):
    mensaje: str
