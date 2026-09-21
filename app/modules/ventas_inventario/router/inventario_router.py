from fastapi import APIRouter, Depends

from app.modules.administracion.dependencies.empleado_access import (
    requerir_admin_o_encargado,
    requerir_admin_o_encargado_o_cajero,
)
from app.modules.ventas_inventario.schemas.inventario.inventario_schemas import (
    ActualizarStockMinimoRequest,
    CrearTransferenciaRequest,
    CrearVentaPresencialRequest,
    InventarioResponse,
    MovimientoInventarioRequest,
    MovimientoInventarioResponse,
    TransferenciaResponse,
    VentaPresencialResponse,
)
from app.modules.ventas_inventario.services.inventario_service import (
    actualizar_stock_minimo_service,
    crear_transferencia_service,
    crear_venta_service,
    listar_movimientos_service,
    listar_transferencias_service,
    listar_ventas_service,
    obtener_inventario_service,
    obtener_transferencia_service,
    obtener_venta_service,
    registrar_movimiento_service,
)

router = APIRouter(tags=["Ventas e inventario"])


@router.get("/api/v1/inventario", response_model=list[InventarioResponse])
def listar_inventario_endpoint(
    sucursal_id: int | None = None,
    producto_id: int | None = None,
    producto_variante_id: int | None = None,
    categoria_id: int | None = None,
    talla_id: int | None = None,
    color_id: int | None = None,
    solo_bajo_stock: bool = False,
    usuario_actual: dict[str, object] = Depends(requerir_admin_o_encargado_o_cajero),
) -> list[InventarioResponse]:
    return obtener_inventario_service(
        usuario_actual,
        {
            "sucursal_id": sucursal_id,
            "producto_id": producto_id,
            "producto_variante_id": producto_variante_id,
            "categoria_id": categoria_id,
            "talla_id": talla_id,
            "color_id": color_id,
            "solo_bajo_stock": solo_bajo_stock,
        },
    )


@router.patch("/api/v1/inventario/{inventario_id}/stock-minimo", response_model=InventarioResponse)
def actualizar_stock_minimo_endpoint(
    inventario_id: int,
    request: ActualizarStockMinimoRequest,
    usuario_actual: dict[str, object] = Depends(requerir_admin_o_encargado),
) -> InventarioResponse:
    return actualizar_stock_minimo_service(inventario_id, request)


@router.get("/api/v1/movimientos-inventario", response_model=list[MovimientoInventarioResponse])
def listar_movimientos_endpoint(
    sucursal_id: int | None = None,
    producto_variante_id: int | None = None,
    tipo: str | None = None,
    usuario_actual: dict[str, object] = Depends(requerir_admin_o_encargado),
) -> list[MovimientoInventarioResponse]:
    return listar_movimientos_service(
        usuario_actual,
        {"sucursal_id": sucursal_id, "producto_variante_id": producto_variante_id, "tipo": tipo},
    )


@router.post("/api/v1/movimientos-inventario", response_model=MovimientoInventarioResponse)
def registrar_movimiento_endpoint(
    request: MovimientoInventarioRequest,
    usuario_actual: dict[str, object] = Depends(requerir_admin_o_encargado),
) -> MovimientoInventarioResponse:
    return registrar_movimiento_service(usuario_actual, request)


@router.get("/api/v1/transferencias-stock", response_model=list[TransferenciaResponse])
def listar_transferencias_endpoint(
    sucursal_id: int | None = None,
    usuario_actual: dict[str, object] = Depends(requerir_admin_o_encargado),
) -> list[TransferenciaResponse]:
    return listar_transferencias_service(usuario_actual, sucursal_id)


@router.post("/api/v1/transferencias-stock", response_model=TransferenciaResponse)
def crear_transferencia_endpoint(
    request: CrearTransferenciaRequest,
    usuario_actual: dict[str, object] = Depends(requerir_admin_o_encargado),
) -> TransferenciaResponse:
    return crear_transferencia_service(usuario_actual, request)


@router.get("/api/v1/transferencias-stock/{transferencia_id}", response_model=TransferenciaResponse)
def obtener_transferencia_endpoint(
    transferencia_id: int,
    usuario_actual: dict[str, object] = Depends(requerir_admin_o_encargado),
) -> TransferenciaResponse:
    return obtener_transferencia_service(usuario_actual, transferencia_id)


@router.get("/api/v1/ventas-presenciales", response_model=list[VentaPresencialResponse])
def listar_ventas_endpoint(
    sucursal_id: int | None = None,
    usuario_actual: dict[str, object] = Depends(requerir_admin_o_encargado_o_cajero),
) -> list[VentaPresencialResponse]:
    return listar_ventas_service(usuario_actual, sucursal_id)


@router.post("/api/v1/ventas-presenciales", response_model=VentaPresencialResponse)
def crear_venta_endpoint(
    request: CrearVentaPresencialRequest,
    usuario_actual: dict[str, object] = Depends(requerir_admin_o_encargado_o_cajero),
) -> VentaPresencialResponse:
    return crear_venta_service(usuario_actual, request)


@router.get("/api/v1/ventas-presenciales/{venta_id}", response_model=VentaPresencialResponse)
def obtener_venta_endpoint(
    venta_id: int,
    usuario_actual: dict[str, object] = Depends(requerir_admin_o_encargado_o_cajero),
) -> VentaPresencialResponse:
    return obtener_venta_service(usuario_actual, venta_id)
