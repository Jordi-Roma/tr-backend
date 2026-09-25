import os
from decimal import Decimal

from fastapi import HTTPException, Request, status

from app.modules.ventas_inventario.repositories import pago_repository as repo
from app.modules.ventas_inventario.schemas.pago.pago_request import CrearCheckoutStripeRequest
from app.modules.ventas_inventario.schemas.pago.pago_response import (
    CheckoutStripeResponse,
    OrdenPagoResponse,
    PagoHistorialDetalleResponse,
    PagoHistorialItemResponse,
    PagoProductoDetalleResponse,
)
from app.modules.ventas_inventario.services.delivery_service import preparar_delivery_para_checkout


def crear_checkout_stripe_service(usuario_actual: dict[str, object], request: CrearCheckoutStripeRequest) -> CheckoutStripeResponse:
    cliente_id = _cliente_id_obligatorio(usuario_actual)
    try:
        tipo_entrega = request.tipo_entrega.strip().upper()
        if tipo_entrega not in {"RECOJO_SUCURSAL", "DELIVERY"}:
            raise ValueError("Tipo de entrega no valido.")
        delivery = preparar_delivery_para_checkout(request.delivery) if tipo_entrega == "DELIVERY" else None
        sucursal_id = int(delivery["sucursal_id"]) if delivery else request.sucursal_id
        orden = repo.crear_orden_desde_carrito(cliente_id, int(usuario_actual["id"]), sucursal_id, delivery)
        session = _crear_session_stripe(orden)
        orden = repo.actualizar_checkout_stripe(
            int(orden["id"]),
            str(session["id"]),
            str(session["url"]),
            session.get("payment_intent"),
        )
        return _checkout_response(orden)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


def obtener_orden_service(usuario_actual: dict[str, object], orden_id: int) -> OrdenPagoResponse:
    orden = repo.obtener_orden_pago(orden_id)
    if orden is None:
        raise HTTPException(status_code=404, detail="Orden de pago no encontrada.")
    _validar_acceso_orden(usuario_actual, orden)
    return _orden_response(orden)


def listar_mis_pagos_service(
    usuario_actual: dict[str, object],
    estado: str | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
) -> list[PagoHistorialItemResponse]:
    _validar_permiso_historial(usuario_actual, "propios")
    cliente_id = _cliente_id_usuario(usuario_actual)
    pagos = repo.listar_historial_pagos(
        cliente_id=cliente_id,
        estado=estado,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )
    return [_historial_item_response(pago) for pago in pagos]


def obtener_mi_pago_service(
    usuario_actual: dict[str, object],
    orden_id: int,
) -> PagoHistorialDetalleResponse:
    _validar_permiso_historial(usuario_actual, "propios")
    cliente_id = _cliente_id_usuario(usuario_actual)
    pago = repo.obtener_historial_pago_detalle(orden_id)
    if pago is None or int(pago["cliente_id"]) != cliente_id:
        raise HTTPException(status_code=404, detail="Pago no encontrado.")
    return _historial_detalle_response(pago)


def listar_pagos_service(
    usuario_actual: dict[str, object],
    estado: str | None = None,
    metodo: str | None = None,
    proveedor: str | None = None,
    cliente: str | None = None,
    sucursal_id: int | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
) -> list[PagoHistorialItemResponse]:
    roles = _roles(usuario_actual)
    if _tiene_acceso_todos_pagos(usuario_actual):
        pagos = repo.listar_historial_pagos(
            sucursal_id=sucursal_id,
            estado=estado,
            metodo=metodo,
            proveedor=proveedor,
            cliente=cliente,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
        )
        return [_historial_item_response(pago) for pago in pagos]

    if "ENCARGADO_SUCURSAL" in roles or _usuario_tiene_permiso(usuario_actual, "pagos:ver_sucursal"):
        sucursal_permitida = _sucursal_id_encargado(usuario_actual)
        if sucursal_id is not None and sucursal_id != sucursal_permitida:
            raise HTTPException(status_code=403, detail="Solo puede consultar pagos de su sucursal.")
        pagos = repo.listar_historial_pagos(
            sucursal_id=sucursal_permitida,
            estado=estado,
            metodo=metodo,
            proveedor=proveedor,
            cliente=cliente,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
        )
        return [_historial_item_response(pago) for pago in pagos]

    raise HTTPException(status_code=403, detail="No tiene permisos para consultar pagos.")


