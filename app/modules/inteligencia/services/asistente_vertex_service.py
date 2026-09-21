import json
import re
from decimal import Decimal

from app.core.config import (
    AI_ASSISTANT_PROVIDER,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    VERTEX_LOCATION,
    VERTEX_MODEL,
    VERTEX_PROJECT_ID,
)


TIPOS_ASISTENTE = [
    "saludo",
    "capacidades",
    "agradecimiento",
    "consulta_personal_reservas",
    "consulta_personal_favoritos",
    "consulta_personal_recomendaciones",
    "ayuda_reservas",
    "ayuda_delivery",
    "ayuda_pagos",
    "ayuda_carrito",
    "ayuda_cuenta",
    "ayuda_favoritos",
    "ayuda_historial_pagos",
    "ayuda_vestidor",
    "sucursales",
    "recomendacion",
    "recomendacion_contextual",
    "disponibilidad",
    "catalogo",
]


def _cliente_vertex():
    proveedor = AI_ASSISTANT_PROVIDER
    if proveedor == "GEMINI" and not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY no está configurada.")
    if proveedor != "GEMINI" and not VERTEX_PROJECT_ID:
        raise RuntimeError("VERTEX_PROJECT_ID no está configurado.")
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("Falta instalar google-genai en el backend.") from exc

    if proveedor == "GEMINI":
        client = genai.Client(api_key=GEMINI_API_KEY)
        return client, types, GEMINI_MODEL

    client = genai.Client(
        vertexai=True,
        project=VERTEX_PROJECT_ID,
        location=VERTEX_LOCATION,
        http_options=types.HttpOptions(api_version="v1"),
    )
    return client, types, VERTEX_MODEL


def _extraer_json(texto: str) -> dict[str, object]:
    limpio = texto.strip()
    if limpio.startswith("```"):
        limpio = re.sub(r"^```(?:json)?", "", limpio, flags=re.IGNORECASE).strip()
        limpio = re.sub(r"```$", "", limpio).strip()
    inicio = limpio.find("{")
    fin = limpio.rfind("}")
    if inicio == -1 or fin == -1 or fin <= inicio:
        raise ValueError("Vertex no devolvió JSON válido.")
    return json.loads(limpio[inicio:fin + 1])


