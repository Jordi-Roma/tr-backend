from decimal import Decimal
from pydantic import BaseModel


class CheckoutStripeResponse(BaseModel):
    modo_pago: str = "LEGADO"
    confirmacion_prueba: bool = False
    orden_id: int
    venta_id: int
    estado: str
    checkout_url: str


class CheckoutQrResponse(BaseModel):
    modo_pago: str = "LEGADO"
    confirmacion_prueba: bool = False
    orden_id: int
    venta_id: int
    monto_total: Decimal
    moneda: str = "BOB"
    estado: str
    qr_payload: str
    alias: str = "StyleAR S.R.L."
    banco: str = "Banco de Crédito BCP"
    cuenta: str = "10000000452319"
    titular: str = "StyleAR Bolivia S.R.L."
    glosa: str
    vencimiento: str


class OrdenPagoResponse(BaseModel):
    modo_pago: str = 'LEGADO'
    confirmacion_prueba: bool = False
    pago_recibido: bool = False
    motivo_incidencia: str | None = None
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
    tipo_compra: str = 'UNIDAD'
    paquete_origen_id: int | None = None
    descuento_mayorista: Decimal | None = None
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
