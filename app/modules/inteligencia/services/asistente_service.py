import os
import re
import unicodedata
from decimal import Decimal

from app.core.config import AI_ASSISTANT_PROVIDER
from app.modules.catalogo.repositories.catalogo_publico_repository import obtener_prenda_catalogo
from app.modules.inteligencia.repositories import recomendacion_repository
from app.modules.inteligencia.repositories.asistente_repository import (
    buscar_productos_para_asistente,
    listar_sucursales_para_asistente,
)
from app.modules.inteligencia.schemas.asistente.asistente_schemas import (
    AsistenteChatRequest,
    AsistenteChatResponse,
    AsistenteProductoResponse,
)
from app.modules.inteligencia.services.recomendacion_service import (
    recomendar_desde_producto,
    recomendar_para_cliente,
)
from app.modules.inteligencia.services.asistente_vertex_service import (
    interpretar_asistente_con_vertex,
    redactar_asistente_con_vertex,
)
from app.modules.reservas.repositories.reserva_repository import listar_reservas_cliente

STOPWORDS = {
    "hay", "tienes", "tienen", "tengo", "una", "uno", "unas", "unos", "para",
    "con", "sin", "del", "de", "la", "el", "los", "las", "que", "quiero",
    "busco", "mostrar", "muestrame", "muéstrame", "donde", "dónde", "esta",
    "está", "disponible", "disponibles", "stock", "talla", "color", "en",
    "por", "favor", "algo", "me", "recomienda", "recomiendame", "recomiéndame",
    "este", "producto", "productos", "prenda", "prendas", "ropa", "cosas",
    "podes", "podés", "puedes", "decirme", "si",
    "cuesta", "cuestan", "cueste", "cuesten", "vale", "valen", "precio",
    "precios", "menos", "menor", "hasta", "maximo", "máximo", "bs",
    "boliviano", "bolivianos",
}
PALABRAS_PERSONALES = {"mis reservas", "mi reserva", "mis favoritos", "mi favorito", "mis compras", "mis recomendaciones", "para mi", "para mí", "mi historial"}
PALABRAS_RESERVAS_PERSONALES = {"mis reservas", "mi reserva"}
PALABRAS_FAVORITOS_PERSONALES = {"mis favoritos", "mi favorito"}
PALABRAS_RECOMENDACIONES_PERSONALES = {"mis recomendaciones", "para mi", "para mí", "segun mis favoritos", "según mis favoritos"}
PALABRAS_AYUDA_PROCESO = {"como", "puedo", "hago", "hacer", "funciona", "funcionan", "proceso", "pasos", "explica", "explicame", "donde", "ver", "consultar", "usar", "uso", "sirve"}
PALABRAS_RESERVA = {"reserva", "reservar", "reservas", "reservarlo", "reservarla"}
PALABRAS_DELIVERY = {"delivery", "entrega", "envio", "enviar", "recibir", "domicilio", "direccion", "ubicacion", "cotizar", "distancia", "mapa"}
PALABRAS_PAGO = {"pago", "pagar", "pagos", "pague", "pagué", "pagado", "pagada", "pagadas", "pagados", "stripe", "tarjeta", "comprar", "compra", "checkout", "pasarela"}
PALABRAS_CARRITO = {"carrito", "agregar", "anadir", "añadir", "cantidad", "vaciar", "eliminar"}
PALABRAS_CUENTA = {"cuenta", "login", "iniciar", "sesion", "registrarme", "registro", "contrasena", "contraseña", "perfil"}
PALABRAS_FAVORITOS = {"favorito", "favoritos", "corazon", "corazón", "guardar"}
PALABRAS_HISTORIAL_PAGOS = {
    "historial",
    "mis pagos",
    "pagos realizados",
    "comprobantes",
    "recibos",
    "cosas que yo pague",
    "cosas que pague",
    "lo que pague",
    "que pague",
    "que yo pague",
    "prendas que pague",
    "compras que pague",
    "compras pagadas",
}
PALABRAS_VESTIDOR = {"vestidor", "probarme", "probar", "foto", "ia", "modelo", "avatar"}
PALABRAS_SUCURSAL = {"sucursal", "sucursales", "tienda", "tiendas", "atencion", "atención"}
PALABRAS_RECOMENDACION = {"recomienda", "recomiendame", "recomiéndame", "similar", "parecido", "combina", "frio", "frío", "invierno", "outfit"}
PALABRAS_SALUDO = {"hola", "buenas", "buenos", "hey"}
PALABRAS_AGRADECIMIENTO = {"gracias", "ok", "okay", "listo", "perfecto"}
PALABRAS_CAPACIDADES = {"ayuda", "ayudar", "ayudas", "puedes", "podes", "podés", "sirves", "haces", "hacer", "funcion", "función", "funciones"}
PALABRAS_PRODUCTO = {"prenda", "prendas", "ropa", "polera", "poleras", "camisa", "camisas", "pantalon", "pantalón", "pantalones", "jean", "jeans", "blusa", "blusas", "vestido", "vestidos", "chaqueta", "chaquetas", "abrigo", "abrigos", "oversize", "talla", "tallas", "color", "colores", "stock"}
TALLAS_CONOCIDAS = {"xs", "s", "m", "l", "xl", "xxl"}
COLORES_CONOCIDOS = {
    "rojo": "roj", "roja": "roj", "rojos": "roj", "rojas": "roj",
    "azul marino": "azul marino", "azul": "azul",
    "negro": "negr", "negra": "negr", "negros": "negr", "negras": "negr",
    "blanco": "blanc", "blanca": "blanc", "blancos": "blanc", "blancas": "blanc",
    "verde": "verde", "verdes": "verde",
    "amarillo": "amarill", "amarilla": "amarill", "amarillos": "amarill", "amarillas": "amarill",
    "gris": "gris", "grises": "gris", "beige": "beige",
    "marron": "marr", "marrón": "marr", "cafe": "caf", "café": "caf",
    "rosa": "ros", "rosado": "ros", "rosada": "ros",
    "morado": "morad", "morada": "morad",
}

