import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from app.core.config import AI_REPORTS_PROVIDER
from app.modules.inteligencia.repositories.reporte_repository import (
    actualizar_estado_reporte_programado,
    consultar_reporte,
    crear_reporte_programado,
    eliminar_reporte_programado,
    listar_reportes_programados,
    listar_sucursales,
    marcar_ejecucion_reporte_programado,
)
from app.modules.inteligencia.services.reporte_vertex_service import interpretar_con_vertex
from app.modules.inteligencia.schemas.reportes.reporte_request import (
    CrearReporteProgramadoRequest,
    ReporteRequest,
)

TITULOS = {
    "VENTAS": "Ventas presenciales",
    "PRODUCTOS_MAS_VENDIDOS": "Productos más vendidos",
    "INVENTARIO": "Inventario por sucursal",
    "RESERVAS": "Reservas",
    "MOVIMIENTOS": "Movimientos de inventario",
    "TRANSFERENCIAS": "Transferencias de stock",
    "PAGOS": "Historial de pagos",
    "DELIVERIES": "Pedidos con delivery",
    "USUARIOS": "Usuarios registrados",
}
MONETARIOS = {"subtotal", "descuento", "total", "importe"}


def catalogo_reportes() -> dict[str, object]:
    return {"tipos": [{"id": key, "nombre": title} for key, title in TITULOS.items()], "sucursales": listar_sucursales()}


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def _interpretar_por_reglas(texto: str) -> dict[str, object]:
    normal = _normalizar(texto)
    hoy = datetime.now(ZoneInfo("America/La_Paz")).date()
    inicio, fin = hoy.replace(day=1), hoy
    if "semana pasada" in normal:
        fin = hoy - timedelta(days=hoy.weekday() + 1)
        inicio = fin - timedelta(days=6)
    elif "esta semana" in normal:
        inicio = hoy - timedelta(days=hoy.weekday())
    elif "este ano" in normal:
        inicio = hoy.replace(month=1, day=1)
    elif "mes pasado" in normal:
        fin = hoy.replace(day=1) - timedelta(days=1)
        inicio = fin.replace(day=1)
    elif "principio de mes" in normal or "inicio de mes" in normal or "comienzo de mes" in normal or "este mes" in normal:
        inicio = hoy.replace(day=1)
    elif "hoy" in normal:
        inicio = fin = hoy
    fechas = re.findall(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", normal)
    if len(fechas) == 2:
        try:
            inicio, fin = (date(int(a[2]), int(a[1]), int(a[0])) for a in fechas)
        except ValueError:
            return {"interpretado": False, "advertencias": ["Las fechas dictadas no son válidas."], "filtros": None}
    meses = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
    rango_texto = re.search(r"\bdel?\s+(\d{1,2})\s+al\s+(\d{1,2})\s+de\s+(\w+)(?:\s+de\s+(\d{4}))?", normal)
    if rango_texto and rango_texto.group(3) in meses:
        try:
            ano = int(rango_texto.group(4) or hoy.year)
            mes = meses[rango_texto.group(3)]
            inicio = date(ano, mes, int(rango_texto.group(1)))
            fin = date(ano, mes, int(rango_texto.group(2)))
        except ValueError:
            return {"interpretado": False, "advertencias": ["El rango dictado no es válido."], "filtros": None}
    palabras = [
        ("PRODUCTOS_MAS_VENDIDOS", ("mas vendido", "mejor vendido", "top producto")),
        ("VENTAS", ("venta", "ventas", "ingreso", "ingresos")),
        ("INVENTARIO", ("inventario", "inventarios", "bajo stock", "existencia", "existencias")),
        ("RESERVAS", ("reserva", "reservas")),
        ("PAGOS", ("pago", "pagos", "stripe", "tarjeta")),
        ("DELIVERIES", ("delivery", "deliveries", "envio", "envios", "entrega", "domicilio")),
        ("USUARIOS", ("usuario", "usuarios", "cuenta", "cuentas", "cliente", "clientes", "cliente registrado", "clientes registrados")),
        ("MOVIMIENTOS", ("movimiento", "movimientos", "entrada", "entradas", "salida", "salidas", "ajuste", "ajustes")),
        ("TRANSFERENCIAS", ("transferencia", "transferencias", "traslado", "traslados")),
    ]
    tipo = next((key for key, opciones in palabras if any(re.search(r"\b" + re.escape(p) + r"\b", normal) for p in opciones)), None)
    if not tipo:
        return {"interpretado": False, "advertencias": ["No se reconoció un tipo de reporte. Prueba con ventas, inventario, reservas, movimientos o transferencias."], "filtros": None}
    tiene_fecha_explicita = bool(
        fechas
        or rango_texto
        or any(p in normal for p in ("hoy", "esta semana", "semana pasada", "este mes", "mes pasado", "este ano", "este año"))
    )
    if tipo == "USUARIOS" and not tiene_fecha_explicita:
        inicio = date(2020, 1, 1)
        fin = hoy
    sucursal_id = None
    sucursales = listar_sucursales()
    for sucursal in sucursales:
        nombre = _normalizar(str(sucursal["nombre"]))
        if nombre in normal:
            sucursal_id = sucursal["id"]
            break
    if "sucursal" in normal and sucursal_id is None and "todas" not in normal:
        return {"interpretado": False, "advertencias": ["No se reconoció la sucursal. Selecciónala en los filtros."], "filtros": None}
    estado = None
    if "pendiente" in normal:
        estado = "PENDIENTE" if tipo in {"PAGOS", "DELIVERIES"} else "PENDIENTE_PAGO" if tipo == "VENTAS" else "PENDIENTE"
    elif "pagado" in normal or "pagadas" in normal or "pagados" in normal:
        estado = "PAGADO" if tipo == "PAGOS" else "COMPLETADA"
    elif "rechaz" in normal:
        estado = "RECHAZADO" if tipo == "PAGOS" else "RECHAZADA"
    elif "cancel" in normal or "anulad" in normal:
        estado = "CANCELADO" if tipo in {"PAGOS", "DELIVERIES"} else "ANULADA"
    elif "entregado" in normal or "entregados" in normal:
        estado = "ENTREGADO"
    elif "camino" in normal:
        estado = "EN_CAMINO"
    elif "preparacion" in normal or "preparación" in normal:
        estado = "EN_PREPARACION"
    tipo_entrega = "DELIVERY" if any(p in normal for p in ("delivery", "domicilio", "envio", "envio a domicilio")) else None
    metodo_pago = "TARJETA" if "tarjeta" in normal else None
    proveedor_pago = "STRIPE" if "stripe" in normal else None
    rol = None
    if "administrador" in normal or "administradores" in normal:
        rol = "ADMINISTRADOR"
    elif "encargado" in normal or "encargados" in normal:
        rol = "ENCARGADO_SUCURSAL"
    elif "cliente" in normal or "clientes" in normal:
        rol = "CLIENTE"
    activo = False if "inactivo" in normal or "inactivos" in normal else True if "activo" in normal or "activos" in normal else None
    try:
        filtros = ReporteRequest(
            tipo=tipo,
            fecha_desde=inicio,
            fecha_hasta=fin,
            sucursal_id=sucursal_id,
            solo_bajo_stock="bajo stock" in normal,
            estado=estado,
            metodo_pago=metodo_pago,
            proveedor_pago=proveedor_pago,
            tipo_entrega=tipo_entrega,
            rol=rol,
            activo=activo,
        )
    except ValueError:
        return {"interpretado": False, "advertencias": ["El rango de fechas no es válido o supera 366 días."], "filtros": None}
    return {"interpretado": True, "advertencias": [], "texto_normalizado": normal, "filtros": filtros.model_dump(mode="json"), "motor": "reglas"}


def interpretar(texto: str) -> dict[str, object]:
    hoy = datetime.now(ZoneInfo("America/La_Paz")).date()
    if AI_REPORTS_PROVIDER == "VERTEX":
        try:
            return interpretar_con_vertex(texto, hoy, listar_sucursales())
        except Exception as exc:
            resultado = _interpretar_por_reglas(texto)
            advertencias = list(resultado.get("advertencias") or [])
            advertencias.append(f"Vertex no respondió; se usó interpretación local. Detalle: {exc}")
            resultado["advertencias"] = advertencias
            resultado["motor"] = "reglas_fallback"
            return resultado
    return _interpretar_por_reglas(texto)


def _presentar(valor: object) -> object:
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, datetime):
        return valor.astimezone(ZoneInfo("America/La_Paz")).isoformat()
    return valor


