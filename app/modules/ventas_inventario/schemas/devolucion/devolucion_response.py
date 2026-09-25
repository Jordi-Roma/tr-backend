from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class VentaDevolucionDetalleResponse(BaseModel):
    venta_detalle_id: int
    producto_variante_id: int
    producto: str
    talla: str
    color: str
    cantidad_vendida: int
    cantidad_disponible: int
    precio_unitario: Decimal
    subtotal: Decimal


class VentaDevolucionElegibleResponse(BaseModel):
    venta_id: int
    venta_codigo: str
    venta_tipo: str
    estado_venta: str
    fecha_venta: datetime
    sucursal_id: int
    sucursal: str
    metodo_pago: str | None = None
    total: Decimal
    detalles: list[VentaDevolucionDetalleResponse]


class DevolucionDetalleResponse(BaseModel):
    id: int
    venta_detalle_id: int
    producto_variante_id: int
    producto: str
    talla: str
    color: str
    cantidad_vendida: int
    cantidad_solicitada: int
    cantidad_aceptada: int
    cantidad_rechazada: int
    precio_unitario: Decimal
    subtotal_original: Decimal
    monto_aprobado: Decimal
    observacion: str | None = None
    inventario_repuesto: bool


class DevolucionResponse(BaseModel):
    id: int
    codigo: str
    venta_id: int
    venta_codigo: str
    cliente_id: int | None = None
    cliente_nombre: str | None = None
    cliente_correo: str | None = None
    sucursal_id: int
    sucursal: str
    estado: str
    motivo: str
    observacion: str | None = None
    monto_solicitado: Decimal
    monto_aprobado: Decimal
    moneda: str
    metodo_pago_original: str | None = None
    proveedor_pago_original: str | None = None
    metodo_reembolso: str | None = None
    proveedor_refund_id: str | None = None
    proveedor_refund_estado: str | None = None
    referencia_reembolso: str | None = None
    error_reembolso: str | None = None
    fecha_solicitud: datetime
    fecha_revision: datetime | None = None
    fecha_recepcion: datetime | None = None
    fecha_reembolso: datetime | None = None
    fecha_cancelacion: datetime | None = None
    cancelada_por_usuario_id: int | None = None
    reembolsada_por_usuario_id: int | None = None
    reembolso_iniciado_por_usuario_id: int | None = None
    fecha_reembolso_solicitud: datetime | None = None
    detalles: list[DevolucionDetalleResponse]
