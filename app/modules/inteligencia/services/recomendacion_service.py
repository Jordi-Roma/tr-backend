import hashlib
import math
import os

from fastapi import HTTPException

from app.core.config import (
    AI_RECOMMENDATIONS_PROVIDER,
    VERTEX_EMBEDDING_MODEL,
    VERTEX_LOCATION,
    VERTEX_PROJECT_ID,
)
from app.modules.catalogo.repositories.catalogo_publico_repository import (
    listar_prendas_catalogo,
    obtener_prenda_catalogo,
)
from app.modules.inteligencia.repositories import recomendacion_repository as repo


OPENAI_EMBEDDING_MODEL = os.getenv('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small')
MODELO = VERTEX_EMBEDDING_MODEL if AI_RECOMMENDATIONS_PROVIDER == 'VERTEX' else OPENAI_EMBEDDING_MODEL


def _texto_producto(row: dict) -> str:
    campos = ('nombre', 'categoria', 'marca', 'descripcion', 'material', 'genero', 'colores', 'colecciones')
    return '\n'.join(f'{campo}: {row[campo]}' for campo in campos if row.get(campo))


def _crear_embedding(texto: str) -> list[float]:
    if AI_RECOMMENDATIONS_PROVIDER == 'VERTEX':
        return _crear_embedding_vertex(texto)
    if AI_RECOMMENDATIONS_PROVIDER != 'OPENAI':
        raise RuntimeError(f'Proveedor de recomendaciones no soportado: {AI_RECOMMENDATIONS_PROVIDER}.')
    if not os.getenv('OPENAI_API_KEY'):
        raise RuntimeError('OPENAI_API_KEY no está configurada en el backend.')
    from openai import OpenAI

    client = OpenAI(timeout=15.0, max_retries=1)
    response = client.embeddings.create(model=OPENAI_EMBEDDING_MODEL, input=texto)
    return [float(value) for value in response.data[0].embedding]


def _crear_embedding_vertex(texto: str) -> list[float]:
    if not VERTEX_PROJECT_ID:
        raise RuntimeError('VERTEX_PROJECT_ID no está configurado en el backend.')
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError('Falta instalar google-genai en el backend.') from exc

    client = genai.Client(
        vertexai=True,
        project=VERTEX_PROJECT_ID,
        location=VERTEX_LOCATION,
        http_options=types.HttpOptions(api_version='v1'),
    )
    response = client.models.embed_content(
        model=VERTEX_EMBEDDING_MODEL,
        contents=texto,
        config=types.EmbedContentConfig(task_type='RETRIEVAL_DOCUMENT'),
    )
    embeddings = getattr(response, 'embeddings', None) or []
    if not embeddings:
        raise RuntimeError('Vertex no devolvió embedding.')
    values = getattr(embeddings[0], 'values', None) or []
    if not values:
        raise RuntimeError('Vertex devolvió un embedding vacío.')
    return [float(value) for value in values]


def indexar_productos() -> dict:
    if AI_RECOMMENDATIONS_PROVIDER == 'VERTEX':
        if not VERTEX_PROJECT_ID:
            raise HTTPException(status_code=503, detail='VERTEX_PROJECT_ID no está configurado en el backend.')
    elif AI_RECOMMENDATIONS_PROVIDER == 'OPENAI':
        if not os.getenv('OPENAI_API_KEY'):
            raise HTTPException(status_code=503, detail='La clave de OpenAI no está configurada en el backend.')
    elif AI_RECOMMENDATIONS_PROVIDER == 'RULES':
        raise HTTPException(status_code=503, detail='Configura AI_RECOMMENDATIONS_PROVIDER=VERTEX u OPENAI para indexar recomendaciones con IA.')
    else:
        raise HTTPException(status_code=503, detail=f'Proveedor de recomendaciones no soportado: {AI_RECOMMENDATIONS_PROVIDER}.')
    productos = repo.listar_productos_para_indice()
    guardados = repo.obtener_embeddings(MODELO)
    actualizados = 0
    errores = 0
    detalle_errores: list[str] = []
    for producto in productos:
        texto = _texto_producto(producto)
        texto_hash = hashlib.sha256(texto.encode('utf-8')).hexdigest()
        anterior = guardados.get(int(producto['id']))
        if anterior and anterior['texto_hash'] == texto_hash:
            continue
        try:
            vector = _crear_embedding(texto)
            repo.guardar_embedding(int(producto['id']), MODELO, texto_hash, vector)
            actualizados += 1
        except Exception as exc:
            errores += 1
            mensaje = _mensaje_error_embedding(exc)
            if mensaje not in detalle_errores and len(detalle_errores) < 3:
                detalle_errores.append(mensaje)
    return {
        'productos': len(productos),
        'actualizados': actualizados,
        'errores': errores,
        'modelo': MODELO,
        'proveedor': AI_RECOMMENDATIONS_PROVIDER,
        'detalle_errores': detalle_errores,
    }