def generar_reporte(request: ReporteRequest) -> dict[str, object]:
    sucursales = listar_sucursales()
    if request.sucursal_id is not None and not any(s["id"] == request.sucursal_id for s in sucursales):
        raise HTTPException(status_code=422, detail="La sucursal seleccionada no existe o está inactiva.")
    rows = consultar_reporte(request)
    if len(rows) == 5000:
        raise HTTPException(status_code=422, detail="El reporte alcanza el límite de 5000 filas. Reduce el período o selecciona una sucursal.")
    filas = [{key: _presentar(value) for key, value in row.items()} for row in rows]
    total = sum((Decimal(str(row.get("total", row.get("monto_total", 0)) or 0)) for row in rows), Decimal(0))
    unidades = sum(int(row.get("real", row.get("unidades", row.get("cantidad", 0))) or 0) for row in rows)
    bajo_stock = sum(1 for row in rows if row.get("estado") == "BAJO STOCK") if request.tipo == "INVENTARIO" else 0
    serie: dict[str, float] = defaultdict(float)
    if request.tipo in {"VENTAS", "RESERVAS", "MOVIMIENTOS", "TRANSFERENCIAS", "PAGOS", "DELIVERIES", "USUARIOS"}:
        for row in rows:
            fecha = row["fecha"].astimezone(ZoneInfo("America/La_Paz"))
            key = fecha.strftime("%Y-%m" if request.agrupacion == "MES" else "%Y-%m-%d")
            serie[key] += float(row.get("total", row.get("monto_total", 1)) or (0 if request.tipo in {"VENTAS", "RESERVAS", "PAGOS"} else 1))
    elif request.tipo == "PRODUCTOS_MAS_VENDIDOS":
        serie = {f"{row['producto']} · {row['sku']}": int(row["unidades"]) for row in rows[:10]}
    else:
        serie = {"Bajo stock": bajo_stock, "Stock OK": len(rows) - bajo_stock}
    return {
        "tipo": request.tipo,
        "titulo": TITULOS[request.tipo],
        "nota": "El inventario muestra el estado actual; no existe historial de snapshots para reconstruirlo por fechas." if request.tipo == "INVENTARIO" else "El valor nominal incluye reservas de todos los estados; no equivale a dinero cobrado." if request.tipo == "RESERVAS" else None,
        "filtros_efectivos": {**request.model_dump(mode="json"), "sucursal": next((str(s["nombre"]) for s in sucursales if s["id"] == request.sucursal_id), "Todas")},
        "generado_en": datetime.now(ZoneInfo("America/La_Paz")).isoformat(),
        "indicadores": ([{"label": "Ventas", "valor": len(rows)}, {"label": "Unidades vendidas", "valor": unidades}, {"label": "Total ventas (Bs)", "valor": float(total)}] if request.tipo == "VENTAS" else
                        [{"label": "Reservas", "valor": len(rows)}, {"label": "Unidades solicitadas", "valor": unidades}, {"label": "Valor nominal (Bs)", "valor": float(total)}] if request.tipo == "RESERVAS" else
                        [{"label": "Pagos", "valor": len(rows)}, {"label": "Monto pagado/registrado (Bs)", "valor": float(total)}] if request.tipo == "PAGOS" else
                        [{"label": "Deliveries", "valor": len(rows)}, {"label": "Costo delivery (Bs)", "valor": float(sum((Decimal(str(row.get("costo_delivery", 0) or 0)) for row in rows), Decimal(0)))}] if request.tipo == "DELIVERIES" else
                        [{"label": "Usuarios", "valor": len(rows)}, {"label": "Activos", "valor": sum(1 for row in rows if row.get("activo") is True)}, {"label": "Inactivos", "valor": sum(1 for row in rows if row.get("activo") is False)}] if request.tipo == "USUARIOS" else
                        [{"label": "Variantes", "valor": len(rows)}, {"label": "Stock real", "valor": unidades}, {"label": "Bajo stock", "valor": bajo_stock}] if request.tipo == "INVENTARIO" else
                        [{"label": "Registros", "valor": len(rows)}, {"label": "Unidades", "valor": unidades}] if request.tipo in {"PRODUCTOS_MAS_VENDIDOS", "TRANSFERENCIAS"} else
                        [{"label": "Movimientos", "valor": len(rows)}]),
        "serie_grafico": [{"label": key, "valor": value} for key, value in sorted(serie.items())],
        "columnas": [{"key": key, "label": key.replace("_", " ").title()} for key in filas[0]] if filas else [],
        "filas": filas,
        "total_filas": len(filas),
        "sin_datos": not filas,
    }


