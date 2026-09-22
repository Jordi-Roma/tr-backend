from datetime import datetime
from pydantic import BaseModel

class ImagenProductoResponse(BaseModel):
    id: int
    producto_id: int
    url: str
    es_principal: bool
    activo: bool
    fecha_creacion: datetime

class ProductoResponse(BaseModel):
    id: int
    categoria_id: int
    categoria_nombre: str
    marca_id: int | None
    marca_nombre: str | None
    nombre: str
    descripcion: str | None
    material: str | None
    genero: str | None
    tipo_prenda: str = "SUPERIOR"
    tipo_corte: str = "REGULAR_FIT"
    ancho_base_cm: float = 53.0
    largo_base_cm: float = 72.0
    modelo_3d_url: str | None = None
    activo: bool
    fecha_creacion: datetime
    colecciones_ids: list[int]
    proveedores_ids: list[int]
    imagenes: list[ImagenProductoResponse]
