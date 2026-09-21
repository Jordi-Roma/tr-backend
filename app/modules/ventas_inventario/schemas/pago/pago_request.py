from pydantic import BaseModel, Field

from app.modules.ventas_inventario.schemas.delivery.delivery_request import DeliveryCheckoutRequest


class CrearCheckoutStripeRequest(BaseModel):
    sucursal_id: int | None = Field(default=None, gt=0)
    tipo_entrega: str = "RECOJO_SUCURSAL"
    delivery: DeliveryCheckoutRequest | None = None


class ConfirmarPagoPruebaRequest(BaseModel):
    aprobar: bool = True