def interpretar_asistente_con_vertex(
    mensaje: str,
    producto_id: int | None,
    sucursal_id: int | None,
    sucursales: list[dict[str, object]],
) -> dict[str, object]:
    client, types, modelo = _cliente_vertex()
    prompt = f"""
Eres el intérprete del asistente de tienda StyleAR.
Convierte el mensaje del cliente a intención y filtros JSON para buscar en una base de datos real.

Tipos válidos: {", ".join(TIPOS_ASISTENTE)}.
Tallas válidas: xs, s, m, l, xl, xxl.
Sucursales disponibles: {json.dumps(sucursales, ensure_ascii=False)}.
Contexto actual: producto_id={producto_id}, sucursal_id={sucursal_id}.

Reglas:
- Responde SOLO JSON, sin markdown.
- No inventes productos ni stock.
- Si pide "mis reservas", "mis favoritos", "mis recomendaciones" o historial personal, usa el tipo personal correspondiente.
- Si pregunta cómo reservar o proceso de reserva, usa ayuda_reservas.
- Si pregunta cómo pedir delivery, envío, entrega, ubicación, mapa, cotización o distancia, usa ayuda_delivery.
- Si pregunta cómo pagar, Stripe, tarjeta, compra o pasarela, usa ayuda_pagos.
- Si pregunta cómo usar el carrito, agregar, cambiar cantidad, eliminar o vaciar, usa ayuda_carrito.
- Si pregunta por login, registro, cuenta, contraseña o perfil, usa ayuda_cuenta.
- Si pregunta cómo guardar o ver favoritos, usa ayuda_favoritos.
- Si pregunta dónde ver pagos, historial, recibos, comprobantes, lo que pagó o cosas que pagó, usa ayuda_historial_pagos.
- Si pregunta cómo usar vestidor, probarse ropa, foto, avatar o IA visual, usa ayuda_vestidor.
- Si pregunta por tiendas/sucursales/atención sin pedir producto, usa sucursales.
- Si pide algo parecido/similar/combina con esta prenda y hay producto_id, usa recomendacion_contextual.
- Si pide recomendaciones generales, outfit, invierno, cena, casual, elegante o combinar, usa recomendacion.
- Si pregunta si hay stock/disponibilidad, usa disponibilidad.
- Si busca prendas/categorías/colores/tallas/precios, usa catalogo.
- terminos debe contener palabras útiles para buscar en producto, categoría, marca, material, descripción u ocasión.
- color_patrones debe contener colores mencionados, por ejemplo "azul marino", "negro", "rojo".
- talla_patrones debe contener tallas mencionadas en minúscula.
- sucursal_patrones debe contener palabras de sucursal o ciudad, por ejemplo "centro", "ventura", "santa cruz".
- precio_max debe ser número si pide barato, menos de, menor a, hasta o máximo con importe; si no, null.
- Si pregunta "prendas/productos/cosas que cuesten menos de X Bs", usa catalogo, precio_max=X y no pongas "bs" ni el número dentro de terminos.

Formato exacto:
{{
  "tipo": "catalogo",
  "terminos": [],
  "color_patrones": [],
  "talla_patrones": [],
  "sucursal_patrones": [],
  "precio_max": null
}}

Mensaje: {mensaje}
"""
    response = client.models.generate_content(
        model=modelo,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
        ),
    )
    data = _extraer_json(response.text or "")
    tipo = str(data.get("tipo") or "catalogo").strip()
    if tipo not in TIPOS_ASISTENTE:
        tipo = "catalogo"
    return {
        "tipo": tipo,
        "terminos": _lista_str(data.get("terminos")),
        "color_patrones": _lista_str(data.get("color_patrones")),
        "talla_patrones": [t.lower() for t in _lista_str(data.get("talla_patrones"))],
        "sucursal_patrones": _lista_str(data.get("sucursal_patrones")),
        "precio_max": _float_o_none(data.get("precio_max")),
    }


def redactar_asistente_con_vertex(
    mensaje: str,
    tipo: str,
    productos: list[dict[str, object]],
    alternativas: list[dict[str, object]],
    respuesta_base: str,
) -> str:
    client, types, modelo = _cliente_vertex()
    datos = [_producto_para_prompt(row) for row in productos[:6]]
    datos_alternativas = [_producto_para_prompt(row) for row in alternativas[:4]]
    prompt = f"""
Eres el asistente de StyleAR. Responde breve, natural y útil en español.

Reglas obligatorias:
- Usa SOLO los datos reales entregados.
- No inventes productos, precios, stock, sucursales, tallas ni colores.
- Si no hay productos, dilo claramente y sugiere probar otro color, talla, categoría o sucursal.
- Si hay alternativas, explica que no hubo coincidencia exacta y muestra alternativas.
- Máximo 4 oraciones.

Pregunta del cliente: {mensaje}
Tipo detectado: {tipo}
Productos reales: {json.dumps(datos, ensure_ascii=False)}
Alternativas reales: {json.dumps(datos_alternativas, ensure_ascii=False)}
Respuesta segura base: {respuesta_base}
"""
    response = client.models.generate_content(
        model=modelo,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.2),
    )
    return (response.text or "").strip() or respuesta_base


def _lista_str(valor: object) -> list[str]:
    if not isinstance(valor, list):
        return []
    return [str(item).strip().lower() for item in valor if str(item).strip()]


def _float_o_none(valor: object) -> float | None:
    if valor is None or valor == "":
        return None
    try:
        return float(str(valor).replace(",", "."))
    except ValueError:
        return None


def _producto_para_prompt(row: dict[str, object]) -> dict[str, object]:
    return {
        "producto": row.get("nombre"),
        "categoria": row.get("categoria"),
        "marca": row.get("marca"),
        "talla": row.get("talla"),
        "color": row.get("color"),
        "sucursal": row.get("sucursal"),
        "ciudad": row.get("ciudad"),
        "stock_real": row.get("stock_real"),
        "precio_vigente": _serializar_decimal(row.get("precio_vigente")),
    }


def _serializar_decimal(value: object) -> object:
    return float(value) if isinstance(value, Decimal) else value
