from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Literal


class AsistenteContexto(BaseModel):
    model_config = ConfigDict(extra='forbid')
    producto_id: int | None = Field(default=None, gt=0, le=2**63-1)
    sucursal_id: int | None = Field(default=None, gt=0, le=2**63-1)
    empresa_id: int | None = Field(default=None, gt=0, le=2**63-1)
    variante_id: int | None = Field(default=None, gt=0, le=2**63-1)
    recurso_tipo: Literal['RESERVA','VENTA','ORDEN_PAGO','DELIVERY','CAMBIO','DEVOLUCION','REEMBOLSO_PAGO'] | None = None
    recurso_id: int | None = Field(default=None, gt=0, le=2**63-1)
    terminos: list[str] = Field(default_factory=list, max_length=8)
    color_patrones: list[str] = Field(default_factory=list, max_length=4)
    talla_patrones: list[str] = Field(default_factory=list, max_length=4)
    precio_max: float | None = Field(default=None, ge=0, le=100000000)

    @model_validator(mode='after')
    def validar_contexto(self):
        if (self.recurso_tipo is None) != (self.recurso_id is None):
            raise ValueError('Indica tipo e identificador de operación juntos.')
        if any(len(t)>60 or not t.strip() for campo in (self.terminos,self.color_patrones,self.talla_patrones) for t in campo):
            raise ValueError('Los filtros deben ser breves y no vacíos.')
        return self


class AsistenteChatRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
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
    precio_final: float | None = None
    precio_final_exacto: str | None = None
    moneda: str = 'BOB'
    variante_id: int | None = None
    sucursal_id: int | None = None
    descripcion: str | None = None
    material: str | None = None
    promocion: dict[str, object] | None = None
    motivo: str | None = None


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
    fuentes: list[str] = Field(default_factory=list)
    consultado_en: str | None = None
    datos: list[dict[str, object]] = Field(default_factory=list)
    contexto: AsistenteContexto | None = None
    aclaracion: bool = False
    hay_mas: bool = False
