import math
import os
from decimal import Decimal, ROUND_HALF_UP

import requests
from fastapi import HTTPException

from app.modules.ventas_inventario.repositories import delivery_repository as repo
from app.modules.ventas_inventario.schemas.delivery.delivery_request import (
    DeliveryCotizarRequest,
    DeliveryEstadoRequest,
    DeliveryGeocodificarResponse,
    DeliverySolicitarRequest,
)
from app.modules.ventas_inventario.schemas.delivery.delivery_response import (
    DeliveryCotizacionResponse,
    DeliveryDetalleResponse,
    DeliveryEstadoResponse,
    DeliveryItemResponse,
    DeliverySucursalResponse,
)

ESTADOS = {"PENDIENTE", "EN_PREPARACION", "EN_CAMINO", "ENTREGADO", "CANCELADO"}
TRANSICIONES = {
    "PENDIENTE": {"EN_PREPARACION", "CANCELADO"},
    "EN_PREPARACION": {"EN_CAMINO", "CANCELADO"},
    "EN_CAMINO": {"ENTREGADO"},
    "ENTREGADO": set(),
    "CANCELADO": set(),
}


def cotizar_delivery_service(request: DeliveryCotizarRequest) -> DeliveryCotizacionResponse:
    sucursal = repo.obtener_sucursal(request.sucursal_id)
    if sucursal is None:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada.")
    if sucursal.get("latitud") is None or sucursal.get("longitud") is None:
        raise HTTPException(status_code=400, detail="La sucursal no tiene ubicacion configurada.")

    distancia_km, tiempo_min = _calcular_ruta(
        Decimal(str(sucursal["latitud"])),
        Decimal(str(sucursal["longitud"])),
        request.latitud_entrega,
        request.longitud_entrega,
    )
    costo = _calcular_costo(distancia_km)
    max_km = _max_km()
    disponible = distancia_km <= max_km
    return DeliveryCotizacionResponse(
        sucursal_id=request.sucursal_id,
        distancia_km=_decimal(distancia_km),
        tiempo_estimado_min=tiempo_min,
        costo_delivery=costo if disponible else Decimal("0.00"),
        disponible=disponible,
        mensaje=None if disponible else "La direccion esta fuera del rango de delivery disponible.",
    )


def geocodificar_delivery_service(direccion: str) -> DeliveryGeocodificarResponse:
    direccion = direccion.strip()
    if len(direccion) < 5:
        raise HTTPException(status_code=400, detail="Ingresa una direccion mas completa.")

    try:
        for consulta in _consultas_geocodificacion(direccion):
            response = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": consulta,
                    "format": "json",
                    "limit": 1,
                    "countrycodes": "bo",
                },
                headers={"User-Agent": "StyleAR/1.0"},
                timeout=8,
            )
            response.raise_for_status()
            data = response.json()
            if data:
                item = data[0]
                return DeliveryGeocodificarResponse(
                    direccion=str(item.get("display_name") or direccion),
                    latitud=Decimal(str(item["lat"])),
                    longitud=Decimal(str(item["lon"])),
                )
    except Exception as error:
        raise HTTPException(status_code=503, detail="No se pudo buscar la direccion en el mapa.") from error

    raise HTTPException(status_code=404, detail="No se encontro la direccion indicada.")


def _consultas_geocodificacion(direccion: str) -> list[str]:
    direccion_lower = direccion.lower()
    consultas = [direccion]
    if "santa cruz" not in direccion_lower:
        consultas.append(f"{direccion}, Santa Cruz de la Sierra")
    if "bolivia" not in direccion_lower:
        consultas.append(f"{direccion}, Santa Cruz de la Sierra, Bolivia")
    return list(dict.fromkeys(consultas))


def listar_sucursales_delivery_service() -> list[DeliverySucursalResponse]:
    # Se reutiliza cotizar/checkout con IDs de sucursal existentes; esta lista ligera sale del repositorio
    # mediante consultas de delivery cuando existan datos. Para el checkout web se usan los filtros de catalogo.
    raise HTTPException(status_code=501, detail="Usa el catalogo de sucursales disponible en la tienda.")


