from pydantic import BaseModel, Field


class AsistenteContexto(BaseModel):
    producto_id: int | None = Field(default=None, gt=0)
    sucursal_id: int | None = Field(default=None, gt=0)


class AsistenteChatRequest(BaseModel):
    mensaje: str = Field(..., min_length=1, max_length=600)
    contexto: AsistenteContexto | None = None


class AsistenteProductoResponse(BaseModel):
    producto_id: int
    nombre: str
    categoria: str | None = None
    marca: str | None = None
    talla: str | None = None
    color: str | None = None
    sucursal: str | None = None
    ciudad: str | None = None
    stock_disponible: int | None = None
    stock_reservado: int | None = None
    stock_real: int | None = None
    precio_vigente: float | None = None


class AsistenteAccionResponse(BaseModel):
    tipo: str
    label: str
    url: str | None = None


class AsistenteChatResponse(BaseModel):
    respuesta: str
    tipo: str
    productos: list[AsistenteProductoResponse] = Field(default_factory=list)
    alternativas: list[AsistenteProductoResponse] = Field(default_factory=list)
    acciones: list[AsistenteAccionResponse] = Field(default_factory=list)
    filtros_detectados: dict[str, object] = Field(default_factory=dict)
    requiere_login: bool = False
