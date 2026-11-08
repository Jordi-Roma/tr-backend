import os
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException, Request, status

from app.core.contexto_empresa import exigir_empresa_id
from app.modules.ventas_inventario.repositories import pago_repository as repo
from app.modules.ventas_inventario.schemas.pago.pago_request import (
    CrearCheckoutQrRequest,
    CrearCheckoutStripeRequest,
)
from app.modules.ventas_inventario.schemas.pago.pago_response import (
    CheckoutQrResponse,
    CheckoutStripeResponse,
    OrdenPagoResponse,
    PagoHistorialDetalleResponse,
    PagoHistorialItemResponse,
    PagoProductoDetalleResponse,
)
from app.modules.ventas_inventario.services.delivery_service import preparar_delivery_para_checkout


def crear_checkout_stripe_service(usuario_actual: dict[str, object], request: CrearCheckoutStripeRequest) -> CheckoutStripeResponse:
    from .pagos_empresa_service import crear_checkout
    return CheckoutStripeResponse(**crear_checkout(usuario_actual,request,'STRIPE'))


def crear_checkout_qr_service(
    usuario_actual: dict[str, object],
    request: CrearCheckoutQrRequest,
) -> CheckoutQrResponse:
    from .pagos_empresa_service import crear_checkout
    return CheckoutQrResponse(**crear_checkout(usuario_actual,request,'QR_BCP'))


def confirmar_pago_qr_service(usuario_actual: dict[str, object], orden_id: int) -> OrdenPagoResponse:
    from .pagos_empresa_service import confirmar_simulacion
    return _orden_response(confirmar_simulacion(usuario_actual,orden_id,True,'QR_BCP'))


def obtener_orden_service(usuario_actual: dict[str, object], orden_id: int) -> OrdenPagoResponse:
    orden = repo.obtener_orden_pago(orden_id, exigir_empresa_id(usuario_actual))
    if orden is None:
        raise HTTPException(status_code=404, detail="Orden de pago no encontrada.")
    _validar_acceso_orden(usuario_actual, orden)
    return _orden_response(orden)


def listar_mis_pagos_service(
    usuario_actual: dict[str, object],
    estado: str | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    limite: int | None = None,
) -> list[PagoHistorialItemResponse]:
    empresa_id = exigir_empresa_id(usuario_actual)
    _validar_permiso_historial(usuario_actual, "propios")
    cliente_id = _cliente_id_usuario(usuario_actual)
    pagos = repo.listar_historial_pagos(
        empresa_id=empresa_id,
        cliente_id=cliente_id,
        estado=estado,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        limite=limite,
    )
    return [_historial_item_response(pago) for pago in pagos]


