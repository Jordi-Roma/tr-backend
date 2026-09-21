from pydantic import BaseModel


class RolResponse(BaseModel):
    id: int
    nombre: str
    descripcion: str | None
    activo: bool
    cantidad_permisos: int = 0


class PermisoResponse(BaseModel):
    id: int
    nombre: str
    modulo: str
    accion: str
    descripcion: str | None
    activo: bool


class MensajeResponse(BaseModel):
    mensaje: str


class RolPermisosResponse(BaseModel):
    rol: RolResponse
    permiso_ids: list[int]