def obtener_pago_service(
    usuario_actual: dict[str, object],
    orden_id: int,
) -> PagoHistorialDetalleResponse:
    pago = repo.obtener_historial_pago_detalle(orden_id)
    if pago is None:
        raise HTTPException(status_code=404, detail="Pago no encontrado.")

    roles = _roles(usuario_actual)
    if _tiene_acceso_todos_pagos(usuario_actual):
        return _historial_detalle_response(pago)

    if "ENCARGADO_SUCURSAL" in roles or _usuario_tiene_permiso(usuario_actual, "pagos:ver_sucursal"):
        sucursal_permitida = _sucursal_id_encargado(usuario_actual)
        if int(pago["sucursal_id"]) != sucursal_permitida:
            raise HTTPException(status_code=404, detail="Pago no encontrado.")
        return _historial_detalle_response(pago)

    raise HTTPException(status_code=403, detail="No tiene permisos para consultar pagos.")


async def webhook_stripe_service(request: Request) -> dict[str, str]:
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    try:
        import stripe
    except ModuleNotFoundError as error:
        raise HTTPException(status_code=503, detail="La dependencia stripe no esta instalada.") from error

    if endpoint_secret:
        try:
            event = stripe.Webhook.construct_event(payload, signature, endpoint_secret)
        except Exception as error:
            raise HTTPException(status_code=400, detail="Webhook de Stripe invalido.") from error
    else:
        event = await request.json()

    tipo = event.get("type")
    data = event.get("data", {}).get("object", {})
    if tipo == "checkout.session.completed":
        session_id = data.get("id")
        if session_id:
            orden = repo.obtener_orden_por_session(session_id)
            if orden:
                repo.marcar_orden_pagada(int(orden["id"]))
    elif tipo == "checkout.session.expired":
        session_id = data.get("id")
        if session_id and (orden := repo.obtener_orden_por_session(session_id)):
            repo.marcar_orden_no_pagada(int(orden["id"]), "EXPIRADO", "CANCELADA")
    elif tipo == "payment_intent.payment_failed":
        payment_intent = data.get("id")
        if payment_intent:
            # Stripe normalmente relaciona el fallo con la sesion; se deja como evento aceptado.
            pass
    elif tipo in {"refund.created", "refund.updated", "refund.failed"}:
        refund_id = data.get("id")
        refund_estado = data.get("status") or ("failed" if tipo == "refund.failed" else "pending")
        metadata = data.get("metadata") or {}
        devolucion_id = metadata.get("devolucion_id")
        fallo = data.get("failure_reason")
        if refund_id and devolucion_id:
            from app.modules.ventas_inventario.services.devolucion_service import (
                procesar_evento_refund_stripe,
            )

            procesar_evento_refund_stripe(
                str(refund_id), str(refund_estado), str(fallo) if fallo else None,
                int(devolucion_id),
            )
        elif refund_id:
            from app.modules.ventas_inventario.repositories import devolucion_repository

            devolucion_repository.actualizar_resultado_stripe_por_refund(
                str(refund_id), str(refund_estado), str(fallo) if fallo else None
            )
    return {"status": "ok"}


def confirmar_pago_prueba_service(usuario_actual: dict[str, object], orden_id: int, aprobar: bool) -> OrdenPagoResponse:
    orden = repo.obtener_orden_pago(orden_id)
    if orden is None:
        raise HTTPException(status_code=404, detail="Orden de pago no encontrada.")
    _validar_acceso_orden(usuario_actual, orden)
    try:
        if aprobar:
            return _orden_response(repo.marcar_orden_pagada(orden_id, int(usuario_actual["id"])))
        return _orden_response(repo.marcar_orden_no_pagada(orden_id, "RECHAZADO", "RECHAZADA"))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def _crear_session_stripe(orden: dict) -> dict:
    secret_key = os.getenv("STRIPE_SECRET_KEY")
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:4200")
    if not secret_key:
        raise HTTPException(status_code=503, detail="STRIPE_SECRET_KEY no esta configurada en el backend.")

    # Si se mantiene la clave placeholder o modo prueba, retornar sesión simulada
    if secret_key.startswith("sk_test_placeholder") or secret_key == "MODO_PRUEBA":
        return {
            "id": f"cs_test_simulada_{orden['id']}",
            "url": f"{frontend_url}/pago/resultado?orden_id={orden['id']}&estado=success",
            "payment_intent": f"pi_simulada_{orden['id']}",
        }

    try:
        import stripe
    except ModuleNotFoundError as error:
        raise HTTPException(status_code=503, detail="La dependencia stripe no esta instalada.") from error

    try:
        stripe.api_key = secret_key
        if str(orden.get("concepto") or "COMPRA") in {"RESERVA_ANTICIPO", "RESERVA_SALDO"}:
            line_items = [_orden_reserva_line_item(orden)]
        else:
            line_items = [_line_item(item) for item in orden["items"]]
        costo_delivery = Decimal(str(orden.get("costo_delivery") or 0))
        if costo_delivery > 0:
            line_items.append(_delivery_line_item(costo_delivery))

        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=line_items,
            success_url=f"{frontend_url}/pago/resultado?orden_id={orden['id']}&estado=success",
            cancel_url=f"{frontend_url}/pago/cancelado?orden_id={orden['id']}&estado=cancel",
            metadata={"orden_id": str(orden["id"]), "venta_id": str(orden["venta_id"])},
        )
        return {"id": session.id, "url": session.url, "payment_intent": session.payment_intent}
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=f"Error al conectar con Stripe: {str(error)}. Verifica tu STRIPE_SECRET_KEY en el backend.",
        ) from error


