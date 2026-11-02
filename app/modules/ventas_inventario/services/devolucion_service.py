import os
from decimal import Decimal

from fastapi import HTTPException

from app.core.contexto_empresa import exigir_empresa_id
from app.modules.ventas_inventario.repositories import devolucion_repository as repo
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

DIAS_PLAZO_DEVOLUCION = max(1, int(os.getenv("DEVOLUCION_PLAZO_DIAS", "30")))
ROLES_ADMIN = {"ADMINISTRADOR"}
ROLES_SUCURSAL = {"ENCARGADO_SUCURSAL", "CAJERO"}


def listar_ventas_elegibles_service(usuario: dict[str, object]) -> list[VentaDevolucionElegibleResponse]:
    empresa_id = exigir_empresa_id(usuario)
    cliente_id = _cliente_id_opcional(usuario)
    if cliente_id is None:
        return []
    from .posventa_service import politica
    pol=politica(empresa_id)
    if not pol['devoluciones_habilitadas']:return []
    return [VentaDevolucionElegibleResponse(**item) for item in repo.listar_ventas_elegibles(cliente_id, pol['plazo_devoluciones'], empresa_id)]


def solicitar_devolucion_service(
    usuario: dict[str, object], venta_id: int, request: CrearDevolucionRequest
) -> DevolucionResponse:
    empresa_id = exigir_empresa_id(usuario)
    cliente_id = _cliente_id_requerido(usuario)
    try:
        result = repo.crear_devolucion(
            cliente_id,
            int(usuario["id"]),
            venta_id,
            request.motivo,
            request.observacion,
            [item.model_dump() for item in request.items],
            DIAS_PLAZO_DEVOLUCION,
            empresa_id,
            str(request.clave_operacion),
        )
        return DevolucionResponse(**result)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def listar_mis_devoluciones_service(usuario: dict[str, object], estado: str | None = None) -> list[DevolucionResponse]:
    empresa_id = exigir_empresa_id(usuario)
    cliente_id = _cliente_id_opcional(usuario)
    if cliente_id is None:
        return []
    return [DevolucionResponse(**item) for item in repo.listar_devoluciones_propias(cliente_id, empresa_id, estado)]


def listar_devoluciones_service(
    usuario: dict[str, object], estado: str | None, venta_id: int | None, cliente: str | None
) -> list[DevolucionResponse]:
    empresa_id = exigir_empresa_id(usuario)
    roles = _roles(usuario)
    ver_todas = "ADMINISTRADOR" in roles or _tiene_permiso(usuario, "devoluciones:ver_todos")
    if ver_todas:
        sucursal_id = None
    else:
        _exigir_permiso(usuario, "devoluciones:ver_sucursal")
        sucursal_id = _sucursal_id_requerida(usuario)
    items = repo.listar_devoluciones_sucursal(
        empresa_id=empresa_id,
        sucursal_id=sucursal_id,
        ver_todas=ver_todas,
        estado=_validar_estado(estado),
        venta_id=venta_id,
        cliente=cliente,
    )
    return [DevolucionResponse(**item) for item in items]


def obtener_devolucion_service(usuario: dict[str, object], devolucion_id: int, propia: bool = False) -> DevolucionResponse:
    item = repo.obtener_devolucion(devolucion_id, exigir_empresa_id(usuario))
    if item is None:
        raise HTTPException(status_code=404, detail="Devolución no encontrada.")
    if propia:
        cliente_id = _cliente_id_requerido(usuario)
        if int(item["cliente_id"] or 0) != cliente_id:
            raise HTTPException(status_code=404, detail="Devolución no encontrada.")
    else:
        _validar_acceso_sucursal(usuario, int(item["sucursal_id"]), "devoluciones:ver_sucursal")
    return DevolucionResponse(**item)


def revisar_devolucion_service(
    usuario: dict[str, object], devolucion_id: int, request: RevisarDevolucionRequest
) -> DevolucionResponse:
    item = _obtener_y_validar_accion(usuario, devolucion_id, "devoluciones:revisar")
    try:
        result = repo.revisar_devolucion(devolucion_id, int(usuario["id"]), request.aprobar, request.observacion, exigir_empresa_id(usuario))
        return DevolucionResponse(**result)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


def registrar_recepcion_service(
    usuario: dict[str, object], devolucion_id: int, request: RegistrarRecepcionDevolucionRequest
) -> DevolucionResponse:
    _obtener_y_validar_accion(usuario, devolucion_id, "devoluciones:recibir")
    try:
        result = repo.registrar_recepcion(
            devolucion_id,
            int(usuario["id"]),
            [item.model_dump() for item in request.items],
            exigir_empresa_id(usuario),
        )
        return DevolucionResponse(**result)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


def procesar_reembolso_service(usuario: dict[str, object], devolucion_id: int) -> DevolucionResponse:
    from .posventa_service import reembolsar
    return DevolucionResponse(**reembolsar(usuario,devolucion_id))