TIPOS_AYUDA_PROCESO = {
    "ayuda_reservas",
    "ayuda_delivery",
    "ayuda_pagos",
    "ayuda_carrito",
    "ayuda_cuenta",
    "ayuda_favoritos",
    "ayuda_historial_pagos",
    "ayuda_vestidor",
}

RESPUESTAS_AYUDA_PROCESO = {
    "ayuda_reservas": "Para hacer una reserva, elige una prenda con stock, selecciona talla/color y sucursal, agrégala al carrito y usa “Confirmar reserva”. Si quieres reservar pagando por Stripe, usa “Reservar con Stripe”. Luego puedes revisar tus reservas desde “Mis reservas”.",
    "ayuda_delivery": "Para pedir delivery, agrega una prenda con stock al carrito, elige “Delivery”, selecciona una sucursal disponible, busca tu dirección o marca el punto en el mapa, cotiza el envío y paga con Stripe. Después puedes seguir el pedido desde “Mis deliveries”.",
    "ayuda_pagos": "Para pagar, primero revisa el carrito. Si eliges recojo en sucursal puedes reservar normal o usar “Reservar con Stripe”. Si eliges delivery, se usa “Pagar delivery con Stripe” después de cotizar el envío. Tus pagos quedan visibles en “Mis pagos”.",
    "ayuda_carrito": "En el carrito puedes revisar tus prendas, cambiar cantidades, eliminar productos o vaciar todo. Desde ahí eliges si será recojo en sucursal o delivery, y el sistema usa la sucursal con stock para continuar.",
    "ayuda_cuenta": "Para usar funciones personales como reservas, favoritos, pagos o deliveries necesitas iniciar sesión. Si no tienes cuenta, regístrate; si olvidaste tu contraseña, usa la recuperación desde la pantalla de ingreso.",
    "ayuda_favoritos": "Para guardar favoritos, toca el corazón de una prenda. Luego puedes volver a verlos desde tu cuenta y también sirven para mejorar tus recomendaciones.",
    "ayuda_historial_pagos": "Tus pagos se revisan desde “Mis pagos”. Ahí puedes ver compras o reservas pagadas con Stripe y consultar el detalle del pago.",
    "ayuda_vestidor": "El vestidor/IA sirve para probar o visualizar prendas antes de decidir. Entra desde la prenda o la sección correspondiente, sigue las indicaciones de imagen y usa el resultado como apoyo antes de agregar al carrito.",
}


