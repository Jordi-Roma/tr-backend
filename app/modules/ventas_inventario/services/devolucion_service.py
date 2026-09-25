import os
from decimal import Decimal

from fastapi import HTTPException

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
    cliente_id = _cliente_id_requerido(usuario)
    return [VentaDevolucionElegibleResponse(**item) for item in repo.listar_ventas_elegibles(cliente_id, DIAS_PLAZO_DEVOLUCION)]


def solicitar_devolucion_service(
    usuario: dict[str, object], venta_id: int, request: CrearDevolucionRequest
) -> DevolucionResponse:
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
        )
        return DevolucionResponse(**result)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def listar_mis_devoluciones_service(usuario: dict[str, object], estado: str | None = None) -> list[DevolucionResponse]:
    cliente_id = _cliente_id_requerido(usuario)
    return [DevolucionResponse(**item) for item in repo.listar_devoluciones_propias(cliente_id, estado)]


def listar_devoluciones_service(
    usuario: dict[str, object], estado: str | None, venta_id: int | None, cliente: str | None
) -> list[DevolucionResponse]:
    ver_todas = _tiene_permiso(usuario, "devoluciones:ver_todos")
    if ver_todas:
        sucursal_id = None
    else:
        _exigir_permiso(usuario, "devoluciones:ver_sucursal")
        sucursal_id = _sucursal_id_requerida(usuario)
    items = repo.listar_devoluciones_sucursal(
        sucursal_id=sucursal_id,
        ver_todas=ver_todas,
        estado=_validar_estado(estado),
        venta_id=venta_id,
        cliente=cliente,
    )
    return [DevolucionResponse(**item) for item in items]


def obtener_devolucion_service(usuario: dict[str, object], devolucion_id: int, propia: bool = False) -> DevolucionResponse:
    item = repo.obtener_devolucion(devolucion_id)
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
        result = repo.revisar_devolucion(devolucion_id, int(usuario["id"]), request.aprobar, request.observacion)
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
        )
        return DevolucionResponse(**result)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


def procesar_reembolso_service(usuario: dict[str, object], devolucion_id: int) -> DevolucionResponse:
    _obtener_y_validar_accion(usuario, devolucion_id, "devoluciones:reembolsar")
    try:
        devolucion = repo.preparar_reembolso_stripe(devolucion_id, int(usuario["id"]))
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if devolucion is None:
        raise HTTPException(
            status_code=400,
            detail="Esta devolución requiere un reembolso manual; registra el método y la referencia del comprobante.",
        )
    if devolucion["estado"] == "REEMBOLSADA":
        result = repo.obtener_devolucion(devolucion_id)
        return DevolucionResponse(**result)

    secret_key = os.getenv("STRIPE_SECRET_KEY", "")
    if not secret_key:
        repo.marcar_error_reembolso(devolucion_id, "STRIPE_SECRET_KEY no está configurada.")
        raise HTTPException(status_code=503, detail="Stripe no está configurado para procesar este reembolso.")
    try:
        if secret_key.startswith("sk_test_placeholder") or secret_key == "MODO_PRUEBA":
            refund_id = f"re_simulada_{devolucion_id}"
            estado_stripe = "succeeded"
        else:
            import stripe

            stripe.api_key = secret_key
            amount = int((Decimal(devolucion["monto_aprobado"]) * 100).quantize(Decimal("1")))
            if amount <= 0:
                raise ValueError("El importe del reembolso debe ser mayor a cero.")
            refund = stripe.Refund.create(
                payment_intent=str(devolucion["proveedor_payment_intent_id"]),
                amount=amount,
                idempotency_key=str(devolucion["clave_idempotencia"]),
                metadata={"devolucion_id": str(devolucion_id), "venta_id": str(devolucion["venta_id"])},
            )
            refund_id = str(refund.id)
            estado_stripe = str(refund.status or "pending")
        result = repo.actualizar_resultado_stripe(
            devolucion_id, refund_id, estado_stripe, usuario_id=int(usuario["id"])
        )
        if result is None:
            result = repo.obtener_devolucion(devolucion_id)
            if result is None or result["estado"] != "REEMBOLSADA":
                raise HTTPException(status_code=409, detail="No se pudo conciliar el resultado confirmado por Stripe.")
        return DevolucionResponse(**result)
    except HTTPException:
        raise
    except Exception as error:
        repo.marcar_error_reembolso(devolucion_id, str(error))
        raise HTTPException(status_code=502, detail="Stripe no pudo confirmar el reembolso. Se puede reintentar de forma segura.") from error


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
        )
        return DevolucionResponse(**result)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


def cancelar_devolucion_service(usuario: dict[str, object], devolucion_id: int) -> DevolucionResponse:
    cliente_id = _cliente_id_requerido(usuario)
    try:
        result = repo.cancelar_devolucion(devolucion_id, cliente_id, int(usuario["id"]))
        return DevolucionResponse(**result)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


def procesar_evento_refund_stripe(
    refund_id: str, estado: str, mensaje_error: str | None = None, devolucion_id: int | None = None
) -> None:
    if devolucion_id is not None:
        repo.actualizar_resultado_stripe_por_devolucion(devolucion_id, refund_id, estado, mensaje_error)
    else:
        repo.actualizar_resultado_stripe_por_refund(refund_id, estado, mensaje_error)


def _cliente_id_requerido(usuario: dict[str, object]) -> int:
    roles = _roles(usuario)
    usuario_id = int(usuario["id"])
    if "CLIENTE" not in roles and not _tiene_permiso(usuario, "devoluciones:solicitar"):
        raise HTTPException(status_code=403, detail="Solo un cliente puede solicitar o consultar sus devoluciones.")
    cliente_id = repo.cliente_id_por_usuario(usuario_id)
    if cliente_id is None:
        raise HTTPException(status_code=403, detail="El usuario no tiene un perfil de cliente asociado.")
    return cliente_id


def _obtener_y_validar_accion(usuario: dict[str, object], devolucion_id: int, accion: str) -> dict:
    item = repo.obtener_devolucion(devolucion_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Devolución no encontrada.")
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
        "ERROR_REEMBOLSO", "REEMBOLSADA", "CANCELADA",
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
