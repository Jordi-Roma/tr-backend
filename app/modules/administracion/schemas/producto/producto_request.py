from pydantic import BaseModel, field_validator

class ImagenProductoRequest(BaseModel):
    url: str
    es_principal: bool = False

class CrearProductoRequest(BaseModel):
    categoria_id: int
    marca_id: int | None = None
    nombre: str
    descripcion: str | None = None
    material: str | None = None
    genero: str | None = None
    tipo_prenda: str = "SUPERIOR"
    tipo_corte: str = "REGULAR_FIT"
    ancho_base_cm: float = 53.0
    largo_base_cm: float = 72.0
    colecciones_ids: list[int] = []
    proveedores_ids: list[int] = []
    imagenes: list[ImagenProductoRequest] = []

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, valor: str) -> str:
        nombre = valor.strip()
        if not nombre:
            raise ValueError("El nombre del producto es obligatorio.")
        return nombre

    @field_validator("genero")
    @classmethod
    def validar_genero(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        genero = valor.strip().upper()
        if genero not in ["MASCULINO", "FEMENINO", "UNISEX"]:
            raise ValueError("El género debe ser MASCULINO, FEMENINO o UNISEX.")
        return genero


class ActualizarProductoRequest(BaseModel):
    categoria_id: int
    marca_id: int | None = None
    nombre: str
    descripcion: str | None = None
    material: str | None = None
    genero: str | None = None
    tipo_prenda: str = "SUPERIOR"
    tipo_corte: str = "REGULAR_FIT"
    ancho_base_cm: float = 53.0
    largo_base_cm: float = 72.0
    colecciones_ids: list[int] = []
    proveedores_ids: list[int] = []
    imagenes: list[ImagenProductoRequest] = []

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, valor: str) -> str:
        nombre = valor.strip()
        if not nombre:
            raise ValueError("El nombre del producto es obligatorio.")
        return nombre

    @field_validator("genero")
    @classmethod
    def validar_genero(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        genero = valor.strip().upper()
        if genero not in ["MASCULINO", "FEMENINO", "UNISEX"]:
            raise ValueError("El género debe ser MASCULINO, FEMENINO o UNISEX.")
        return genero