def registrar_reembolso_manual_service(
    usuario: dict[str, object], devolucion_id: int, request: RegistrarReembolsoManualRequest
) -> DevolucionResponse:
    _obtener_y_validar_accion(usuario, devolucion_id, "devoluciones:reembolsar")
    try:
        result = repo.registrar_reembolso_manual(
            devolucion_id,
            int(usuario["id"]),
            request.metodo,
            request.referencia,
            request.observacion,
            exigir_empresa_id(usuario),
        )
        return DevolucionResponse(**result)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


def cancelar_devolucion_service(usuario: dict[str, object], devolucion_id: int) -> DevolucionResponse:
    cliente_id = _cliente_id_requerido(usuario)
    try:
        result = repo.cancelar_devolucion(devolucion_id, cliente_id, int(usuario["id"]), exigir_empresa_id(usuario))
        return DevolucionResponse(**result)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


def procesar_evento_refund_stripe(
    refund_id: str, estado: str, mensaje_error: str | None = None, devolucion_id: int | None = None,
    empresa_id: int | None = None,
) -> None:
    if devolucion_id is not None:
        if empresa_id is not None:
            repo.actualizar_resultado_stripe_por_devolucion(devolucion_id, refund_id, estado, mensaje_error, empresa_id=empresa_id)
    else:
        repo.actualizar_resultado_stripe_por_refund(refund_id, estado, mensaje_error)


def _cliente_id_opcional(usuario: dict[str, object]) -> int | None:
    usuario_id = int(usuario["id"])
    return repo.cliente_id_por_usuario(usuario_id, exigir_empresa_id(usuario))


def _cliente_id_requerido(usuario: dict[str, object]) -> int:
    roles = _roles(usuario)
    usuario_id = int(usuario["id"])
    if "CLIENTE" not in roles and "ADMINISTRADOR" not in roles and not _tiene_permiso(usuario, "devoluciones:solicitar"):
        raise HTTPException(status_code=403, detail="Solo un cliente puede solicitar o consultar sus devoluciones.")
    cliente_id = repo.cliente_id_por_usuario(usuario_id, exigir_empresa_id(usuario))
    if cliente_id is None:
        raise HTTPException(status_code=403, detail="El usuario no tiene un perfil de cliente asociado.")
    return cliente_id


def _obtener_y_validar_accion(usuario: dict[str, object], devolucion_id: int, accion: str) -> dict:
    item = repo.obtener_devolucion(devolucion_id, exigir_empresa_id(usuario))
    if item is None:
        raise HTTPException(status_code=404, detail="Devolución no encontrada.")
    if item.get("tipo_operacion") == "CAMBIO":raise HTTPException(409,"Gestiona esta solicitud desde Cambios de prendas.")
    _validar_acceso_sucursal(usuario, int(item["sucursal_id"]), accion)
    return item


def _validar_acceso_sucursal(usuario: dict[str, object], sucursal_id: int, permiso_sucursal: str) -> None:
    roles = _roles(usuario)
    if "ADMINISTRADOR" in roles or _tiene_permiso(usuario, "devoluciones:ver_todos"):
        return
    accion_requerida = permiso_sucursal
    if not _tiene_permiso(usuario, accion_requerida):
        raise HTTPException(status_code=403, detail="No tiene permiso para gestionar devoluciones.")
    sucursal_usuario = repo.sucursal_id_por_usuario(int(usuario["id"]))
    if sucursal_usuario is None:
        raise HTTPException(status_code=403, detail="El usuario no tiene una sucursal asignada.")
    if sucursal_usuario != sucursal_id:
        raise HTTPException(status_code=404, detail="Devolución no encontrada.")


def _exigir_permiso(usuario: dict[str, object], accion: str) -> None:
    if "ADMINISTRADOR" not in _roles(usuario) and not _tiene_permiso(usuario, accion):
        raise HTTPException(status_code=403, detail="No tiene permiso para consultar devoluciones.")


def _tiene_permiso(usuario: dict[str, object], accion: str) -> bool:
    return repo.usuario_tiene_permiso(int(usuario["id"]), accion)


def _roles(usuario: dict[str, object]) -> set[str]:
    return {str(rol) for rol in usuario.get("roles", [])}


def _validar_estado(estado: str | None) -> str | None:
    if estado is None or not estado.strip():
        return None
    validos = {
        "SOLICITADA", "EN_REVISION", "APROBADA", "RECHAZADA", "REEMBOLSO_PENDIENTE",
        "ERROR_REEMBOLSO", "REEMBOLSADA", "CANCELADA", "ESPERA_ACEPTACION",
    }
    normalizado = estado.strip().upper()
    if normalizado not in validos:
        raise HTTPException(status_code=400, detail="Estado de devolución no válido.")
    return normalizado


def _sucursal_id_requerida(usuario: dict[str, object]) -> int:
    sucursal_id = repo.sucursal_id_por_usuario(int(usuario["id"]))
    if sucursal_id is None:
        raise HTTPException(status_code=403, detail="El usuario no tiene una sucursal asignada.")
    return sucursal_id