def crear_delivery_service(
    usuario_actual: dict[str, object],
    request: DeliverySolicitarRequest,
) -> DeliveryDetalleResponse:
    _validar_permiso(usuario_actual, "delivery:solicitar")
    cliente_id = _cliente_id_obligatorio(usuario_actual)
    cotizacion = cotizar_delivery_service(request)
    if not cotizacion.disponible:
        raise HTTPException(status_code=400, detail=cotizacion.mensaje)
    try:
        delivery = repo.crear_delivery_independiente(
            {
                **request.model_dump(),
                "cliente_id": cliente_id,
                "distancia_km": cotizacion.distancia_km,
                "tiempo_estimado_min": cotizacion.tiempo_estimado_min,
                "costo_delivery": cotizacion.costo_delivery,
            }
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    detalle = repo.obtener_delivery(int(delivery["id"]))
    if detalle is None:
        raise HTTPException(status_code=404, detail="Delivery no encontrado.")
    return _detalle_response(detalle)


def listar_mis_deliveries_service(
    usuario_actual: dict[str, object],
    estado: str | None = None,
) -> list[DeliveryItemResponse]:
    _validar_permiso(usuario_actual, "delivery:ver_propios")
    cliente_id = _cliente_id_obligatorio(usuario_actual)
    return [_item_response(item) for item in repo.listar_deliveries(cliente_id=cliente_id, estado=estado)]


def obtener_mi_delivery_service(usuario_actual: dict[str, object], delivery_id: int) -> DeliveryDetalleResponse:
    _validar_permiso(usuario_actual, "delivery:ver_propios")
    cliente_id = _cliente_id_obligatorio(usuario_actual)
    delivery = repo.obtener_delivery(delivery_id)
    if delivery is None or int(delivery["cliente_id"]) != cliente_id:
        raise HTTPException(status_code=404, detail="Delivery no encontrado.")
    return _detalle_response(delivery)


def listar_deliveries_service(
    usuario_actual: dict[str, object],
    estado: str | None = None,
    cliente: str | None = None,
    sucursal_id: int | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
) -> list[DeliveryItemResponse]:
    if _tiene_permiso(usuario_actual, "delivery:ver_todos") or "ADMINISTRADOR" in _roles(usuario_actual):
        rows = repo.listar_deliveries(
            estado=estado,
            cliente=cliente,
            sucursal_id=sucursal_id,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
        )
        return [_item_response(item) for item in rows]

    if _tiene_permiso(usuario_actual, "delivery:ver_sucursal") or _roles(usuario_actual).intersection({"ENCARGADO_SUCURSAL", "CAJERO"}):
        sucursal_permitida = _sucursal_id_obligatoria(usuario_actual)
        if sucursal_id is not None and sucursal_id != sucursal_permitida:
            raise HTTPException(status_code=403, detail="Solo puede consultar deliveries de su sucursal.")
        rows = repo.listar_deliveries(
            estado=estado,
            cliente=cliente,
            sucursal_id=sucursal_permitida,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
        )
        return [_item_response(item) for item in rows]

    raise HTTPException(status_code=403, detail="No tiene permisos para consultar deliveries.")


def obtener_delivery_service(usuario_actual: dict[str, object], delivery_id: int) -> DeliveryDetalleResponse:
    delivery = repo.obtener_delivery(delivery_id)
    if delivery is None:
        raise HTTPException(status_code=404, detail="Delivery no encontrado.")
    _validar_acceso_staff(usuario_actual, delivery)
    return _detalle_response(delivery)


def actualizar_estado_delivery_service(
    usuario_actual: dict[str, object],
    delivery_id: int,
    request: DeliveryEstadoRequest,
) -> DeliveryEstadoResponse:
    estado = request.estado.strip().upper()
    if estado not in ESTADOS:
        raise HTTPException(status_code=400, detail="Estado de delivery no valido.")

    delivery = repo.obtener_delivery(delivery_id)
    if delivery is None:
        raise HTTPException(status_code=404, detail="Delivery no encontrado.")
    _validar_acceso_staff(usuario_actual, delivery)

    if estado == "CANCELADO":
        _validar_permiso(usuario_actual, "delivery:cancelar")
    else:
        _validar_permiso(usuario_actual, "delivery:gestionar_estado")

    estado_actual = str(delivery["estado"])
    if estado != estado_actual and estado not in TRANSICIONES.get(estado_actual, set()):
        raise HTTPException(status_code=400, detail=f"No se puede cambiar de {estado_actual} a {estado}.")

    try:
        actualizado = repo.actualizar_estado(delivery_id, estado, request.observacion)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return DeliveryEstadoResponse(mensaje="Estado de delivery actualizado.", delivery=_detalle_response(actualizado))


def preparar_delivery_para_checkout(request) -> dict | None:
    if request is None:
        return None
    cotizacion = cotizar_delivery_service(request)
    if not cotizacion.disponible:
        raise HTTPException(status_code=400, detail=cotizacion.mensaje)
    return {
        "sucursal_id": request.sucursal_id,
        "direccion_entrega": request.direccion_entrega,
        "referencia": request.referencia,
        "latitud_entrega": request.latitud_entrega,
        "longitud_entrega": request.longitud_entrega,
        "distancia_km": cotizacion.distancia_km,
        "tiempo_estimado_min": cotizacion.tiempo_estimado_min,
        "costo_delivery": cotizacion.costo_delivery,
    }


def _calcular_ruta(
    origen_lat: Decimal,
    origen_lng: Decimal,
    destino_lat: Decimal,
    destino_lng: Decimal,
) -> tuple[Decimal, int]:
    api_key = os.getenv("OPENROUTE_API_KEY", "").strip()
    if api_key:
        try:
            response = requests.post(
                "https://api.openrouteservice.org/v2/directions/driving-car",
                headers={"Authorization": api_key, "Content-Type": "application/json"},
                json={
                    "coordinates": [
                        [float(origen_lng), float(origen_lat)],
                        [float(destino_lng), float(destino_lat)],
                    ]
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            summary = data["features"][0]["properties"]["summary"]
            distancia = Decimal(str(summary["distance"])) / Decimal("1000")
            tiempo = max(1, int(round(float(summary["duration"]) / 60)))
            return _decimal(distancia), tiempo
        except Exception:
            pass

    distancia = _haversine_km(origen_lat, origen_lng, destino_lat, destino_lng)
    tiempo = max(1, int(math.ceil(float(distancia) / 25 * 60)))
    return _decimal(distancia), tiempo


def _haversine_km(lat1: Decimal, lon1: Decimal, lat2: Decimal, lon2: Decimal) -> Decimal:
    radio = 6371.0
    lat1_f, lon1_f, lat2_f, lon2_f = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
    dlat = lat2_f - lat1_f
    dlon = lon2_f - lon1_f
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_f) * math.cos(lat2_f) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return Decimal(str(radio * c))


def _calcular_costo(distancia_km: Decimal) -> Decimal:
    if distancia_km <= Decimal("3"):
        return Decimal("8.00")
    if distancia_km <= Decimal("6"):
        return Decimal("12.00")
    if distancia_km <= Decimal("10"):
        return Decimal("18.00")
    return Decimal("0.00")


def _max_km() -> Decimal:
    return Decimal(os.getenv("DELIVERY_MAX_KM", "10"))


def _decimal(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _roles(usuario_actual: dict[str, object]) -> set[str]:
    return {str(rol) for rol in usuario_actual.get("roles", [])}


def _tiene_permiso(usuario_actual: dict[str, object], accion: str) -> bool:
    return repo.usuario_tiene_permiso(int(usuario_actual["id"]), accion)


def _validar_permiso(usuario_actual: dict[str, object], accion: str) -> None:
    roles = _roles(usuario_actual)
    if accion == "delivery:solicitar" and "CLIENTE" in roles:
        return
    if accion == "delivery:ver_propios" and "CLIENTE" in roles:
        return
    if accion in {"delivery:ver_todos", "delivery:gestionar_estado", "delivery:cancelar"} and "ADMINISTRADOR" in roles:
        return
    if accion in {"delivery:ver_sucursal", "delivery:gestionar_estado", "delivery:cancelar"} and "ENCARGADO_SUCURSAL" in roles:
        return
    if accion in {"delivery:ver_sucursal", "delivery:gestionar_estado"} and "CAJERO" in roles:
        return
    if _tiene_permiso(usuario_actual, accion):
        return
    raise HTTPException(status_code=403, detail="No tiene permisos para delivery.")


def _cliente_id_obligatorio(usuario_actual: dict[str, object]) -> int:
    cliente_id = repo.obtener_cliente_id_por_usuario(int(usuario_actual["id"]))
    if cliente_id is None:
        raise HTTPException(status_code=403, detail="El usuario no tiene cliente asociado.")
    return cliente_id


def _sucursal_id_obligatoria(usuario_actual: dict[str, object]) -> int:
    sucursal_id = repo.obtener_sucursal_id_por_usuario_empleado(int(usuario_actual["id"]))
    if sucursal_id is None:
        raise HTTPException(status_code=403, detail="No tiene una sucursal asignada.")
    return sucursal_id


def _validar_acceso_staff(usuario_actual: dict[str, object], delivery: dict) -> None:
    if _tiene_permiso(usuario_actual, "delivery:ver_todos") or "ADMINISTRADOR" in _roles(usuario_actual):
        return
    if _tiene_permiso(usuario_actual, "delivery:ver_sucursal") or _roles(usuario_actual).intersection({"ENCARGADO_SUCURSAL", "CAJERO"}):
        if int(delivery["sucursal_id"]) != _sucursal_id_obligatoria(usuario_actual):
            raise HTTPException(status_code=404, detail="Delivery no encontrado.")
        return
    raise HTTPException(status_code=403, detail="No tiene permisos para consultar deliveries.")


def _item_response(delivery: dict) -> DeliveryItemResponse:
    return DeliveryItemResponse(
        id=int(delivery["id"]),
        venta_id=int(delivery["venta_id"]),
        venta_codigo=_texto(delivery.get("venta_codigo")),
        cliente_id=int(delivery["cliente_id"]) if delivery.get("cliente_id") is not None else None,
        cliente_nombre=_texto(delivery.get("cliente_nombre")),
        cliente_correo=_texto(delivery.get("cliente_correo")),
        sucursal_id=int(delivery["sucursal_id"]),
        sucursal_nombre=_texto(delivery.get("sucursal_nombre")),
        direccion_entrega=str(delivery["direccion_entrega"]),
        referencia=_texto(delivery.get("referencia")),
        distancia_km=delivery.get("distancia_km"),
        tiempo_estimado_min=int(delivery["tiempo_estimado_min"]) if delivery.get("tiempo_estimado_min") is not None else None,
        costo_delivery=delivery["costo_delivery"],
        estado=str(delivery["estado"]),
        total_venta=delivery.get("total_venta"),
        fecha_creacion=delivery["fecha_creacion"].isoformat() if delivery.get("fecha_creacion") else "",
        fecha_entrega=delivery["fecha_entrega"].isoformat() if delivery.get("fecha_entrega") else None,
    )


def _detalle_response(delivery: dict) -> DeliveryDetalleResponse:
    item = _item_response(delivery)
    return DeliveryDetalleResponse(
        **item.model_dump(),
        sucursal_direccion=_texto(delivery.get("sucursal_direccion")),
        sucursal_latitud=delivery.get("sucursal_latitud"),
        sucursal_longitud=delivery.get("sucursal_longitud"),
        latitud_entrega=delivery["latitud_entrega"],
        longitud_entrega=delivery["longitud_entrega"],
        observacion=_texto(delivery.get("observacion")),
    )


def _texto(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