def responder_chat_asistente(request: AsistenteChatRequest, usuario_actual: dict[str, object] | None) -> AsistenteChatResponse:
    mensaje = request.mensaje.strip()
    mensaje_normalizado = _normalizar(mensaje)
    contexto = request.contexto
    producto_id = contexto.producto_id if contexto else None
    sucursal_id = contexto.sucursal_id if contexto else None
    tipo, filtros, terminos = _interpretar_consulta_asistente(mensaje, mensaje_normalizado, producto_id, sucursal_id)

    if _requiere_login(mensaje_normalizado, tipo) and usuario_actual is None:
        return _respuesta_requiere_login()

    if tipo == "saludo":
        return AsistenteChatResponse(respuesta="¡Hola! Soy el asistente de StyleAR. Puedo ayudarte a buscar prendas por color, talla o categoría, consultar stock por sucursal, explicarte cómo reservar y mostrarte sucursales disponibles.", tipo=tipo)

    if tipo == "capacidades":
        return AsistenteChatResponse(respuesta="Puedo ayudarte a buscar prendas reales del catálogo, consultar stock por talla/color/sucursal, recomendar alternativas y explicarte procesos como reservas, delivery, pagos con Stripe, carrito, favoritos, cuenta, vestidor y dónde ver tus pagos o pedidos.", tipo=tipo)

    if tipo == "agradecimiento":
        return AsistenteChatResponse(respuesta="¡De nada! Si quieres, también puedo ayudarte a buscar una prenda, consultar stock o explicarte reservas, delivery, pagos, carrito y favoritos.", tipo=tipo)

    if tipo == "consulta_personal_reservas":
        return _respuesta_mis_reservas(usuario_actual)
    if tipo == "consulta_personal_favoritos":
        return _respuesta_mis_favoritos(usuario_actual)
    if tipo == "consulta_personal_recomendaciones":
        return _respuesta_mis_recomendaciones(usuario_actual)

    if tipo in TIPOS_AYUDA_PROCESO:
        return AsistenteChatResponse(respuesta=_respuesta_ayuda_proceso(tipo), tipo=tipo)

    if tipo == "sucursales":
        return AsistenteChatResponse(respuesta=_respuesta_sucursales(listar_sucursales_para_asistente()), tipo=tipo)

    if tipo in {"recomendacion", "recomendacion_contextual"} and producto_id is not None:
        recomendadas = _mapear_catalogo_a_productos(recomendar_desde_producto(producto_id, sucursal_id=sucursal_id))
        if recomendadas:
            return AsistenteChatResponse(respuesta="Encontré prendas reales parecidas a esta. Te muestro opciones disponibles con stock.", tipo="recomendacion_contextual", productos=recomendadas, filtros_detectados=_filtros_publicos(filtros))

    productos = buscar_productos_para_asistente(
        terminos=terminos,
        color_patrones=filtros["color_patrones"],
        talla_patrones=filtros["talla_patrones"],
        sucursal_patrones=filtros["sucursal_patrones"],
        precio_max=filtros["precio_max"],
        producto_id=producto_id,
        sucursal_id=sucursal_id,
    )

    alternativas: list[dict[str, object]] = []
    if not productos and _hay_filtros_estrictos(filtros):
        alternativas = _buscar_alternativas(terminos, filtros, producto_id, sucursal_id)

    respuesta_base = _respuesta_productos(productos, tipo, alternativas, filtros)
    respuesta = _redactar_con_ia(mensaje, productos, respuesta_base, tipo, alternativas)

    return AsistenteChatResponse(
        respuesta=respuesta,
        tipo=tipo,
        productos=[_mapear_producto(row) for row in productos],
        alternativas=[_mapear_producto(row) for row in alternativas],
        filtros_detectados=_filtros_publicos(filtros),
        requiere_login=False,
    )