def _line_item(item: dict) -> dict:
    precio = Decimal(item["precio_unitario"])
    return {
        "quantity": int(item["cantidad"]),
        "price_data": {
            "currency": "bob",
            "unit_amount": int((precio * 100).quantize(Decimal("1"))),
            "product_data": {
                "name": str(item["producto"]),
                "description": f"{item['categoria']} - {item['talla']} / {item['color']}",
            },
        },
    }


def _delivery_line_item(costo_delivery: Decimal) -> dict:
    return {
        "quantity": 1,
        "price_data": {
            "currency": "bob",
            "unit_amount": int((costo_delivery * 100).quantize(Decimal("1"))),
            "product_data": {
                "name": "Delivery",
                "description": "Envio a domicilio",
            },
        },
    }


def _orden_reserva_line_item(orden: dict) -> dict:
    monto = Decimal(str(orden.get("monto_total") or 0))
    concepto = str(orden.get("concepto") or "")
    nombre = "Anticipo de reserva" if concepto == "RESERVA_ANTICIPO" else "Saldo de reserva"
    return {
        "quantity": 1,
        "price_data": {
            "currency": "bob",
            "unit_amount": int((monto * 100).quantize(Decimal("1"))),
            "product_data": {
                "name": nombre,
                "description": "Pago de reserva StyleAR",
            },
        },
    }


def _cliente_id_obligatorio(usuario_actual: dict[str, object]) -> int:
    roles = {str(rol) for rol in usuario_actual.get("roles", [])}
    if "CLIENTE" not in roles:
        raise HTTPException(status_code=403, detail="Solo clientes pueden pagar compras digitales.")
    cliente_id = repo.obtener_cliente_id_por_usuario(int(usuario_actual["id"]))
    if cliente_id is None:
        raise HTTPException(status_code=403, detail="El usuario no tiene cliente asociado.")
    return cliente_id


def _cliente_id_usuario(usuario_actual: dict[str, object]) -> int:
    cliente_id = repo.obtener_cliente_id_por_usuario(int(usuario_actual["id"]))
    if cliente_id is None:
        raise HTTPException(status_code=403, detail="El usuario no tiene cliente asociado.")
    return cliente_id


def _validar_acceso_orden(usuario_actual: dict[str, object], orden: dict) -> None:
    roles = {str(rol) for rol in usuario_actual.get("roles", [])}
    if "ADMINISTRADOR" in roles:
        return
    cliente_id = repo.obtener_cliente_id_por_usuario(int(usuario_actual["id"]))
    if cliente_id is None or int(orden["cliente_id"]) != cliente_id:
        raise HTTPException(status_code=404, detail="Orden de pago no encontrada.")


def _validar_permiso_historial(usuario_actual: dict[str, object], alcance: str) -> None:
    roles = _roles(usuario_actual)
    if alcance == "propios" and (
        "CLIENTE" in roles or _usuario_tiene_permiso(usuario_actual, "pagos:ver_propios")
    ):
        return
    if alcance == "todos" and _tiene_acceso_todos_pagos(usuario_actual):
        return
    if alcance == "sucursal" and (
        "ENCARGADO_SUCURSAL" in roles or _usuario_tiene_permiso(usuario_actual, "pagos:ver_sucursal")
    ):
        return
    raise HTTPException(status_code=403, detail="No tiene permisos para consultar pagos.")