def _mensaje_error_embedding(exc: Exception) -> str:
    texto = str(exc).lower()
    if 'credit_balance_exhausted' in texto or 'insufficient_quota' in texto or 'no credits remaining' in texto:
        return 'La cuenta de OpenAI no tiene créditos disponibles para generar embeddings.'
    if 'quota' in texto or 'resource_exhausted' in texto:
        return 'Vertex no tiene cuota disponible para generar embeddings en este momento.'
    if 'permission' in texto or 'permission_denied' in texto or '403' in texto:
        return 'Vertex no tiene permisos suficientes para generar embeddings.'
    if 'not found' in texto or '404' in texto:
        return 'El modelo de embeddings de Vertex no está disponible en la ubicación configurada.'
    if 'connection error' in texto:
        return 'No se pudo conectar con el proveedor de IA para generar embeddings.'
    if exc.__class__.__name__ == 'ModuleNotFoundError':
        return 'Falta una dependencia de IA en el entorno backend.'
    return f'No se pudo generar embedding: {exc.__class__.__name__}.'


def _coseno(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return -1.0
    norma_a = math.sqrt(sum(value * value for value in a))
    norma_b = math.sqrt(sum(value * value for value in b))
    if not norma_a or not norma_b:
        return -1.0
    return sum(x * y for x, y in zip(a, b)) / (norma_a * norma_b)


def _candidatos_disponibles(sucursal_id: int | None, talla_id: int | None) -> list[dict]:
    filtros: dict[str, object] = {'solo_disponibles': True, 'por_pagina': 500, 'pagina': 1}
    if sucursal_id is not None:
        filtros['sucursal_id'] = sucursal_id
    if talla_id is not None:
        filtros['talla_id'] = talla_id
    prendas, _ = listar_prendas_catalogo(filtros)
    return [p for p in prendas if p['stock_total'] > 0 and p['precio_final'] is not None]


def _validar_respuesta(producto_id: int, sucursal_id: int | None, talla_id: int | None) -> dict | None:
    prenda = obtener_prenda_catalogo(producto_id, sucursal_id)
    if not prenda or prenda['precio_final'] is None:
        return None
    if talla_id is None:
        return prenda if prenda['stock_total'] > 0 else None
    variantes = [v for v in prenda['variantes'] if
        v['talla_id'] == talla_id and v['stock_total'] > 0 and v['precio_final'] is not None
    ]
    if not variantes:
        return None
    prenda['precio_final'] = min(v['precio_final'] for v in variantes)
    prenda['precio_vigente'] = min(v['precio_vigente'] for v in variantes if v['precio_vigente'] is not None)
    prenda['stock_total'] = sum(int(v['stock_total']) for v in variantes)
    return prenda


def recomendar_desde_producto(producto_id: int, sucursal_id: int | None = None,
                              talla_id: int | None = None, limite: int = 6) -> list[dict]:
    origen = obtener_prenda_catalogo(producto_id)
    if origen is None:
        raise HTTPException(status_code=404, detail='Producto no encontrado.')
    embeddings = repo.obtener_embeddings(MODELO)
    vector_origen = embeddings.get(producto_id)
    disponibles = _candidatos_disponibles(sucursal_id, talla_id)
    if not vector_origen:
        return _recomendaciones_iniciales(
            disponibles,
            producto_id,
            sucursal_id,
            talla_id,
            limite,
            int(origen.get('categoria_id') or 0),
            'Sugerencia inicial mientras se actualizan las recomendaciones con IA.',
        )
    puntuados = []
    for item in disponibles:
        id_ = int(item['producto_id'])
        vector = embeddings.get(id_)
        if id_ != producto_id and vector:
            puntuados.append((
                _coseno(vector_origen['embedding'], vector['embedding']),
                id_,
                'Parecido a la prenda que estás viendo.',
            ))
    puntuados.sort(reverse=True)
    resultado = _materializar(puntuados, sucursal_id, talla_id, limite)
    if resultado:
        return resultado
    return _recomendaciones_iniciales(
        disponibles,
        producto_id,
        sucursal_id,
        talla_id,
        limite,
        int(origen.get('categoria_id') or 0),
        'Producto disponible relacionado por categoría.',
    )


def recomendar_para_cliente(cliente_id: int, limite: int = 8) -> list[dict]:
    embeddings = repo.obtener_embeddings(MODELO)
    preferencias = repo.obtener_preferencias(cliente_id)
    if not preferencias['usar_historial']:
        return []
    favoritos = repo.listar_favoritos(cliente_id)
    compras = repo.listar_compras_confirmadas(cliente_id)
    semillas: list[tuple[int, float]] = [(id_, 3.0) for id_ in favoritos[:20]]
    semillas.extend((int(row['producto_id']), min(float(row['peso']), 3.0) * 1.5) for row in compras)
    categorias = set(int(id_) for id_ in preferencias['categorias'])
    if categorias:
        semillas.extend((int(row['id']), 0.6) for row in repo.listar_productos_para_indice()
                        if int(row['id']) in embeddings and int(row.get('categoria_id') or 0) in categorias)
    vectores = [(embeddings[id_]['embedding'], peso) for id_, peso in semillas if id_ in embeddings]
    if not vectores:
        return _recomendaciones_iniciales(
            _candidatos_disponibles(None, None),
            None,
            None,
            None,
            limite,
            None,
            'Recomendación inicial con prendas disponibles mientras conocemos tus gustos.',
        )
    dimension = len(vectores[0][0])
    perfil = [0.0] * dimension
    for vector, peso in vectores:
        if len(vector) != dimension:
            continue
        for idx, value in enumerate(vector):
            perfil[idx] += value * peso
    excluidos = set(favoritos) | {int(row['producto_id']) for row in compras}
    puntuados = []
    motivo = _motivo_para_cliente(bool(favoritos), bool(compras), bool(categorias))
    for item in _candidatos_disponibles(None, None):
        id_ = int(item['producto_id'])
        vector = embeddings.get(id_)
        if id_ not in excluidos and vector:
            puntuados.append((_coseno(perfil, vector['embedding']), id_, motivo))
    puntuados.sort(reverse=True)
    resultado = _materializar(puntuados, None, None, limite)
    if resultado:
        return resultado
    return _recomendaciones_iniciales(
        _candidatos_disponibles(None, None),
        None,
        None,
        None,
        limite,
        None,
        'Recomendación inicial con prendas disponibles mientras conocemos tus gustos.',
        excluidos,
    )


def _materializar(puntuados: list[tuple[float, int, str]], sucursal_id: int | None,
                 talla_id: int | None, limite: int) -> list[dict]:
    resultado = []
    for score, producto_id, motivo in puntuados:
        prenda = _validar_respuesta(producto_id, sucursal_id, talla_id)
        if prenda:
            resultado.append(_con_motivo(prenda, motivo, score))
        if len(resultado) == limite:
            break
    return resultado


def _recomendaciones_iniciales(candidatos: list[dict], producto_id: int | None,
                              sucursal_id: int | None, talla_id: int | None,
                              limite: int, categoria_id: int | None,
                              motivo: str, excluidos_extra: set[int] | None = None) -> list[dict]:
    excluidos = set(excluidos_extra or set())
    if producto_id is not None:
        excluidos.add(producto_id)
    ordenados = sorted(
        candidatos,
        key=lambda item: (
            0 if categoria_id and int(item.get('categoria_id') or 0) == categoria_id else 1,
            -int(item.get('stock_total') or 0),
            str(item.get('nombre') or ''),
        ),
    )
    resultado = []
    for item in ordenados:
        id_ = int(item['producto_id'])
        if id_ in excluidos:
            continue
        prenda = _validar_respuesta(id_, sucursal_id, talla_id)
        if prenda:
            resultado.append(_con_motivo(prenda, motivo, None))
        if len(resultado) == limite:
            break
    return resultado


def _con_motivo(prenda: dict, motivo: str, score: float | None) -> dict:
    item = dict(prenda)
    item['motivo'] = motivo
    item['score'] = round(float(score), 4) if score is not None else None
    return item


def _motivo_para_cliente(tiene_favoritos: bool, tiene_compras: bool, tiene_categorias: bool) -> str:
    if tiene_favoritos and tiene_compras:
        return 'Similar a tus favoritos y compras anteriores.'
    if tiene_favoritos:
        return 'Similar a tus favoritos.'
    if tiene_compras:
        return 'Relacionado con una compra anterior.'
    if tiene_categorias:
        return 'Coincide con tus preferencias.'
    return 'Recomendación inicial con prendas disponibles.'


def cliente_id_obligatorio(usuario: dict) -> int:
    cliente_id = repo.obtener_cliente_id(int(usuario['id']))
    if cliente_id is None:
        raise HTTPException(status_code=403, detail='Solo clientes pueden usar estas recomendaciones.')
    return cliente_id
