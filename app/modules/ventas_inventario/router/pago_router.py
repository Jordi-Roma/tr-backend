from fastapi import APIRouter, Depends, Request

from app.modules.autenticacion.dependencies.usuario_actual import obtener_usuario_actual
from app.modules.ventas_inventario.schemas.pago.pago_request import (
    ConfirmarPagoPruebaRequest,
    CrearCheckoutStripeRequest,
)
from app.modules.ventas_inventario.schemas.pago.pago_response import (
    CheckoutStripeResponse,
    OrdenPagoResponse,
    PagoHistorialDetalleResponse,
    PagoHistorialItemResponse,
)
from app.modules.ventas_inventario.services.pago_service import (
    confirmar_pago_prueba_service,
    crear_checkout_stripe_service,
    listar_mis_pagos_service,
    listar_pagos_service,
    obtener_mi_pago_service,
    obtener_orden_service,
    obtener_pago_service,
    webhook_stripe_service,
)

router = APIRouter(prefix="/api/v1/pagos", tags=["Pagos digitales"])


@router.get("/mis-pagos", response_model=list[PagoHistorialItemResponse])
def listar_mis_pagos(
    estado: str | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> list[PagoHistorialItemResponse]:
    return listar_mis_pagos_service(usuario_actual, estado, fecha_desde, fecha_hasta)


@router.get("/mis-pagos/{orden_id}", response_model=PagoHistorialDetalleResponse)
def obtener_mi_pago(
    orden_id: int,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> PagoHistorialDetalleResponse:
    return obtener_mi_pago_service(usuario_actual, orden_id)


@router.get("", response_model=list[PagoHistorialItemResponse])
def listar_pagos(
    estado: str | None = None,
    metodo: str | None = None,
    proveedor: str | None = None,
    cliente: str | None = None,
    sucursal_id: int | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> list[PagoHistorialItemResponse]:
    return listar_pagos_service(
        usuario_actual,
        estado,
        metodo,
        proveedor,
        cliente,
        sucursal_id,
        fecha_desde,
        fecha_hasta,
    )


@router.get("/{orden_id}", response_model=PagoHistorialDetalleResponse)
def obtener_pago(
    orden_id: int,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> PagoHistorialDetalleResponse:
    return obtener_pago_service(usuario_actual, orden_id)


@router.post("/stripe/checkout", response_model=CheckoutStripeResponse)
def crear_checkout_stripe(
    request: CrearCheckoutStripeRequest,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> CheckoutStripeResponse:
    return crear_checkout_stripe_service(usuario_actual, request)


@router.get("/orden/{orden_id}", response_model=OrdenPagoResponse)
def obtener_orden_pago(
    orden_id: int,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> OrdenPagoResponse:
    return obtener_orden_service(usuario_actual, orden_id)


@router.post("/stripe/confirmar-prueba/{orden_id}", response_model=OrdenPagoResponse)
def confirmar_pago_prueba(
    orden_id: int,
    request: ConfirmarPagoPruebaRequest,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> OrdenPagoResponse:
    return confirmar_pago_prueba_service(usuario_actual, orden_id, request.aprobar)


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request) -> dict[str, str]:
    return await webhook_stripe_service(request)
