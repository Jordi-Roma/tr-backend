from decimal import Decimal
from pydantic import BaseModel


class CheckoutStripeResponse(BaseModel):
    orden_id: int
    venta_id: int
    estado: str
    checkout_url: str


class OrdenPagoResponse(BaseModel):
    orden_id: int
    venta_id: int
    cliente_id: int | None = None
    monto_total: Decimal
    moneda: str
    metodo: str
    estado: str
    proveedor: str
    checkout_url: str | None = None
    proveedor_session_id: str | None = None
    fecha_pago: str | None = None


class PagoProductoDetalleResponse(BaseModel):
    producto: str
    categoria: str | None = None
    talla: str | None = None
    color: str | None = None
    cantidad: int
    precio_unitario: Decimal
    subtotal: Decimal


class PagoHistorialItemResponse(BaseModel):
    orden_id: int
    venta_id: int
    venta_codigo: str | None = None
    cliente_id: int | None = None
    cliente_nombre: str | None = None
    cliente_correo: str | None = None
    sucursal_id: int | None = None
    sucursal_nombre: str | None = None
    monto_total: Decimal
    moneda: str
    metodo: str
    estado: str
    proveedor: str
    fecha_creacion: str
    fecha_pago: str | None = None


class PagoHistorialDetalleResponse(PagoHistorialItemResponse):
    proveedor_session_id: str | None = None
    proveedor_payment_intent_id: str | None = None
    checkout_url: str | None = None
    productos: list[PagoProductoDetalleResponse] = []