def _roles(usuario_actual: dict[str, object]) -> set[str]:
    return {str(rol) for rol in usuario_actual.get("roles", [])}


def _usuario_tiene_permiso(usuario_actual: dict[str, object], accion: str) -> bool:
    return repo.usuario_tiene_permiso(int(usuario_actual["id"]), accion)


def _tiene_acceso_todos_pagos(usuario_actual: dict[str, object]) -> bool:
    roles = _roles(usuario_actual)
    return "ADMINISTRADOR" in roles or _usuario_tiene_permiso(usuario_actual, "pagos:ver_todos")


def _sucursal_id_encargado(usuario_actual: dict[str, object]) -> int:
    sucursal_id = repo.obtener_sucursal_id_por_usuario_empleado(int(usuario_actual["id"]))
    if sucursal_id is None:
        raise HTTPException(
            status_code=403,
            detail="No tiene una sucursal asignada para consultar pagos.",
        )
    return sucursal_id


def _checkout_response(orden: dict) -> CheckoutStripeResponse:
    return CheckoutStripeResponse(
        orden_id=int(orden["id"]),
        venta_id=int(orden["venta_id"]),
        estado=str(orden["estado"]),
        checkout_url=str(orden["checkout_url"]),
    )


def _orden_response(orden: dict) -> OrdenPagoResponse:
    return OrdenPagoResponse(
        orden_id=int(orden["id"]),
        venta_id=int(orden["venta_id"]),
        cliente_id=int(orden["cliente_id"]) if orden.get("cliente_id") is not None else None,
        monto_total=orden["monto_total"],
        moneda=str(orden["moneda"]),
        metodo=str(orden["metodo"]),
        estado=str(orden["estado"]),
        proveedor=str(orden["proveedor"]),
        checkout_url=orden.get("checkout_url"),
        proveedor_session_id=orden.get("proveedor_session_id"),
        fecha_pago=orden["fecha_pago"].isoformat() if orden.get("fecha_pago") else None,
    )


def _historial_item_response(pago: dict) -> PagoHistorialItemResponse:
    return PagoHistorialItemResponse(
        orden_id=int(pago["orden_id"]),
        venta_id=int(pago["venta_id"]),
        venta_codigo=None if pago.get("venta_codigo") is None else str(pago["venta_codigo"]),
        cliente_id=int(pago["cliente_id"]) if pago.get("cliente_id") is not None else None,
        cliente_nombre=_limpiar_texto(pago.get("cliente_nombre")),
        cliente_correo=_limpiar_texto(pago.get("cliente_correo")),
        sucursal_id=int(pago["sucursal_id"]) if pago.get("sucursal_id") is not None else None,
        sucursal_nombre=_limpiar_texto(pago.get("sucursal_nombre")),
        monto_total=pago["monto_total"],
        moneda=str(pago["moneda"]),
        metodo=str(pago["metodo"]),
        estado=str(pago["estado"]),
        proveedor=str(pago["proveedor"]),
        fecha_creacion=pago["fecha_creacion"].isoformat() if pago.get("fecha_creacion") else "",
        fecha_pago=pago["fecha_pago"].isoformat() if pago.get("fecha_pago") else None,
    )


def _historial_detalle_response(pago: dict) -> PagoHistorialDetalleResponse:
    item = _historial_item_response(pago)
    return PagoHistorialDetalleResponse(
        **item.model_dump(),
        proveedor_session_id=_limpiar_texto(pago.get("proveedor_session_id")),
        proveedor_payment_intent_id=_limpiar_texto(pago.get("proveedor_payment_intent_id")),
        checkout_url=_limpiar_texto(pago.get("checkout_url")),
        productos=[
            PagoProductoDetalleResponse(
                producto=str(producto["producto"]),
                categoria=_limpiar_texto(producto.get("categoria")),
                talla=_limpiar_texto(producto.get("talla")),
                color=_limpiar_texto(producto.get("color")),
                cantidad=int(producto["cantidad"]),
                precio_unitario=producto["precio_unitario"],
                subtotal=producto["subtotal"],
            )
            for producto in pago.get("productos", [])
        ],
    )


def _limpiar_texto(valor: object) -> str | None:
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None
