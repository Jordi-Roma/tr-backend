from fastapi import APIRouter, Depends

from app.modules.autenticacion.dependencies.usuario_actual import obtener_usuario_actual
from app.modules.ventas_inventario.schemas.devolucion.devolucion_request import (
    CrearDevolucionRequest,
    RegistrarRecepcionDevolucionRequest,
    RegistrarReembolsoManualRequest,
    RevisarDevolucionRequest,
)
from app.modules.ventas_inventario.schemas.devolucion.devolucion_response import (
    DevolucionResponse,
    VentaDevolucionElegibleResponse,
)
from app.modules.ventas_inventario.services.devolucion_service import (
    cancelar_devolucion_service,
    listar_devoluciones_service,
    listar_mis_devoluciones_service,
    listar_ventas_elegibles_service,
    obtener_devolucion_service,
    procesar_reembolso_service,
    registrar_recepcion_service,
    registrar_reembolso_manual_service,
    revisar_devolucion_service,
    solicitar_devolucion_service,
)

router = APIRouter(prefix="/api/v1/devoluciones", tags=["Devoluciones"])


@router.get("/ventas-elegibles", response_model=list[VentaDevolucionElegibleResponse])
def listar_ventas_elegibles(
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> list[VentaDevolucionElegibleResponse]:
    return listar_ventas_elegibles_service(usuario_actual)


@router.get("/mis-devoluciones", response_model=list[DevolucionResponse])
def listar_mis_devoluciones(
    estado: str | None = None,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> list[DevolucionResponse]:
    return listar_mis_devoluciones_service(usuario_actual, estado)


@router.get("/mis-devoluciones/{devolucion_id}", response_model=DevolucionResponse)
def obtener_mi_devolucion(
    devolucion_id: int,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> DevolucionResponse:
    return obtener_devolucion_service(usuario_actual, devolucion_id, propia=True)


@router.patch("/mis-devoluciones/{devolucion_id}/cancelar", response_model=DevolucionResponse)
def cancelar_mi_devolucion(
    devolucion_id: int,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> DevolucionResponse:
    return cancelar_devolucion_service(usuario_actual, devolucion_id)


@router.get("", response_model=list[DevolucionResponse])
def listar_devoluciones(
    estado: str | None = None,
    venta_id: int | None = None,
    cliente: str | None = None,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> list[DevolucionResponse]:
    return listar_devoluciones_service(usuario_actual, estado, venta_id, cliente)


@router.get("/{devolucion_id}", response_model=DevolucionResponse)
def obtener_devolucion(
    devolucion_id: int,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> DevolucionResponse:
    return obtener_devolucion_service(usuario_actual, devolucion_id)


@router.post("/ventas/{venta_id}", response_model=DevolucionResponse, status_code=201)
def solicitar_devolucion(
    venta_id: int,
    request: CrearDevolucionRequest,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> DevolucionResponse:
    return solicitar_devolucion_service(usuario_actual, venta_id, request)


@router.patch("/{devolucion_id}/revision", response_model=DevolucionResponse)
def revisar_devolucion(
    devolucion_id: int,
    request: RevisarDevolucionRequest,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> DevolucionResponse:
    return revisar_devolucion_service(usuario_actual, devolucion_id, request)


@router.patch("/{devolucion_id}/recepcion", response_model=DevolucionResponse)
def registrar_recepcion(
    devolucion_id: int,
    request: RegistrarRecepcionDevolucionRequest,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> DevolucionResponse:
    return registrar_recepcion_service(usuario_actual, devolucion_id, request)


@router.post("/{devolucion_id}/reembolso", response_model=DevolucionResponse)
def procesar_reembolso(
    devolucion_id: int,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> DevolucionResponse:
    return procesar_reembolso_service(usuario_actual, devolucion_id)


@router.post("/{devolucion_id}/reembolso/manual", response_model=DevolucionResponse)
def registrar_reembolso_manual(
    devolucion_id: int,
    request: RegistrarReembolsoManualRequest,
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> DevolucionResponse:
    return registrar_reembolso_manual_service(usuario_actual, devolucion_id, request)
