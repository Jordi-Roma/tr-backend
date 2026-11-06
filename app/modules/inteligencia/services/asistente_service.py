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
)

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


def responder_chat_asistente(request: AsistenteChatRequest, usuario_actual: dict[str, object] | None,
                            empresa_id: int) -> AsistenteChatResponse:
    """Consulta datos autorizados; los hechos nunca proceden de texto generado."""
    from datetime import datetime, timezone
    from fastapi import HTTPException
    from app.modules.inteligencia.repositories import asistente_repository as datos
    contexto = request.contexto
    contexto = datos.validar_contexto(contexto, empresa_id)
    if usuario_actual is not None and usuario_actual.get('empresa_id') != empresa_id:
        raise HTTPException(403, 'La empresa no corresponde a la sesión.')
    mensaje = _normalizar(request.mensaje)
    tipo_personal = _intencion_personal(mensaje)
    seguimiento = bool(re.search(r'^(y |en |cuando |cuanto |esa |ese |la misma|el mismo)',mensaje))
    if contexto and contexto.recurso_tipo:
        if usuario_actual is None:
            return _respuesta_requiere_login()
        # Revalidar incluso si el siguiente mensaje cambia de tema o cuenta.
        propias = datos.consultar_operaciones_cliente(empresa_id,int(usuario_actual['id']),contexto.recurso_tipo,contexto.recurso_id)
        if not propias:
            return _respuesta('No encontré esa operación en tu cuenta. Selecciona una operación propia.', 'operacion_no_disponible', aclaracion=True)
        if (seguimiento or re.search(r'politica|condicion|plazo',mensaje)) and not tipo_personal:
            tipo_personal = contexto.recurso_tipo
    if tipo_personal:
        resultado = _consultar_personal(mensaje,tipo_personal,usuario_actual,empresa_id,contexto)
    elif re.search(r'\b(cambiar(?:la|lo)?|cambios?|devolver(?:la|lo)?|devoluciones|devolucion|reembolsos?|reembolsar|politica)\b',mensaje):
        resultado = _ayuda_empresa('posventa',empresa_id)
    elif re.search(r'\b(delivery|envio|entrega)\b',mensaje) and re.search(r'cuanto|costo|precio|como',mensaje):
        resultado = _ayuda_empresa('ayuda_delivery',empresa_id)
    elif ('horario' in mensaje or re.search(r'(hora|cuando) (abre|cierra)',mensaje)):
        sucursales = listar_sucursales_para_asistente(empresa_id,limite=11)
        resultado = _respuesta('No hay horarios de atención registrados para consultar. Puedes contactar a la sucursal.',
            'sucursales',datos=sucursales[:10],fuentes=['Sucursales publicadas'],hay_mas=len(sucursales)>10)
    else:
        producto_id = contexto.producto_id if contexto else None
        sucursal_id = contexto.sucursal_id if contexto else None
        tipo,filtros,terminos = _interpretar_consulta_asistente(request.mensaje,mensaje,producto_id,sucursal_id,empresa_id)
        # Resolver nombres de sucursal de esta empresa; no mantener una lista fija de ciudades.
        sucursales = listar_sucursales_para_asistente(empresa_id,limite=51)
        nombradas = [s for s in sucursales if _normalizar(str(s['nombre'])) in mensaje]
        if len(nombradas)==1:
            sucursal_id = nombradas[0]['id']
            filtros['sucursal_patrones'] = []
        if seguimiento and contexto:
            for campo in ('color_patrones','talla_patrones'):
                if not filtros[campo]:
                    filtros[campo] = getattr(contexto,campo)
            if filtros['precio_max'] is None:
                filtros['precio_max'] = contexto.precio_max
            if contexto.terminos:
                terminos = contexto.terminos
        # Los colores, tallas y sucursales son filtros, no términos OR que amplían la búsqueda.
        ignorados = set(STOPWORDS) | set(TALLAS_CONOCIDAS) | set(COLORES_CONOCIDOS) | {
            'promocion','promociones','oferta','ofertas','descuento','descuentos','cuanto','cuantos','tienen','esta','este',
            'cual','cuales','y','tambien','sucursal','sucursales','encuentro','quedan','negros','azules','camis','estan'}
        nombres_sucursal = set(' '.join(_normalizar(str(s['nombre'])) for s in nombradas).split())
        terminos = [t for t in terminos if _normalizar(t) not in ignorados|nombres_sucursal
                    and not t.startswith(('promocion','ofert','descuent'))][:8]
        if tipo in ('saludo','capacidades','agradecimiento') and not seguimiento:
            texto = {'saludo':'¡Hola! Puedo ayudarte con prendas, precios, promociones, sucursales, políticas y tus operaciones al iniciar sesión.',
                'capacidades':'Puedo consultar catálogo, variantes, precios, stock, promociones y políticas de esta empresa. Con tu sesión también puedes consultar reservas, compras, pagos, entregas y posventa propias.',
                'agradecimiento':'¡De nada! Puedes consultar otra prenda o una operación de tu cuenta.'}[tipo]
            resultado = _respuesta(texto,tipo)
        elif tipo in TIPOS_AYUDA_PROCESO:
            resultado = _ayuda_empresa(tipo,empresa_id)
        elif tipo=='sucursales' and not seguimiento and not any(p in mensaje for p in PALABRAS_PRODUCTO):
            seleccion = nombradas or sucursales
            resultado = _respuesta(_respuesta_sucursales(seleccion),'sucursales',datos=seleccion[:10],fuentes=['Sucursales publicadas'],hay_mas=len(seleccion)>10)
        elif tipo in ('consulta_personal_favoritos','consulta_personal_recomendaciones'):
            resultado = _respuesta_mis_favoritos(usuario_actual,empresa_id) if tipo.endswith('favoritos') else _respuesta_mis_recomendaciones(usuario_actual,empresa_id)
            resultado.fuentes = ['Favoritos propios'] if tipo.endswith('favoritos') else ['Recomendaciones disponibles']
        elif tipo in ('recomendacion','recomendacion_contextual') and producto_id is not None:
            productos = _mapear_catalogo_a_productos(recomendar_desde_producto(producto_id,empresa_id,sucursal_id=sucursal_id))
            resultado = _respuesta('Estas son sugerencias disponibles relacionadas con la prenda seleccionada.','recomendacion_contextual',productos=productos,fuentes=['Catálogo actual','Recomendaciones relacionadas'])
        else:
            resultado = _consultar_catalogo(mensaje,tipo,filtros,terminos,producto_id,sucursal_id,contexto,empresa_id)
    resultado.consultado_en = datetime.now(timezone.utc).isoformat()
    return resultado