def _interpretar_consulta_asistente(
    mensaje: str,
    mensaje_normalizado: str,
    producto_id: int | None,
    sucursal_id: int | None,
) -> tuple[str, dict[str, object], list[str]]:
    tipo_reglas = _clasificar_intencion(mensaje_normalizado)
    if tipo_reglas in {
        "saludo",
        "capacidades",
        "agradecimiento",
        "consulta_personal_reservas",
        "consulta_personal_favoritos",
        "consulta_personal_recomendaciones",
        *TIPOS_AYUDA_PROCESO,
        "sucursales",
    }:
        return tipo_reglas, _detectar_filtros(mensaje_normalizado), _extraer_terminos(mensaje_normalizado)

    if AI_ASSISTANT_PROVIDER in {"VERTEX", "GEMINI"}:
        try:
            interpretacion = interpretar_asistente_con_vertex(
                mensaje,
                producto_id=producto_id,
                sucursal_id=sucursal_id,
                sucursales=listar_sucursales_para_asistente(),
            )
            tipo = str(interpretacion["tipo"])
            filtros = {
                "color_patrones": list(interpretacion["color_patrones"]),
                "talla_patrones": list(interpretacion["talla_patrones"]),
                "sucursal_patrones": list(interpretacion["sucursal_patrones"]),
                "precio_max": interpretacion["precio_max"],
            }
            terminos = list(interpretacion["terminos"])
            if not terminos and tipo in {"catalogo", "disponibilidad", "recomendacion"}:
                terminos = _extraer_terminos(mensaje_normalizado)
            return tipo, filtros, terminos
        except Exception:
            pass

    filtros = _detectar_filtros(mensaje_normalizado)
    terminos = _extraer_terminos(mensaje_normalizado)
    return tipo_reglas, filtros, terminos


def _clasificar_intencion(mensaje: str) -> str:
    palabras = set(mensaje.split())
    if any(frase in mensaje for frase in PALABRAS_RESERVAS_PERSONALES):
        return "consulta_personal_reservas"
    if any(frase in mensaje for frase in PALABRAS_RECOMENDACIONES_PERSONALES):
        return "consulta_personal_recomendaciones"
    if any(frase in mensaje for frase in PALABRAS_FAVORITOS_PERSONALES):
        return "consulta_personal_favoritos"
    if len(palabras) <= 4 and bool(palabras & PALABRAS_AGRADECIMIENTO):
        return "agradecimiento"
    if _es_pregunta_capacidades(mensaje, palabras):
        return "capacidades"
    if len(palabras) <= 4 and bool(palabras & PALABRAS_SALUDO):
        return "saludo"
    tipo_ayuda = _detectar_ayuda_proceso(mensaje, palabras)
    if tipo_ayuda:
        return tipo_ayuda
    if palabras & PALABRAS_SUCURSAL and not (palabras & {"polera", "poleras", "prenda", "prendas", "stock"}):
        return "sucursales"
    if palabras & PALABRAS_RECOMENDACION:
        if "esta prenda" in mensaje or "este producto" in mensaje or "parecido" in palabras or "similar" in palabras:
            return "recomendacion_contextual"
        return "recomendacion"
    if "stock" in palabras or "disponible" in palabras or "disponibles" in palabras:
        return "disponibilidad"
    return "catalogo"


