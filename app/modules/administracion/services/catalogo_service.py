from app.modules.administracion.repositories.clasificacion_repository import escribir_clasificacion
from fastapi import HTTPException

from app.modules.administracion.repositories.catalogo_repository import (
    listar_categorias,
    listar_colores,
    listar_tallas,
    obtener_categoria_por_id,
    obtener_color_por_id,
    obtener_talla_por_id,
    listar_marcas,
    obtener_marca_por_id,
)
from app.modules.administracion.schemas.catalogo.catalogo_request import (
    ActualizarCategoriaRequest,
    ActualizarColorRequest,
    ActualizarTallaRequest,
    CrearCategoriaRequest,
    CrearColorRequest,
    CrearTallaRequest,
    ActualizarMarcaRequest,
    CrearMarcaRequest,
)
from app.modules.administracion.schemas.catalogo.catalogo_response import (
    CategoriaResponse,
    ColorResponse,
    MensajeResponse,
    TallaResponse,
    MarcaResponse,
)


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORÍAS
# ═══════════════════════════════════════════════════════════════════════════

def obtener_categorias(*, empresa_id: int) -> list[CategoriaResponse]:
    categorias = listar_categorias(empresa_id=empresa_id)
    return [construir_categoria_response(c) for c in categorias]


def obtener_categoria(categoria_id: int, *, empresa_id: int) -> CategoriaResponse:
    categoria = obtener_categoria_por_id(categoria_id, empresa_id=empresa_id)

    if categoria is None:
        raise HTTPException(status_code=404, detail="Categoría no encontrada.")

    return construir_categoria_response(categoria)