def _interpretar_consulta_asistente(
    mensaje: str,
    mensaje_normalizado: str,
    producto_id: int | None,
    sucursal_id: int | None,
    empresa_id: int,
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

    contiene_sensible = re.search(r'@|eyJ[A-Za-z0-9_-]+\.|\b(token|password|contrasena|contraseña|clave|credencial)\b',mensaje,re.I)
    if AI_ASSISTANT_PROVIDER in {"VERTEX", "GEMINI"} and not contiene_sensible:
        try:
            interpretacion = interpretar_asistente_con_vertex(
                mensaje,
                producto_id=producto_id,
                sucursal_id=sucursal_id,
                sucursales=listar_sucursales_para_asistente(empresa_id),
            )
            tipo = str(interpretacion["tipo"])
            if tipo not in {'catalogo','disponibilidad','recomendacion','recomendacion_contextual'}:
                tipo = tipo_reglas
            filtros = {
                "color_patrones": [str(v)[:60] for v in interpretacion["color_patrones"][:4]],
                "talla_patrones": [str(v)[:10] for v in interpretacion["talla_patrones"][:4]],
                "sucursal_patrones": [str(v)[:60] for v in interpretacion["sucursal_patrones"][:4]],
                "precio_max": max(0,min(100000000,float(interpretacion["precio_max"]))) if interpretacion["precio_max"] is not None else None,
            }
            terminos = [str(t)[:60] for t in interpretacion["terminos"][:8]]
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
        if termino.endswith('ones') and len(termino)>5:
            expandidos.add(termino[:-2])
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


def _buscar_alternativas(terminos: list[str], filtros: dict[str, object], producto_id: int | None,
                         sucursal_id: int | None, empresa_id: int) -> list[dict[str, object]]:
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
        encontrados = buscar_productos_para_asistente(terminos=terminos, color_patrones=intento["color_patrones"], talla_patrones=intento["talla_patrones"], sucursal_patrones=intento["sucursal_patrones"], precio_max=precio_max, producto_id=producto_id, sucursal_id=sucursal_id, limite=4, empresa_id=empresa_id)
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
    nombres = [f"{item['nombre']} ({item['ciudad']})"+
        (f", dirección: {item['direccion']}" if item.get('direccion') else '')+
        (f", teléfono: {item['telefono']}" if item.get('telefono') else '') for item in sucursales[:5]]
    return "Estas son algunas sucursales activas: " + ", ".join(nombres) + "."


def _formatear_precio_simple(value: object) -> str:
    numero = float(value)
    return str(int(numero)) if numero.is_integer() else f"{numero:.2f}"


def _respuesta_ayuda_proceso(tipo: str) -> str:
    return RESPUESTAS_AYUDA_PROCESO.get(tipo, RESPUESTAS_AYUDA_PROCESO["ayuda_reservas"])



def _respuesta_mis_favoritos(usuario_actual: dict[str, object] | None, empresa_id: int) -> AsistenteChatResponse:
    if usuario_actual is None:
        return _respuesta_requiere_login()
    cliente_id = recomendacion_repository.obtener_cliente_id(int(usuario_actual["id"]), empresa_id)
    if cliente_id is None:
        return AsistenteChatResponse(respuesta="Tu usuario no tiene un cliente asociado para consultar favoritos.", tipo="consulta_personal_favoritos")
    favoritos = recomendacion_repository.listar_favoritos(cliente_id, empresa_id)
    productos = _mapear_catalogo_a_productos([obtener_prenda_catalogo(producto_id, None, empresa_id) for producto_id in favoritos[:6]])
    if not productos:
        return AsistenteChatResponse(respuesta="Todavía no tienes prendas marcadas como favoritas.", tipo="consulta_personal_favoritos")
    return AsistenteChatResponse(respuesta=f"Encontré {len(productos)} prenda(s) en tus favoritos.", tipo="consulta_personal_favoritos", productos=productos)


def _respuesta_mis_recomendaciones(usuario_actual: dict[str, object] | None, empresa_id: int) -> AsistenteChatResponse:
    if usuario_actual is None:
        return _respuesta_requiere_login()
    cliente_id = recomendacion_repository.obtener_cliente_id(int(usuario_actual["id"]), empresa_id)
    if cliente_id is None:
        return AsistenteChatResponse(respuesta="Tu usuario no tiene un cliente asociado para generar recomendaciones personales.", tipo="consulta_personal_recomendaciones")
    preferencias = recomendacion_repository.obtener_preferencias(cliente_id,empresa_id)
    if not preferencias['usar_historial']:
        return AsistenteChatResponse(respuesta='La personalización está desactivada en tus preferencias. Puedes consultar prendas relacionadas sin usar tu historial.',tipo='personalizacion_desactivada')
    sugerencias = recomendar_para_cliente(cliente_id, empresa_id)
    productos = _mapear_catalogo_a_productos(sugerencias)
    if not productos:
        return AsistenteChatResponse(respuesta="Aún no tengo suficientes favoritos, compras o preferencias para recomendarte prendas personalizadas.", tipo="consulta_personal_recomendaciones")
    return AsistenteChatResponse(respuesta="Estas son tus sugerencias disponibles. El motivo de cada una indica si es personalizada o inicial.", tipo="consulta_personal_recomendaciones", productos=productos)


def _respuesta_requiere_login() -> AsistenteChatResponse:
    return AsistenteChatResponse(respuesta="Para revisar esa información personal necesito que inicies sesión.", tipo="requiere_login", requiere_login=True, acciones=[{"tipo": "login", "label": "Iniciar sesión", "url": "/login"}])


def _redactar_con_ia(mensaje, productos, respuesta_base, tipo, alternativas=None):
    # El proveedor se limita a clasificación validada; los hechos se presentan mediante plantillas.
    return respuesta_base


def _mapear_producto(row: dict[str, object]) -> AsistenteProductoResponse:
    return AsistenteProductoResponse(producto_id=int(row["producto_id"]), nombre=str(row["nombre"]), categoria=_str_o_none(row.get("categoria")), marca=_str_o_none(row.get("marca")), talla=_str_o_none(row.get("talla")), color=_str_o_none(row.get("color")), sucursal=_str_o_none(row.get("sucursal")), ciudad=_str_o_none(row.get("ciudad")), stock_disponible=_int_o_none(row.get("stock_disponible")), stock_reservado=_int_o_none(row.get("stock_reservado")), stock_real=_int_o_none(row.get("stock_real")), precio_vigente=_float_o_none(row.get("precio_vigente")),
        precio_final=_float_o_none(row.get('precio_final')),precio_final_exacto=str(row['precio_final']) if row.get('precio_final') is not None else None,
        variante_id=row.get('variante_id'),sucursal_id=row.get('sucursal_id'),descripcion=row.get('descripcion'),material=row.get('material'),promocion=row.get('promocion'))


def _mapear_catalogo_a_productos(items: list[dict[str, object] | None]) -> list[AsistenteProductoResponse]:
    productos = []
    for item in items:
        if not item:
            continue
        productos.append(AsistenteProductoResponse(producto_id=int(item["producto_id"]), nombre=str(item["nombre"]), categoria=_str_o_none(item.get("categoria")), marca=_str_o_none(item.get("marca")), stock_real=_int_o_none(item.get("stock_total")), precio_vigente=_float_o_none(item.get("precio_vigente")),
            precio_final=_float_o_none(item.get('precio_final')),precio_final_exacto=str(item['precio_final']) if item.get('precio_final') is not None else None,
            descripcion=item.get('descripcion'),material=item.get('material'),motivo=item.get('motivo')))
    return productos


def _filtros_publicos(filtros: dict[str, object]) -> dict[str, object]:
    return {"colores": filtros["color_patrones"], "tallas": filtros["talla_patrones"], "sucursales": filtros["sucursal_patrones"], "precio_max": filtros["precio_max"]}


def _normalizar(texto: str) -> str:
    texto_normalizado = unicodedata.normalize("NFD", texto.lower().strip())
    return "".join(caracter for caracter in texto_normalizado if unicodedata.category(caracter) != "Mn").strip('¿?¡!.,;: ')


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


def _respuesta(texto, tipo, **campos):
    return AsistenteChatResponse(respuesta=texto,tipo=tipo,**campos)


def _intencion_personal(mensaje):
    if 'recom' in mensaje or 'favorit' in mensaje:
        return None
    personal = bool(re.search(r'\b(mi|mis|ese|esa)\b|ya me|me devolv|numero|codigo|#',mensaje))
    if not personal:
        personal = bool(re.search(r'\b(reserva|pedido|pago|compra|cambio|devolucion|reembolso)\s+\d+',mensaje))
    if not personal:
        return None
    if any(t in mensaje for t in ('reembolso','reintegro','me devolv','me devolvier')):
        return 'REEMBOLSO'
    for palabras,tipo in ((('reserva',),'RESERVA'),(('pedido','delivery','entrega'),'DELIVERY'),
                          (('devolucion',),'DEVOLUCION'),(('cambio',),'CAMBIO'),
                          (('pago','historial','comprobante'),'ORDEN_PAGO'),(('compra',),'VENTA')):
        if any(t in mensaje for t in palabras):
            return tipo
    return None


def _consultar_personal(mensaje,tipo,usuario,empresa_id,contexto):
    from app.modules.inteligencia.repositories.asistente_repository import consultar_operaciones_cliente
    from app.modules.inteligencia.schemas.asistente.asistente_schemas import AsistenteContexto
    from fastapi.encoders import jsonable_encoder
    if usuario is None:
        return _respuesta_requiere_login()
    if recomendacion_repository.obtener_cliente_id(int(usuario['id']),empresa_id) is None:
        return _respuesta('Esta cuenta no tiene un cliente asociado para consultar operaciones propias.','sin_cliente')
    rid = contexto.recurso_id if contexto and contexto.recurso_tipo==tipo else None
    codigo = None
    referencia = re.search(r'(?:codigo|numero|nro|#)\s*[:#]?\s*([a-z0-9][a-z0-9_-]{0,39})',mensaje)
    numero = re.search(r'\b(?:reserva|pago|pedido|compra|cambio|devolucion|reembolso)\s+(\d+)\b',mensaje)
    if referencia:
        if referencia[1].isdigit():
            rid = int(referencia[1])
        else:
            codigo = referencia[1]
            rid = None
    elif numero:
        rid = int(numero[1])
    if rid is not None and not 0<rid<2**63:
        return _respuesta('El identificador de la operación no es válido. Selecciona una operación de tu cuenta.','aclaracion',aclaracion=True)
    if tipo=='REEMBOLSO':
        if contexto and contexto.recurso_tipo in ('DEVOLUCION','CAMBIO','REEMBOLSO_PAGO') and not referencia and not numero:
            filas = consultar_operaciones_cliente(empresa_id,int(usuario['id']),contexto.recurso_tipo,contexto.recurso_id)
        elif contexto and contexto.recurso_tipo in ('ORDEN_PAGO','VENTA') and not referencia and not numero:
            filtro = {'orden_id':contexto.recurso_id} if contexto.recurso_tipo=='ORDEN_PAGO' else {'venta_id':contexto.recurso_id}
            filas = consultar_operaciones_cliente(empresa_id,int(usuario['id']),'REEMBOLSO_PAGO',**filtro)
        else:
            # IDs de dos fuentes distintas no se eligen por coincidencia: pedir el tipo si se proporciona solo número.
            if rid is not None:
                return _respuesta('Indica si se trata de la devolución de una prenda o del reembolso de un pago, y selecciona la operación.','aclaracion',aclaracion=True)
            filas = consultar_operaciones_cliente(empresa_id,int(usuario['id']),'REEMBOLSO_PAGO',codigo=codigo)
            devoluciones = consultar_operaciones_cliente(empresa_id,int(usuario['id']),'DEVOLUCION',codigo=codigo)
            filas += devoluciones
    else:
        filas = consultar_operaciones_cliente(empresa_id,int(usuario['id']),tipo,rid,codigo)
    if not filas:
        return _respuesta('No encontré esa operación en tu cuenta. Puedes revisar tus operaciones y seleccionar una.','operacion_no_disponible',fuentes=['Operaciones propias'],aclaracion=True)
    hay_mas = len(filas)>5
    filas = filas[:5]
    for fila in filas:
        estado = fila['estado']
        if tipo=='REEMBOLSO' or fila['recurso_tipo']=='REEMBOLSO_PAGO':
            fila['reembolso_confirmado'] = estado in ('CONFIRMADO','REEMBOLSADA') or (estado=='CAMBIO_COMPLETADO' and fila.get('fecha_reembolso') is not None)
        fila['siguiente_paso'] = _siguiente_paso(fila)
    resumen = '; '.join(_resumen_operacion(r,mensaje) for r in filas)
    texto = ('Estas son hasta cinco operaciones recientes de tu cuenta: ' if len(filas)>1 else 'Tu operación está registrada así: ') + resumen + '.'
    if tipo=='REEMBOLSO':
        texto += ' Aprobado o pendiente no significa reembolsado; consulta el indicador de confirmación de cada operación.'
    if len(filas)>1:
        texto += ' Selecciona el tipo e identificador de la operación que deseas consultar.'
    nueva = AsistenteContexto(empresa_id=empresa_id,recurso_tipo=filas[0]['recurso_tipo'],recurso_id=filas[0]['id']) if len(filas)==1 else None
    return _respuesta(texto,'consulta_personal',datos=jsonable_encoder(filas),contexto=nueva,
        fuentes=['Operaciones propias actualizadas'],aclaracion=len(filas)>1,hay_mas=hay_mas)


def _resumen_operacion(fila,mensaje):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    def fecha(valor):
        return valor.astimezone(ZoneInfo('America/La_Paz')).isoformat() if isinstance(valor,datetime) else str(valor)
    texto = f"{fila.get('codigo') or fila['id']}: estado registrado {fila['estado'].lower().replace('_',' ')}"
    if fila.get('importe') is not None:
        texto += f", importe {fila['importe']} {fila['moneda']}"
    if fila.get('sucursal'):
        texto += f", sucursal {fila['sucursal']}"
    if fila.get('fecha_cita'):
        texto += f", cita {fecha(fila['fecha_cita'])}"
    if fila.get('fecha_expiracion'):
        texto += f", vencimiento {fecha(fila['fecha_expiracion'])}"
    if fila.get('tiempo_estimado_min') is not None:
        texto += f", estimación registrada de {fila['tiempo_estimado_min']} minutos (no es una hora garantizada de llegada)"
    if fila.get('fecha_entrega'):
        texto += f", entrega registrada {fecha(fila['fecha_entrega'])}"
    if 'reembolso_confirmado' in fila:
        texto += ', reembolso confirmado en el sistema' if fila['reembolso_confirmado'] else ', todavía sin confirmación de reembolso'
    if re.search(r'politica|condicion|plazo',mensaje) and fila.get('politica_aplicada'):
        condiciones = ', '.join(f"{k.replace('_',' ')}: {v}" for k,v in fila['politica_aplicada'].items())
        texto += ', política registrada al iniciar la operación: '+condiciones
    if re.search(r'que hago|siguiente|paso|ahora',mensaje):
        texto += '. '+fila['siguiente_paso']
    return texto


def _siguiente_paso(fila):
    estado = fila['estado']
    if fila['recurso_tipo']=='RESERVA':
        if estado in ('COMPLETADA','CANCELADA','VENCIDA'):
            return 'Consulta el detalle de tu reserva; no está pendiente de atención.'
        return 'Revisa la fecha de cita y el vencimiento en el detalle de tu reserva.'
    if estado in ('ESPERA_ACEPTACION','COTIZADO'):
        return 'Revisa la propuesta en el detalle y acepta o rechaza desde el flujo correspondiente.'
    if estado in ('ESPERA_PAGO','PENDIENTE_PAGO','PENDIENTE'):
        return 'Consulta el detalle para comprobar si hay un pago o paso pendiente.'
    if estado in ('REEMBOLSO_PENDIENTE','ESPERA_REINTEGRO','ERROR_REEMBOLSO'):
        return 'Consulta el seguimiento del reembolso o contacta a la empresa; aún no se confirma la devolución del dinero.'
    return 'Consulta el detalle de la operación para ver sus pasos y seguimiento.'


def _ayuda_empresa(tipo,empresa_id):
    from app.modules.ventas_inventario.services.posventa_service import politica
    from app.modules.ventas_inventario.services.pagos_empresa_service import configuracion
    if tipo=='posventa':
        p = politica(empresa_id)
        datos = {k:p.get(k) for k in ('cambios_habilitados','devoluciones_habilitadas','plazo_cambios','plazo_devoluciones','condiciones_cambios','condiciones_devoluciones')}
        textos=[]
        for plural in ('cambios','devoluciones'):
            if datos['cambios_habilitados' if plural=='cambios' else 'devoluciones_habilitadas']:
                textos.append(f"{plural.capitalize()}: plazo configurado de {datos['plazo_'+plural]} días. Condiciones: {datos['condiciones_'+plural]}")
            else:
                textos.append(f'{plural.capitalize()}: no están habilitados en la política actual de esta empresa.')
        return _respuesta(' '.join(textos)+' La solicitud se evalúa en el proceso correspondiente; el chat no la aprueba.',
            'politica_posventa',datos=[datos],fuentes=['Política vigente de la empresa'])
    if tipo in ('ayuda_pagos','ayuda_historial_pagos'):
        cfg = configuracion(empresa_id)
        metodos = [nombre for nombre,k in (('tarjeta con Stripe','stripe_habilitado'),('QR','qr_habilitado')) if cfg[k]]
        texto = ('Medios digitales habilitados: '+', '.join(metodos)+'.') if metodos else 'No hay medios digitales habilitados en esta empresa.'
        texto += f" El entorno configurado es {cfg['modo']}; un pago de prueba no acredita un cobro real."
        texto += ' Consulta tus pagos desde el historial autenticado para ver el estado de cada operación.'
        return _respuesta(texto,'ayuda_pagos',datos=[{'modo':cfg['modo'],'medios':metodos}],fuentes=['Configuración de pagos de la empresa'])
    if tipo=='ayuda_reservas':
        from app.modules.reservas.repositories.reserva_repository import DIAS_RESERVA_GRATUITA
        return _respuesta(f'La reserva desde el carrito vigente es gratuita y vence a los {DIAS_RESERVA_GRATUITA} días de su creación. Las reservas históricas que tengan anticipo conservan su importe y estado propios. Selecciona prendas con stock, talla, color y sucursal y confirma desde el flujo de reservas; consultar el chat no aparta unidades.',
            tipo,fuentes=['Reglas vigentes de reservas'])
    if tipo=='ayuda_delivery':
        return _respuesta('Selecciona delivery y la dirección en el checkout para obtener la cotización vigente del sistema. El costo y tiempo dependen de esa cotización; aquí no se calcula ni crea un envío. Con tu sesión puedes consultar el estado de tus entregas.',tipo,fuentes=['Flujo vigente de entregas'])
    return _respuesta(_respuesta_ayuda_proceso(tipo),tipo,fuentes=['Ayuda del sistema'])


def _consultar_catalogo(mensaje,tipo,filtros,terminos,producto_id,sucursal_id,contexto,empresa_id):
    from app.modules.inteligencia.schemas.asistente.asistente_schemas import AsistenteContexto
    promocion = any(p in mensaje for p in ('promocion','oferta','descuento'))
    if contexto is None and re.search(r'^(y |esa |ese |en )',mensaje) and not terminos:
        return _respuesta('¿A qué prenda u operación te refieres? Selecciónala o indica su nombre o código.','aclaracion',aclaracion=True)
    if producto_id is None and any(t in mensaje for t in ('esta prenda','ese producto','esa prenda','este producto')):
        return _respuesta('Selecciona la prenda o indica su nombre para consultar su variante.','aclaracion',aclaracion=True)
    if producto_id is not None and re.search(r'\b(material|descripcion|marca)\b',mensaje):
        prenda = obtener_prenda_catalogo(producto_id,sucursal_id,empresa_id)
        if not prenda:
            return _respuesta('La prenda seleccionada ya no está disponible.','producto_no_disponible')
        campos = [k for k in ('material','descripcion','marca') if k in mensaje]
        texto = '; '.join(f"{k.capitalize()}: {prenda.get(k) or 'no registrado'}" for k in campos)
        return _respuesta(texto,'detalle_producto',productos=_mapear_catalogo_a_productos([prenda]),
            contexto=AsistenteContexto(empresa_id=empresa_id,producto_id=producto_id,sucursal_id=sucursal_id),fuentes=['Ficha publicada del producto'])
    if not producto_id and not terminos and not promocion and not any(filtros.values()) and not ('ropa' in mensaje or 'prenda' in mensaje or 'recom' in mensaje):
        return _respuesta('¿Qué prenda, talla o sucursal deseas consultar? También puedo ayudarte con políticas y tus operaciones.','aclaracion',aclaracion=True)
    variante_id = contexto.variante_id if contexto else None
    # Pedir otro color/talla debe cambiar de variante, no fijar la variante anterior.
    if contexto and (_extraer_colores_mencionados(mensaje) or _extraer_tallas_mencionadas(mensaje)):
        variante_id = None
    productos = buscar_productos_para_asistente(terminos=terminos,empresa_id=empresa_id,producto_id=producto_id,
        sucursal_id=sucursal_id,color_patrones=filtros['color_patrones'],talla_patrones=filtros['talla_patrones'],
        sucursal_patrones=filtros['sucursal_patrones'],precio_max=filtros['precio_max'],limite=9,
        solo_promociones=promocion,variante_id=variante_id)
    hay_mas = len(productos)>8
    productos = productos[:8]
    alternativas=[]
    if not productos and _hay_filtros_estrictos(filtros) and not promocion:
        alternativas = _buscar_alternativas(terminos,filtros,producto_id,sucursal_id,empresa_id)
    texto = _respuesta_productos(productos,tipo,alternativas,filtros)
    diagnostico = None
    if not productos and producto_id is not None:
        prenda = obtener_prenda_catalogo(producto_id,sucursal_id,empresa_id)
        variantes = [v for v in (prenda or {}).get('variantes',[]) if (not filtros['talla_patrones'] or v['talla'].lower() in filtros['talla_patrones'])
            and (not filtros['color_patrones'] or any(p in _normalizar(v['color']) for p in filtros['color_patrones']))]
        if not variantes:
            diagnostico='VARIANTE_NO_ENCONTRADA'
            texto='No encontré esa combinación de talla y color publicada para la prenda seleccionada.'
        elif not any(v['stock_total']>0 for v in variantes):
            diagnostico='SIN_STOCK'
            texto='La variante está publicada, pero no tiene unidades utilizables en la sucursal o alcance seleccionado.'
        elif all(v['precio_final'] is None for v in variantes):
            diagnostico='PRECIO_NO_DISPONIBLE'
            texto='La variante tiene existencias pero no cuenta con un precio vigente para ofrecerla.'
    if productos:
        p=productos[0]
        if p['precio_final'] is not None:
            texto += f" Precio de esa variante en {p['sucursal']}: {p['precio_final']:.2f} BOB."
        else:
            texto += ' No hay precio vigente registrado para esa variante.'
        texto += ' El stock es informativo y se verifica otra vez al confirmar la operación.'
    if alternativas:
        texto += ' Las alternativas no cumplen necesariamente todos los filtros solicitados; revisa talla, color y sucursal.'
    if hay_mas:
        texto += ' Se muestran hasta ocho resultados; precisa la prenda o sucursal para acotar la búsqueda.'
    ids = {p['producto_id'] for p in productos}
    nuevo = AsistenteContexto(empresa_id=empresa_id,producto_id=next(iter(ids)) if len(ids)==1 else producto_id,
        sucursal_id=sucursal_id,terminos=terminos,color_patrones=filtros['color_patrones'],
        talla_patrones=filtros['talla_patrones'],precio_max=filtros['precio_max'])
    return _respuesta(texto,'promociones' if promocion else tipo,productos=[_mapear_producto(p) for p in productos],
        alternativas=[_mapear_producto(p) for p in alternativas],filtros_detectados={**_filtros_publicos(filtros),'diagnostico':diagnostico},
        contexto=nuevo,fuentes=['Catálogo actual','Precios y promociones vigentes','Existencias por variante y sucursal'],hay_mas=hay_mas)