def obtener_mi_pago_service(
    usuario_actual: dict[str, object],
    orden_id: int,
) -> PagoHistorialDetalleResponse:
    empresa_id = exigir_empresa_id(usuario_actual)
    _validar_permiso_historial(usuario_actual, "propios")
    cliente_id = _cliente_id_usuario(usuario_actual)
    pago = repo.obtener_historial_pago_detalle(orden_id, empresa_id)
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
    empresa_id = exigir_empresa_id(usuario_actual)
    roles = _roles(usuario_actual)
    if _tiene_acceso_todos_pagos(usuario_actual):
        pagos = repo.listar_historial_pagos(
            empresa_id=empresa_id,
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
            empresa_id=empresa_id,
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
    pago = repo.obtener_historial_pago_detalle(orden_id, exigir_empresa_id(usuario_actual))
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
    import stripe
    from .pagos_empresa_service import usa_stripe_compartido
    from ..router.pagos_empresa_router import procesar_evento_stripe

    secret = os.getenv('STRIPE_WEBHOOK_SECRET','')
    if not secret:
        raise HTTPException(503,'Configure la firma del webhook Stripe de pruebas.')
    try:
        event = stripe.Webhook.construct_event(await request.body(),request.headers.get('stripe-signature',''),secret)
    except Exception:
        raise HTTPException(400,'Firma Stripe inválida.')
    if event.get('livemode') is not False:
        raise HTTPException(403,'Sólo se admite Stripe de prueba.')
    tipo = event.get('type')
    obj = event.get('data', {}).get('object', {})
    from app.modules.administracion.services.suscripcion_stripe_service import procesar_evento
    suscripcion = procesar_evento(tipo, obj)
    if suscripcion is not None:
        return suscripcion
    meta = obj.get('metadata') or {}
    if tipo in ('refund.created','refund.updated','refund.failed'):
        if 'reembolso_pago_id' in meta and 'empresa_id' in meta:
            try:
                empresa = int(meta['empresa_id'])
            except (ValueError, TypeError):
                raise HTTPException(409,'Empresa inválida en el reembolso Stripe.')
            if usa_stripe_compartido(empresa):
                return procesar_evento_stripe(empresa, event)
        if 'devolucion_id' in meta and 'empresa_id' in meta:
            from app.modules.autenticacion.repositories.perfil_repository import _transaccion
            with _transaccion() as cur:
                cur.execute('SELECT politica_snapshot FROM devolucion WHERE id=%s AND empresa_id=%s',(meta['devolucion_id'],meta['empresa_id']))
                nueva=cur.fetchone()
            if nueva and nueva['politica_snapshot'] is not None:
                empresa = int(meta['empresa_id'])
                if usa_stripe_compartido(empresa):
                    return procesar_evento_stripe(empresa, event)
                return {'status':'ignorado'}
            from .devolucion_service import procesar_evento_refund_stripe
            try:
                procesar_evento_refund_stripe(str(obj['id']),str(obj.get('status') or 'pending'),
                    str(obj.get('failure_reason') or ''),int(meta['devolucion_id']),int(meta['empresa_id']))
            except (ValueError,KeyError,TypeError):
                raise HTTPException(409,'Metadatos de devolución inválidos.')
        return {'status':'recibido'}
    if tipo not in ('checkout.session.completed','checkout.session.expired',
                    'checkout.session.async_payment_succeeded','checkout.session.async_payment_failed'):
        return {'status':'ignorado'}
    orden=repo.obtener_orden_por_session(obj.get('id',''))
    if not orden:
        return {'status':'ignorado'}
    if orden.get('modo_pago') == 'PRUEBA':
        if orden.get('proveedor') == 'STRIPE' and usa_stripe_compartido(orden['empresa_id']):
            return procesar_evento_stripe(orden['empresa_id'], event)
        return {'status':'ignorado'}
    if orden.get('modo_pago')!='LEGADO' or orden.get('concepto') not in ('RESERVA_ANTICIPO','RESERVA_SALDO'):
        return {'status':'ignorado'}
    if (str(meta.get('empresa_id'))!=str(orden['empresa_id']) or str(meta.get('orden_id'))!=str(orden['id'])
        or obj.get('amount_total')!=int(Decimal(orden['monto_total'])*100) or str(obj.get('currency','')).upper()!=orden['moneda']):
        raise HTTPException(409,'La confirmación no corresponde a la reserva, empresa, moneda o importe.')
    if event.get('type')=='checkout.session.completed' and obj.get('payment_status')=='paid':
        repo.marcar_orden_pagada(orden['id'],empresa_id=orden['empresa_id'])
    elif event.get('type')=='checkout.session.expired':
        repo.marcar_orden_no_pagada(orden['id'],'EXPIRADO','CANCELADA',orden['empresa_id'])
    return {'status':'ok'}


def confirmar_pago_prueba_service(usuario_actual: dict[str, object], orden_id: int, aprobar: bool) -> OrdenPagoResponse:
    from .pagos_empresa_service import confirmar_simulacion
    return _orden_response(confirmar_simulacion(usuario_actual,orden_id,aprobar,'STRIPE'))


def _crear_session_stripe(orden: dict) -> dict:
    secret_key = os.getenv("STRIPE_SECRET_KEY")
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:4200")
    if not secret_key:
        raise HTTPException(status_code=503, detail="STRIPE_SECRET_KEY no esta configurada en el backend.")
    if not (secret_key.startswith("sk_test_") or secret_key == "MODO_PRUEBA"):
        raise HTTPException(status_code=403, detail="Solo se permite Stripe en modo de prueba.")

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
            metadata={"orden_id": str(orden["id"]), "venta_id": str(orden["venta_id"]), "empresa_id": str(orden["empresa_id"])},
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
    if int(orden["empresa_id"]) != exigir_empresa_id(usuario_actual):
        raise HTTPException(status_code=404, detail="Orden de pago no encontrada.")
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
    from .pagos_empresa_service import habilitado_pruebas, simulacion_reserva_legada
    return OrdenPagoResponse(
        modo_pago=orden.get('modo_pago','LEGADO'),
        confirmacion_prueba=habilitado_pruebas() and ((orden.get('modo_pago')=='PRUEBA' and str(orden.get('proveedor_session_id','')).startswith(('cs_simulada_','qr_prueba_'))) or simulacion_reserva_legada(orden)),
        pago_recibido=orden.get('pago_recibido',False),
        motivo_incidencia=orden.get('motivo_incidencia'),
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
                tipo_compra=producto.get('tipo_compra','UNIDAD'),
                paquete_origen_id=producto.get('paquete_origen_id'),
                descuento_mayorista=producto.get('descuento_mayorista'),
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
