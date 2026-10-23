from pydantic import BaseModel


class PerfilResponse(BaseModel):
    id: int
    nombre: str
    apellido: str
    username: str
    correo: str
    telefono: str | None
    roles: list[str]
    empresa_id: int | None = None
    empresa_codigo: str | None = None
    sesion_revocada: bool = False


class MensajeResponse(BaseModel):
    mensaje: str


class DireccionResponse(BaseModel):
    id: int
    ciudad_id: int
    direccion: str
    referencia: str | None
    es_principal: bool


class ListaDireccionesResponse(BaseModel):
    direcciones: list[DireccionResponse]