def _requiere_login(mensaje: str, tipo: str | None = None) -> bool:
    return tipo in {"consulta_personal_reservas", "consulta_personal_favoritos", "consulta_personal_recomendaciones"} or any(frase in mensaje for frase in PALABRAS_PERSONALES)


def _es_pregunta_capacidades(mensaje: str, palabras: set[str]) -> bool:
    if palabras & PALABRAS_PRODUCTO:
        return False
    frases = ("que puedes hacer", "qué puedes hacer", "que podes hacer", "qué podés hacer", "en que me puedes ayudar", "en qué me puedes ayudar", "en que me podes ayudar", "en qué me podés ayudar", "para que sirves", "para qué sirves")
    return any(frase in mensaje for frase in frases) or bool(palabras & PALABRAS_CAPACIDADES)


def _detectar_ayuda_proceso(mensaje: str, palabras: set[str]) -> str | None:
    pide_ayuda = bool(palabras & PALABRAS_AYUDA_PROCESO) or "como " in mensaje or "que hago" in mensaje or "donde veo" in mensaje
    if not pide_ayuda and not any(frase in mensaje for frase in PALABRAS_HISTORIAL_PAGOS):
        return None
    if palabras & PALABRAS_DELIVERY or any(palabra in mensaje for palabra in PALABRAS_DELIVERY):
        return "ayuda_delivery"
    if palabras & PALABRAS_HISTORIAL_PAGOS or any(frase in mensaje for frase in PALABRAS_HISTORIAL_PAGOS):
        return "ayuda_historial_pagos"
    if palabras & PALABRAS_PAGO or any(palabra in mensaje for palabra in PALABRAS_PAGO):
        return "ayuda_pagos"
    if palabras & PALABRAS_CARRITO or any(palabra in mensaje for palabra in PALABRAS_CARRITO):
        return "ayuda_carrito"
    if palabras & PALABRAS_CUENTA or any(palabra in mensaje for palabra in PALABRAS_CUENTA):
        return "ayuda_cuenta"
    if palabras & PALABRAS_FAVORITOS or any(palabra in mensaje for palabra in PALABRAS_FAVORITOS):
        return "ayuda_favoritos"
    if palabras & PALABRAS_VESTIDOR or any(palabra in mensaje for palabra in PALABRAS_VESTIDOR):
        return "ayuda_vestidor"
    if palabras & PALABRAS_RESERVA or any(palabra in mensaje for palabra in PALABRAS_RESERVA):
        return "ayuda_reservas"
    return None


def _detectar_filtros(mensaje: str) -> dict[str, object]:
    return {"color_patrones": _extraer_colores_mencionados(mensaje), "talla_patrones": _extraer_tallas_mencionadas(mensaje), "sucursal_patrones": _extraer_sucursales_mencionadas(mensaje), "precio_max": _extraer_precio_maximo(mensaje)}


def _extraer_terminos(mensaje: str) -> list[str]:
    tokens = re.findall(r"[a-záéíóúñ0-9]+", mensaje.lower())
    terminos = []
    for token in tokens:
        if token in STOPWORDS:
            continue
        if token.isdigit():
            continue
        if len(token) <= 1 and token not in TALLAS_CONOCIDAS:
            continue
        terminos.append(token)
    expandidos = set(terminos)
    for termino in terminos:
        if termino.endswith("s") and len(termino) > 3:
            expandidos.add(termino[:-1])
    return sorted(expandidos)


def _extraer_colores_mencionados(mensaje: str) -> list[str]:
    encontrados = []
    for color, patron in COLORES_CONOCIDOS.items():
        if re.search(rf"\b{re.escape(color)}\b", mensaje):
            encontrados.append(patron)
    if "azul marino" in encontrados and "azul" in encontrados:
        encontrados.remove("azul")
    return sorted(set(encontrados))


