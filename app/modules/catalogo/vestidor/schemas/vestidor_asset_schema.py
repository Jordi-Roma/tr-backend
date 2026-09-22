from pydantic import BaseModel


class TallaARResponse(BaseModel):
    id: int
    nombre: str
    ancho_cm: float
    largo_cm: float


class ColorARResponse(BaseModel):
    id: int
    nombre: str
    hex: str | None = None
    imagen_url: str | None = None


class VarianteARResponse(BaseModel):
    id: int
    talla_id: int | None = None
    talla_nombre: str | None = None
    color_id: int | None = None
    color_nombre: str | None = None
    sku: str
    precio: float
    disponible: bool = True


class PrendaARResponse(BaseModel):
    producto_id: int
    nombre: str
    descripcion: str | None = None
    categoria: str
    tipo_prenda: str  # SUPERIOR, INFERIOR, VESTIDO
    tipo_corte: str  # REGULAR_FIT, SLIM_FIT, OVERSIZE
    ancho_base_cm: float
    largo_base_cm: float
    imagen_ar_url: str | None = None
    modelo_3d_url: str | None = None
    precio: float
    tallas: list[TallaARResponse] = []
    colores: list[ColorARResponse] = []
    variantes: list[VarianteARResponse] = []