def _presentar_programado(item: dict[str, object]) -> dict[str, object]:
    return {
        **item,
        "creado_en": item["creado_en"].astimezone(ZoneInfo("America/La_Paz")).isoformat() if item.get("creado_en") else None,
        "ultima_ejecucion": item["ultima_ejecucion"].astimezone(ZoneInfo("America/La_Paz")).isoformat() if item.get("ultima_ejecucion") else None,
        "proxima_ejecucion": item["proxima_ejecucion"].astimezone(ZoneInfo("America/La_Paz")).isoformat() if item.get("proxima_ejecucion") else None,
    }


def listar_programados_service() -> list[dict[str, object]]:
    return [_presentar_programado(item) for item in listar_reportes_programados()]


def crear_programado_service(request: CrearReporteProgramadoRequest, usuario_actual: dict[str, object]) -> dict[str, object]:
    usuario_id = int(usuario_actual["id"]) if "id" in usuario_actual else None
    item = crear_reporte_programado(request.model_dump(), usuario_id)
    return _presentar_programado(item)


def actualizar_estado_programado_service(programado_id: int, activo: bool) -> dict[str, object]:
    item = actualizar_estado_reporte_programado(programado_id, activo)
    if not item:
        raise HTTPException(status_code=404, detail="Programación de reporte no encontrada.")
    return _presentar_programado(item)


def eliminar_programado_service(programado_id: int) -> dict[str, str]:
    ok = eliminar_reporte_programado(programado_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Programación de reporte no encontrada.")
    return {"status": "ok", "mensaje": "Programación eliminada exitosamente."}


def ejecutar_programado_service(programado_id: int) -> dict[str, object]:
    item = marcar_ejecucion_reporte_programado(programado_id)
    if not item:
        raise HTTPException(status_code=404, detail="Programación de reporte no encontrada.")
    hoy = datetime.now(ZoneInfo("America/La_Paz")).date()
    desde = hoy - timedelta(days=30)
    rep_req = ReporteRequest(
        tipo=item["tipo"],
        fecha_desde=desde,
        fecha_hasta=hoy,
        sucursal_id=item.get("sucursal_id"),
        solo_bajo_stock=item.get("solo_bajo_stock", False),
    )
    resultado = generar_reporte(rep_req)
    return {
        "programado": _presentar_programado(item),
        "reporte": resultado,
        "mensaje": f"Reporte '{item['titulo']}' ejecutado exitosamente para {item['destinatario_email']} ({item['formato']}).",
    }
