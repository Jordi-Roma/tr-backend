from fastapi import HTTPException, status

from app.core.contexto_empresa import exigir_empresa_id

from app.modules.ventas_inventario.repositories.inventario_repository import (
    actualizar_stock_minimo,
    crear_transferencia,
    crear_venta_presencial,
    listar_inventario,
    listar_movimientos,
    listar_transferencias,
    listar_ventas,
    obtener_sucursal_empleado,
    sucursal_pertenece_empresa,
    obtener_inventario,
    obtener_transferencia,
    obtener_venta,
    registrar_movimiento_manual,
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

ROLES_STAFF = {"ENCARGADO_SUCURSAL", "CAJERO", "PERSONAL_VENTAS"}


def obtener_inventario_service(
    usuario_actual: dict[str, object],
    filtros: dict[str, object],
) -> list[InventarioResponse]:
    filtros = _forzar_sucursal_si_no_admin(usuario_actual, filtros)
    return [InventarioResponse(**row) for row in listar_inventario(filtros, exigir_empresa_id(usuario_actual))]


def actualizar_stock_minimo_service(
    usuario_actual: dict[str, object],
    inventario_id: int,
    request: ActualizarStockMinimoRequest,
) -> InventarioResponse:
    empresa_id = exigir_empresa_id(usuario_actual)
    actual = obtener_inventario(inventario_id, empresa_id)
    if actual is None:
        raise HTTPException(status_code=404, detail="Inventario no encontrado.")
    _validar_sucursal_operacion(usuario_actual, int(actual["sucursal_id"]))
    inventario = actualizar_stock_minimo(inventario_id, request.stock_minimo, empresa_id)
    if inventario is None:
        raise HTTPException(status_code=404, detail="Inventario no encontrado.")
    return InventarioResponse(**inventario)


def listar_movimientos_service(
    usuario_actual: dict[str, object],
    filtros: dict[str, object],
) -> list[MovimientoInventarioResponse]:
    filtros = _forzar_sucursal_si_no_admin(usuario_actual, filtros)
    return [MovimientoInventarioResponse(**row) for row in listar_movimientos(filtros, exigir_empresa_id(usuario_actual))]


def registrar_movimiento_service(
    usuario_actual: dict[str, object],
    request: MovimientoInventarioRequest,
) -> MovimientoInventarioResponse:
    sucursal_id = _validar_sucursal_operacion(usuario_actual, request.sucursal_id)
    tipo = request.tipo.upper()
    if tipo not in {"ENTRADA", "SALIDA", "AJUSTE_POSITIVO", "AJUSTE_NEGATIVO"}:
        raise HTTPException(status_code=400, detail="Tipo de movimiento manual invalido.")
    if request.proveedor_id is not None and tipo != "ENTRADA":
        raise HTTPException(status_code=400, detail="Solo las entradas de inventario pueden asociarse a un proveedor.")
    try:
        row = registrar_movimiento_manual(
            int(usuario_actual["id"]),
            exigir_empresa_id(usuario_actual),
            sucursal_id,
            request.producto_variante_id,
            tipo,
            request.cantidad,
            request.motivo,
            request.proveedor_id,
        )
        return MovimientoInventarioResponse(**row)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def crear_transferencia_service(
    usuario_actual: dict[str, object],
    request: CrearTransferenciaRequest,
) -> TransferenciaResponse:
    origen = _validar_sucursal_operacion(usuario_actual, request.sucursal_origen_id)
    try:
        transferencia = crear_transferencia(
            int(usuario_actual["id"]),
            exigir_empresa_id(usuario_actual),
            origen,
            request.sucursal_destino_id,
            request.observacion,
            [item.model_dump() for item in request.items],
        )
        return TransferenciaResponse(**transferencia)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def listar_transferencias_service(
    usuario_actual: dict[str, object],
    sucursal_id: int | None,
) -> list[TransferenciaResponse]:
    sucursal = _sucursal_permitida(usuario_actual, sucursal_id)
    return [TransferenciaResponse(**row) for row in listar_transferencias(exigir_empresa_id(usuario_actual), sucursal)]


def obtener_transferencia_service(
    usuario_actual: dict[str, object],
    transferencia_id: int,
) -> TransferenciaResponse:
    transferencia = obtener_transferencia(transferencia_id, exigir_empresa_id(usuario_actual))
    if transferencia is None:
        raise HTTPException(status_code=404, detail="Transferencia no encontrada.")
    sucursal = _sucursal_permitida(usuario_actual, None)
    if sucursal is not None and sucursal not in {
        int(transferencia["sucursal_origen_id"]),
        int(transferencia["sucursal_destino_id"]),
    }:
        raise HTTPException(status_code=404, detail="Transferencia no encontrada.")
    return TransferenciaResponse(**transferencia)


def crear_venta_service(
    usuario_actual: dict[str, object],
    request: CrearVentaPresencialRequest,
) -> VentaPresencialResponse:
    sucursal_id = _validar_sucursal_operacion(usuario_actual, request.sucursal_id)
    try:
        venta = crear_venta_presencial(
            int(usuario_actual["id"]),
            exigir_empresa_id(usuario_actual),
            sucursal_id,
            request.cliente_id,
            request.metodo_pago,
            request.observacion,
            [item.model_dump() for item in request.items],
        )
        return VentaPresencialResponse(**venta)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def listar_ventas_service(
    usuario_actual: dict[str, object],
    sucursal_id: int | None,
) -> list[VentaPresencialResponse]:
    sucursal = _sucursal_permitida(usuario_actual, sucursal_id)
    return [VentaPresencialResponse(**row) for row in listar_ventas(exigir_empresa_id(usuario_actual), sucursal)]


def obtener_venta_service(usuario_actual: dict[str, object], venta_id: int) -> VentaPresencialResponse:
    venta = obtener_venta(venta_id, exigir_empresa_id(usuario_actual))
    if venta is None:
        raise HTTPException(status_code=404, detail="Venta no encontrada.")
    sucursal = _sucursal_permitida(usuario_actual, None)
    if sucursal is not None and int(venta["sucursal_id"]) != sucursal:
        raise HTTPException(status_code=404, detail="Venta no encontrada.")
    return VentaPresencialResponse(**venta)


def _roles(usuario_actual: dict[str, object]) -> set[str]:
    return {str(rol) for rol in usuario_actual.get("roles", [])}


def _sucursal_permitida(usuario_actual: dict[str, object], sucursal_solicitada: int | None) -> int | None:
    roles = _roles(usuario_actual)
    if "ADMINISTRADOR" in roles:
        return sucursal_solicitada
    if roles.intersection(ROLES_STAFF):
        sucursal = obtener_sucursal_empleado(int(usuario_actual["id"]), exigir_empresa_id(usuario_actual))
        if sucursal is None:
            raise HTTPException(status_code=403, detail="El usuario no tiene sucursal asignada.")
        return sucursal
    raise HTTPException(status_code=403, detail="No tiene permisos para realizar esta accion.")


def _validar_sucursal_operacion(usuario_actual: dict[str, object], sucursal_id: int) -> int:
    if not sucursal_pertenece_empresa(sucursal_id, exigir_empresa_id(usuario_actual)):
        raise HTTPException(status_code=404, detail="Sucursal no encontrada en esta empresa.")
    sucursal = _sucursal_permitida(usuario_actual, sucursal_id)
    if sucursal is not None and sucursal != sucursal_id:
        raise HTTPException(status_code=403, detail="No puede operar sobre otra sucursal.")
    return sucursal_id


def _forzar_sucursal_si_no_admin(
    usuario_actual: dict[str, object],
    filtros: dict[str, object],
) -> dict[str, object]:
    filtros = dict(filtros)
    sucursal = _sucursal_permitida(usuario_actual, filtros.get("sucursal_id"))
    if sucursal is not None:
        filtros["sucursal_id"] = sucursal
    return filtros
