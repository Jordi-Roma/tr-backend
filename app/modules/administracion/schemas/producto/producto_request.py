import base64
import re
from urllib.parse import urlsplit
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from app.modules.administracion.schemas.variante.variante_request import VarianteInicialRequest


def validar_url(valor: str) -> str:
    valor = valor.strip()
    partes = urlsplit(valor)
    if (partes.scheme in ('http', 'https') and partes.hostname) or (valor.startswith('/static/') and not valor.startswith('//')):
        return valor
    raise ValueError('Utiliza una URL http/https o un archivo de /static/.')


class ImagenProductoRequest(BaseModel):
    url: str = Field(min_length=1, max_length=7_000_000)
    es_principal: bool = False

    @field_validator('url')
    @classmethod
    def validar_imagen(cls, valor: str) -> str:
        valor = valor.strip()
        if valor.startswith('data:'):
            if not re.match(r'^data:image/(png|jpeg|webp|gif);base64,', valor):
                raise ValueError('La imagen debe ser PNG, JPEG, WEBP o GIF.')
            try:
                contenido = base64.b64decode(valor.split(',',1)[1], validate=True)
            except ValueError as error:
                raise ValueError('La imagen no contiene datos base64 válidos.') from error
            if not contenido or len(contenido) > 5*1024*1024:
                raise ValueError('La imagen debe tener contenido y ocupar como máximo 5 MB.')
            return valor
        return validar_url(valor)


class ProductoDatos(BaseModel):
    categoria_id: int = Field(gt=0)
    marca_id: int | None = Field(default=None, gt=0)
    nombre: str = Field(min_length=1, max_length=180)
    descripcion: str | None = Field(default=None, max_length=10000)
    material: str | None = Field(default=None, max_length=120)
    genero: str | None = None
    tipo_prenda: Literal['SUPERIOR','INFERIOR','VESTIDO'] = 'SUPERIOR'
    tipo_corte: Literal['REGULAR_FIT','SLIM_FIT','OVERSIZE'] = 'REGULAR_FIT'
    ancho_base_cm: float = Field(default=53.0, ge=0.01, le=9999.99, allow_inf_nan=False)
    largo_base_cm: float = Field(default=72.0, ge=0.01, le=9999.99, allow_inf_nan=False)
    modelo_3d_url: str | None = Field(default=None, max_length=2048)
    colecciones_ids: list[int] = Field(default_factory=list, max_length=100)
    proveedores_ids: list[int] = Field(default_factory=list, max_length=100)
    imagenes: list[ImagenProductoRequest] = Field(default_factory=list, max_length=20)

    @field_validator('ancho_base_cm','largo_base_cm', mode='before')
    @classmethod
    def dimensiones_por_defecto(cls, valor, info):
        return (53.0 if info.field_name=='ancho_base_cm' else 72.0) if valor is None else valor

    @field_validator('nombre')
    @classmethod
    def validar_nombre(cls, valor):
        if not valor.strip():
            raise ValueError('El nombre del producto es obligatorio.')
        return valor.strip()

    @field_validator('descripcion','material','modelo_3d_url')
    @classmethod
    def limpiar_opcional(cls, valor):
        return valor.strip() or None if valor is not None else None

    @field_validator('modelo_3d_url')
    @classmethod
    def validar_modelo(cls, valor):
        return validar_url(valor) if valor else None

    @field_validator('genero')
    @classmethod
    def validar_genero(cls, valor):
        if not valor:
            return None
        valor = valor.strip().upper()
        if valor not in ('MASCULINO','FEMENINO','UNISEX'):
            raise ValueError('El género debe ser MASCULINO, FEMENINO o UNISEX.')
        return valor

    @field_validator('colecciones_ids','proveedores_ids')
    @classmethod
    def validar_ids(cls, valores):
        if any(v < 1 for v in valores):
            raise ValueError('Las asociaciones deben tener identificadores positivos.')
        return sorted(set(valores))

    @model_validator(mode='after')
    def validar_imagenes(self):
        if len({i.url for i in self.imagenes}) != len(self.imagenes):
            raise ValueError('No repita una imagen en el producto.')
        principales = sum(i.es_principal for i in self.imagenes)
        if principales > 1:
            raise ValueError('Sólo una imagen puede ser principal.')
        if self.imagenes and principales == 0:
            self.imagenes[0].es_principal = True
        return self


class CrearProductoRequest(ProductoDatos):
    variantes: list[VarianteInicialRequest] = Field(default_factory=list, max_length=100)


class ActualizarProductoRequest(ProductoDatos):
    pass
