from fastapi import APIRouter, Depends

from app.modules.autenticacion.dependencies.usuario_actual import obtener_usuario_actual
from app.modules.administracion.dependencies.empleado_access import requerir_admin_o_encargado
from app.modules.reservas.schemas.reservas.reserva_request import (
    CambiarEstadoReservaRequest,
    CrearReservaDesdeCarritoRequest,
    FinalizarReservaRequest,
    PagarReservaRequest,
)
from app.modules.reservas.schemas.reservas.reserva_response import ReservaPagoResponse, ReservaResponse
from app.modules.reservas.services.reserva_service import (
    cambiar_estado,
    cancelar_mi_reserva,
    crear_desde_carrito,
    finalizar_como_venta,
    finalizar_mi_reserva,
    listar_mis_reservas,
    listar_todas,
    obtener_mi_reserva,
    obtener_reserva,
    pagar_anticipo_con_stripe,
)

router = APIRouter(
    prefix="/api/v1/reservas",
    tags=["Reservas"],
)


@router.post("/desde-carrito", response_model=ReservaResponse)
def crear_reserva_desde_carrito_endpoint(
    request: CrearReservaDesdeCarritoRequest,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> ReservaResponse:
    return crear_desde_carrito(usuario_actual, request)


@router.get("/mis-reservas", response_model=list[ReservaResponse])
def listar_mis_reservas_endpoint(
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> list[ReservaResponse]:
    return listar_mis_reservas(usuario_actual)


@router.get("", response_model=list[ReservaResponse])
def listar_reservas_endpoint(
    estado: str | None = None,
    sucursal_id: int | None = None,
    usuario_actual: dict[str, object] = Depends(requerir_admin_o_encargado),
) -> list[ReservaResponse]:
    return listar_todas(usuario_actual, estado, sucursal_id)


@router.get("/{reserva_id}", response_model=ReservaResponse)
def obtener_reserva_endpoint(
    reserva_id: int,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> ReservaResponse:
    roles = [str(rol) for rol in usuario_actual.get("roles", [])]

    if "ADMINISTRADOR" in roles or "ENCARGADO_SUCURSAL" in roles:
        return obtener_reserva(usuario_actual, reserva_id)

    return obtener_mi_reserva(usuario_actual, reserva_id)


@router.patch("/{reserva_id}/cancelar", response_model=ReservaResponse)
def cancelar_reserva_endpoint(
    reserva_id: int,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> ReservaResponse:
    return cancelar_mi_reserva(usuario_actual, reserva_id)


@router.post("/{reserva_id}/anticipo/stripe", response_model=ReservaPagoResponse)
def pagar_anticipo_reserva_stripe_endpoint(
    reserva_id: int,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> ReservaPagoResponse:
    return pagar_anticipo_con_stripe(usuario_actual, reserva_id)


@router.post("/{reserva_id}/finalizar", response_model=ReservaPagoResponse)
def finalizar_mi_reserva_endpoint(
    reserva_id: int,
    request: PagarReservaRequest,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> ReservaPagoResponse:
    return finalizar_mi_reserva(usuario_actual, reserva_id, request)


@router.patch("/{reserva_id}/estado", response_model=ReservaResponse)
def cambiar_estado_reserva_endpoint(
    reserva_id: int,
    request: CambiarEstadoReservaRequest,
    usuario_actual: dict[str, object] = Depends(requerir_admin_o_encargado),
) -> ReservaResponse:
    return cambiar_estado(usuario_actual, reserva_id, request)


@router.post("/{reserva_id}/finalizar-venta", response_model=ReservaResponse)
def finalizar_reserva_como_venta_endpoint(
    reserva_id: int,
    request: FinalizarReservaRequest,
    usuario_actual: dict[str, object] = Depends(requerir_admin_o_encargado),
) -> ReservaResponse:
    return finalizar_como_venta(usuario_actual, reserva_id, request)