def _extraer_tallas_mencionadas(mensaje: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", mensaje.lower())
    return sorted({token for token in tokens if token in TALLAS_CONOCIDAS})


def _extraer_sucursales_mencionadas(mensaje: str) -> list[str]:
    patrones = []
    if "ventura" in mensaje:
        patrones.append("ventura")
    if "centro" in mensaje:
        patrones.append("centro")
    if "santa cruz" in mensaje:
        patrones.append("santa cruz")
    return sorted(set(patrones))


def _extraer_precio_maximo(mensaje: str) -> float | None:
    if not any(palabra in mensaje for palabra in ("barato", "barata", "menos de", "menor a", "maximo", "máximo", "hasta")):
        return None
    match = re.search(r"(?:menos de|menor a|hasta|maximo|máximo)\s*(\d+(?:[.,]\d+)?)", mensaje)
    return float(match.group(1).replace(",", ".")) if match else None


def _hay_filtros_estrictos(filtros: dict[str, object]) -> bool:
    return bool(filtros["color_patrones"] or filtros["talla_patrones"] or filtros["sucursal_patrones"])


def _buscar_alternativas(terminos: list[str], filtros: dict[str, object], producto_id: int | None, sucursal_id: int | None) -> list[dict[str, object]]:
    color_patrones = list(filtros["color_patrones"])
    talla_patrones = list(filtros["talla_patrones"])
    sucursal_patrones = list(filtros["sucursal_patrones"])
    precio_max = filtros["precio_max"]
    intentos = [
        {"color_patrones": color_patrones, "talla_patrones": [], "sucursal_patrones": sucursal_patrones},
        {"color_patrones": [], "talla_patrones": talla_patrones, "sucursal_patrones": sucursal_patrones},
        {"color_patrones": [], "talla_patrones": [], "sucursal_patrones": sucursal_patrones},
        {"color_patrones": [], "talla_patrones": [], "sucursal_patrones": []},
    ]
    alternativas: list[dict[str, object]] = []
    vistos: set[tuple[object, object, object, object]] = set()
    for intento in intentos:
        encontrados = buscar_productos_para_asistente(terminos=terminos, color_patrones=intento["color_patrones"], talla_patrones=intento["talla_patrones"], sucursal_patrones=intento["sucursal_patrones"], precio_max=precio_max, producto_id=producto_id, sucursal_id=sucursal_id, limite=4)
        for item in encontrados:
            key = (item.get("producto_id"), item.get("talla"), item.get("color"), item.get("sucursal"))
            if key not in vistos:
                alternativas.append(item)
                vistos.add(key)
            if len(alternativas) == 4:
                return alternativas
    return alternativas


def _respuesta_productos(productos: list[dict[str, object]], tipo: str, alternativas: list[dict[str, object]] | None = None, filtros: dict[str, object] | None = None) -> str:
    if not productos:
        if alternativas:
            return "No encontré una coincidencia exacta para tu consulta, pero sí encontré alternativas reales disponibles."
        precio_max = filtros.get("precio_max") if filtros else None
        if precio_max is not None:
            return f"No encontré prendas disponibles por Bs {_formatear_precio_simple(precio_max)} o menos. Puedes probar con un precio un poco mayor, otra categoría o revisar otra sucursal."
        return "No encontré prendas disponibles que coincidan con tu consulta. Puedes intentar con otro color, talla, categoría o sucursal."
    primero = productos[0]
    stock = int(primero.get("stock_real") or 0)
    sucursal = primero.get("sucursal") or "una sucursal disponible"
    talla = primero.get("talla")
    color = primero.get("color")
    nombre = primero.get("nombre")
    detalle = f"{nombre}"
    if talla or color:
        detalle += f" en {talla or 'talla disponible'} / {color or 'color disponible'}"
    if len(productos) == 1:
        return f"Sí, encontré {detalle}, disponible en {sucursal} con {stock} unidad(es)."
    extras = len(productos) - 1
    if tipo in {"recomendacion", "recomendacion_contextual"}:
        return f"Encontré opciones reales del catálogo. La primera es {detalle}, disponible en {sucursal} con {stock} unidad(es). También hay {extras} alternativa(s) más."
    return f"Sí, encontré {detalle}, disponible en {sucursal} con {stock} unidad(es). Además encontré {extras} resultado(s) relacionado(s)."


def _respuesta_sucursales(sucursales: list[dict[str, object]]) -> str:
    if not sucursales:
        return "No encontré sucursales activas registradas en este momento."
    nombres = [f"{item['nombre']} ({item['ciudad']})" for item in sucursales[:5]]
    return "Estas son algunas sucursales activas: " + ", ".join(nombres) + "."


def _formatear_precio_simple(value: object) -> str:
    numero = float(value)
    return str(int(numero)) if numero.is_integer() else f"{numero:.2f}"


def _respuesta_ayuda_proceso(tipo: str) -> str:
    return RESPUESTAS_AYUDA_PROCESO.get(tipo, RESPUESTAS_AYUDA_PROCESO["ayuda_reservas"])


def _respuesta_mis_reservas(usuario_actual: dict[str, object] | None) -> AsistenteChatResponse:
    if usuario_actual is None:
        return _respuesta_requiere_login()
    reservas = listar_reservas_cliente(int(usuario_actual["id"]))
    if not reservas:
        return AsistenteChatResponse(respuesta="No encontré reservas registradas para tu cuenta.", tipo="consulta_personal_reservas")
    resumen = [f"{reserva['codigo']} en {reserva['sucursal']} está {reserva['estado']}" for reserva in reservas[:3]]
    return AsistenteChatResponse(respuesta="Estas son tus reservas más recientes: " + "; ".join(resumen) + ".", tipo="consulta_personal_reservas")


def _respuesta_mis_favoritos(usuario_actual: dict[str, object] | None) -> AsistenteChatResponse:
    if usuario_actual is None:
        return _respuesta_requiere_login()
    cliente_id = recomendacion_repository.obtener_cliente_id(int(usuario_actual["id"]))
    if cliente_id is None:
        return AsistenteChatResponse(respuesta="Tu usuario no tiene un cliente asociado para consultar favoritos.", tipo="consulta_personal_favoritos")
    favoritos = recomendacion_repository.listar_favoritos(cliente_id)
    productos = _mapear_catalogo_a_productos([obtener_prenda_catalogo(producto_id) for producto_id in favoritos[:6]])
    if not productos:
        return AsistenteChatResponse(respuesta="Todavía no tienes prendas marcadas como favoritas.", tipo="consulta_personal_favoritos")
    return AsistenteChatResponse(respuesta=f"Encontré {len(productos)} prenda(s) en tus favoritos.", tipo="consulta_personal_favoritos", productos=productos)


def _respuesta_mis_recomendaciones(usuario_actual: dict[str, object] | None) -> AsistenteChatResponse:
    if usuario_actual is None:
        return _respuesta_requiere_login()
    cliente_id = recomendacion_repository.obtener_cliente_id(int(usuario_actual["id"]))
    if cliente_id is None:
        return AsistenteChatResponse(respuesta="Tu usuario no tiene un cliente asociado para generar recomendaciones personales.", tipo="consulta_personal_recomendaciones")
    productos = _mapear_catalogo_a_productos(recomendar_para_cliente(cliente_id))
    if not productos:
        return AsistenteChatResponse(respuesta="Aún no tengo suficientes favoritos, compras o preferencias para recomendarte prendas personalizadas.", tipo="consulta_personal_recomendaciones")
    return AsistenteChatResponse(respuesta="Con base en tus favoritos, compras o preferencias, estas prendas podrían gustarte.", tipo="consulta_personal_recomendaciones", productos=productos)


def _respuesta_requiere_login() -> AsistenteChatResponse:
    return AsistenteChatResponse(respuesta="Para revisar esa información personal necesito que inicies sesión.", tipo="requiere_login", requiere_login=True, acciones=[{"tipo": "login", "label": "Iniciar sesión", "url": "/login"}])


def _redactar_con_ia(mensaje: str, productos: list[dict[str, object]], respuesta_base: str, tipo: str, alternativas: list[dict[str, object]] | None = None) -> str:
    if AI_ASSISTANT_PROVIDER in {"VERTEX", "GEMINI"}:
        try:
            return redactar_asistente_con_vertex(mensaje, tipo, productos, alternativas or [], respuesta_base)
        except Exception:
            return respuesta_base

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return respuesta_base
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        modelo = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
        datos = [{"producto": row.get("nombre"), "categoria": row.get("categoria"), "marca": row.get("marca"), "talla": row.get("talla"), "color": row.get("color"), "sucursal": row.get("sucursal"), "ciudad": row.get("ciudad"), "stock_real": row.get("stock_real"), "precio_vigente": _serializar_decimal(row.get("precio_vigente"))} for row in productos[:6]]
        completion = client.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": "Eres el asistente de StyleAR. Responde breve en español. Solo usa datos reales entregados; no inventes productos, precios, stock ni sucursales."},
                {"role": "user", "content": f"Pregunta: {mensaje}\nTipo: {tipo}\nDatos reales: {datos}\nRespuesta segura base: {respuesta_base}\nRedacta una respuesta natural manteniendo esos hechos."},
            ],
            temperature=0.2,
            max_tokens=220,
        )
        contenido = completion.choices[0].message.content
        return contenido.strip() if contenido else respuesta_base
    except Exception:
        return respuesta_base