def registrar_categoria(
    request: CrearCategoriaRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> CategoriaResponse:
    fila = escribir_clasificacion('categoria', usuario_actual, registro_id=None, ip=direccion_ip, ua=user_agent, datos=request.model_dump())
    return construir_categoria_response(fila)


def editar_categoria(
    categoria_id: int,
    request: ActualizarCategoriaRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> CategoriaResponse:
    fila = escribir_clasificacion('categoria', usuario_actual, registro_id=categoria_id, ip=direccion_ip, ua=user_agent, datos=request.model_dump())
    return construir_categoria_response(fila)


def eliminar_categoria(
    categoria_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    fila = escribir_clasificacion('categoria', usuario_actual, registro_id=categoria_id, ip=direccion_ip, ua=user_agent, activo=False)
    return MensajeResponse(mensaje="Clasificación desactivada correctamente.")


def reactivar_categoria(
    categoria_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> CategoriaResponse:
    fila = escribir_clasificacion('categoria', usuario_actual, registro_id=categoria_id, ip=direccion_ip, ua=user_agent, activo=True)
    return construir_categoria_response(fila)


def construir_categoria_response(categoria: dict[str, object]) -> CategoriaResponse:
    return CategoriaResponse(
        id=int(categoria["id"]),
        categoria_padre_id=int(categoria["categoria_padre_id"]) if categoria.get("categoria_padre_id") is not None else None,
        categoria_padre_nombre=str(categoria["categoria_padre_nombre"]) if categoria.get("categoria_padre_nombre") is not None else None,
        nombre=str(categoria["nombre"]),
        descripcion=str(categoria["descripcion"]) if categoria["descripcion"] is not None else None,
        activo=bool(categoria["activo"]),
        fecha_creacion=categoria["fecha_creacion"],
    )


# ═══════════════════════════════════════════════════════════════════════════
# TALLAS
# ═══════════════════════════════════════════════════════════════════════════

def obtener_tallas(tipo_prenda: str | None = None, *, empresa_id: int) -> list[TallaResponse]:
    tallas = listar_tallas(tipo_prenda=tipo_prenda, empresa_id=empresa_id)
    return [construir_talla_response(t) for t in tallas]


def obtener_talla(talla_id: int, *, empresa_id: int) -> TallaResponse:
    talla = obtener_talla_por_id(talla_id, empresa_id=empresa_id)

    if talla is None:
        raise HTTPException(status_code=404, detail="Talla no encontrada.")

    return construir_talla_response(talla)


def registrar_talla(
    request: CrearTallaRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> TallaResponse:
    fila = escribir_clasificacion('talla', usuario_actual, registro_id=None, ip=direccion_ip, ua=user_agent, datos=request.model_dump())
    return construir_talla_response(fila)


def editar_talla(
    talla_id: int,
    request: ActualizarTallaRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> TallaResponse:
    fila = escribir_clasificacion('talla', usuario_actual, registro_id=talla_id, ip=direccion_ip, ua=user_agent, datos=request.model_dump())
    return construir_talla_response(fila)


def eliminar_talla(
    talla_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    fila = escribir_clasificacion('talla', usuario_actual, registro_id=talla_id, ip=direccion_ip, ua=user_agent, activo=False)
    return MensajeResponse(mensaje="Clasificación desactivada correctamente.")


def reactivar_talla(
    talla_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> TallaResponse:
    fila = escribir_clasificacion('talla', usuario_actual, registro_id=talla_id, ip=direccion_ip, ua=user_agent, activo=True)
    return construir_talla_response(fila)


def construir_talla_response(talla: dict[str, object]) -> TallaResponse:
    return TallaResponse(
        id=int(talla["id"]),
        nombre=str(talla["nombre"]),
        descripcion=str(talla["descripcion"]) if talla["descripcion"] is not None else None,
        tipo_prenda=str(talla.get("tipo_prenda", "SUPERIOR")),
        ancho_cm=float(talla["ancho_cm"]) if talla.get("ancho_cm") is not None else None,
        largo_cm=float(talla["largo_cm"]) if talla.get("largo_cm") is not None else None,
        activo=bool(talla["activo"]),
        fecha_creacion=talla["fecha_creacion"],
    )


# ═══════════════════════════════════════════════════════════════════════════
# COLORES
# ═══════════════════════════════════════════════════════════════════════════

def obtener_colores(*, empresa_id: int) -> list[ColorResponse]:
    colores = listar_colores(empresa_id=empresa_id)
    return [construir_color_response(c) for c in colores]


def obtener_color(color_id: int, *, empresa_id: int) -> ColorResponse:
    color = obtener_color_por_id(color_id, empresa_id=empresa_id)

    if color is None:
        raise HTTPException(status_code=404, detail="Color no encontrado.")

    return construir_color_response(color)


def registrar_color(
    request: CrearColorRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> ColorResponse:
    fila = escribir_clasificacion('color', usuario_actual, registro_id=None, ip=direccion_ip, ua=user_agent, datos=request.model_dump())
    return construir_color_response(fila)


def editar_color(
    color_id: int,
    request: ActualizarColorRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> ColorResponse:
    fila = escribir_clasificacion('color', usuario_actual, registro_id=color_id, ip=direccion_ip, ua=user_agent, datos=request.model_dump())
    return construir_color_response(fila)


def eliminar_color(
    color_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    fila = escribir_clasificacion('color', usuario_actual, registro_id=color_id, ip=direccion_ip, ua=user_agent, activo=False)
    return MensajeResponse(mensaje="Clasificación desactivada correctamente.")


def reactivar_color(
    color_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> ColorResponse:
    fila = escribir_clasificacion('color', usuario_actual, registro_id=color_id, ip=direccion_ip, ua=user_agent, activo=True)
    return construir_color_response(fila)


def construir_color_response(color: dict[str, object]) -> ColorResponse:
    return ColorResponse(
        id=int(color["id"]),
        nombre=str(color["nombre"]),
        codigo_hex=str(color["codigo_hex"]) if color["codigo_hex"] is not None else None,
        activo=bool(color["activo"]),
        fecha_creacion=color["fecha_creacion"],
    )


# ═══════════════════════════════════════════════════════════════════════════
# MARCAS
# ═══════════════════════════════════════════════════════════════════════════

def obtener_marcas(*, empresa_id: int) -> list[MarcaResponse]:
    marcas = listar_marcas(empresa_id=empresa_id)
    return [construir_marca_response(m) for m in marcas]


def obtener_marca(marca_id: int, *, empresa_id: int) -> MarcaResponse:
    marca = obtener_marca_por_id(marca_id, empresa_id=empresa_id)

    if marca is None:
        raise HTTPException(status_code=404, detail="Marca no encontrada.")

    return construir_marca_response(marca)


def registrar_marca(
    request: CrearMarcaRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MarcaResponse:
    fila = escribir_clasificacion('marca', usuario_actual, registro_id=None, ip=direccion_ip, ua=user_agent, datos=request.model_dump())
    return construir_marca_response(fila)


def editar_marca(
    marca_id: int,
    request: ActualizarMarcaRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MarcaResponse:
    fila = escribir_clasificacion('marca', usuario_actual, registro_id=marca_id, ip=direccion_ip, ua=user_agent, datos=request.model_dump())
    return construir_marca_response(fila)


def eliminar_marca(
    marca_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    fila = escribir_clasificacion('marca', usuario_actual, registro_id=marca_id, ip=direccion_ip, ua=user_agent, activo=False)
    return MensajeResponse(mensaje="Clasificación desactivada correctamente.")


def reactivar_marca(
    marca_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MarcaResponse:
    fila = escribir_clasificacion('marca', usuario_actual, registro_id=marca_id, ip=direccion_ip, ua=user_agent, activo=True)
    return construir_marca_response(fila)


def construir_marca_response(marca: dict[str, object]) -> MarcaResponse:
    return MarcaResponse(
        id=int(marca["id"]),
        nombre=str(marca["nombre"]),
        descripcion=str(marca["descripcion"]) if marca["descripcion"] is not None else None,
        activo=bool(marca["activo"]),
        fecha_creacion=marca["fecha_creacion"],
    )