def _mapear_producto(row: dict[str, object]) -> AsistenteProductoResponse:
    return AsistenteProductoResponse(producto_id=int(row["producto_id"]), nombre=str(row["nombre"]), categoria=_str_o_none(row.get("categoria")), marca=_str_o_none(row.get("marca")), talla=_str_o_none(row.get("talla")), color=_str_o_none(row.get("color")), sucursal=_str_o_none(row.get("sucursal")), ciudad=_str_o_none(row.get("ciudad")), stock_disponible=_int_o_none(row.get("stock_disponible")), stock_reservado=_int_o_none(row.get("stock_reservado")), stock_real=_int_o_none(row.get("stock_real")), precio_vigente=_float_o_none(row.get("precio_vigente")))


def _mapear_catalogo_a_productos(items: list[dict[str, object] | None]) -> list[AsistenteProductoResponse]:
    productos = []
    for item in items:
        if not item:
            continue
        productos.append(AsistenteProductoResponse(producto_id=int(item["producto_id"]), nombre=str(item["nombre"]), categoria=_str_o_none(item.get("categoria")), marca=_str_o_none(item.get("marca")), stock_real=_int_o_none(item.get("stock_total")), precio_vigente=_float_o_none(item.get("precio_vigente"))))
    return productos


def _filtros_publicos(filtros: dict[str, object]) -> dict[str, object]:
    return {"colores": filtros["color_patrones"], "tallas": filtros["talla_patrones"], "sucursales": filtros["sucursal_patrones"], "precio_max": filtros["precio_max"]}


def _normalizar(texto: str) -> str:
    texto_normalizado = unicodedata.normalize("NFD", texto.lower().strip())
    return "".join(caracter for caracter in texto_normalizado if unicodedata.category(caracter) != "Mn")


def _str_o_none(value: object) -> str | None:
    return str(value) if value is not None else None


def _int_o_none(value: object) -> int | None:
    return int(value) if value is not None else None


def _float_o_none(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _serializar_decimal(value: object) -> object:
    return float(value) if isinstance(value, Decimal) else value
