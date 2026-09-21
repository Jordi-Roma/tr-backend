from fastapi import HTTPException
from app.modules.autenticacion.repositories.bitacora_repository import registrar_bitacora

from app.modules.administracion.repositories.catalogo_repository import (
    activar_categoria,
    activar_color,
    activar_talla,
    actualizar_categoria,
    actualizar_color,
    actualizar_talla,
    contar_productos_activos_por_categoria,
    contar_variantes_activas_por_color,
    contar_variantes_activas_por_talla,
    crear_categoria,
    crear_color,
    crear_talla,
    desactivar_categoria,
    desactivar_color,
    desactivar_talla,
    listar_categorias,
    listar_colores,
    listar_tallas,
    obtener_categoria_por_id,
    obtener_categoria_por_nombre,
    obtener_color_por_id,
    obtener_color_por_nombre,
    obtener_talla_por_id,
    obtener_talla_por_nombre,
    obtener_talla_por_nombre_y_tipo,
    obtener_descendientes_categoria,
    activar_marca,
    actualizar_marca,
    contar_productos_activos_por_marca,
    crear_marca,
    desactivar_marca,
    listar_marcas,
    obtener_marca_por_id,
    obtener_marca_por_nombre,
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

def obtener_categorias() -> list[CategoriaResponse]:
    categorias = listar_categorias()
    return [construir_categoria_response(c) for c in categorias]


def obtener_categoria(categoria_id: int) -> CategoriaResponse:
    categoria = obtener_categoria_por_id(categoria_id)

    if categoria is None:
        raise HTTPException(status_code=404, detail="Categoría no encontrada.")

    return construir_categoria_response(categoria)


def registrar_categoria(
    request: CrearCategoriaRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> CategoriaResponse:
    if obtener_categoria_por_nombre(request.nombre) is not None:
        raise HTTPException(
            status_code=409,
            detail="Ya existe una categoría con ese nombre.",
        )

    if request.categoria_padre_id is not None:
        padre = obtener_categoria_por_id(request.categoria_padre_id)
        if padre is None:
            raise HTTPException(status_code=400, detail="La categoría padre no existe.")
        if not padre["activo"]:
            raise HTTPException(status_code=400, detail="La categoría padre está inactiva.")

    categoria = crear_categoria(
        categoria_padre_id=request.categoria_padre_id,
        nombre=request.nombre.strip(),
        descripcion=request.descripcion,
    )
    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="CREAR",
        modulo="CATALOGO",
        resultado="EXITOSO",
        descripcion=f"Categoría creada: {request.nombre.strip()}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return construir_categoria_response(categoria)


def editar_categoria(
    categoria_id: int,
    request: ActualizarCategoriaRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> CategoriaResponse:
    actual = obtener_categoria_por_id(categoria_id)

    if actual is None:
        raise HTTPException(status_code=404, detail="Categoría no encontrada.")

    existente = obtener_categoria_por_nombre(request.nombre)
    if existente is not None and int(existente["id"]) != categoria_id:
        raise HTTPException(
            status_code=409,
            detail="Ya existe otra categoría con ese nombre.",
        )

    if request.categoria_padre_id is not None:
        if request.categoria_padre_id == categoria_id:
            raise HTTPException(status_code=400, detail="Una categoría no puede ser padre de sí misma.")
        
        padre = obtener_categoria_por_id(request.categoria_padre_id)
        if padre is None:
            raise HTTPException(status_code=400, detail="La categoría padre no existe.")
        if not padre["activo"]:
            raise HTTPException(status_code=400, detail="La categoría padre está inactiva.")
            
        descendientes = obtener_descendientes_categoria(categoria_id)
        if request.categoria_padre_id in descendientes:
            raise HTTPException(status_code=400, detail="Una categoría no puede tener como padre a una de sus propias subcategorías.")

    categoria = actualizar_categoria(
        categoria_id=categoria_id,
        categoria_padre_id=request.categoria_padre_id,
        nombre=request.nombre.strip(),
        descripcion=request.descripcion,
    )

    if categoria is None:
        raise HTTPException(status_code=404, detail="Categoría no encontrada.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="ACTUALIZAR",
        modulo="CATALOGO",
        resultado="EXITOSO",
        descripcion=f"Categoría actualizada: ID {categoria_id} ({request.nombre.strip()})",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return construir_categoria_response(categoria)


def eliminar_categoria(
    categoria_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    categoria = obtener_categoria_por_id(categoria_id)

    if categoria is None or categoria["activo"] is not True:
        raise HTTPException(status_code=404, detail="Categoría no encontrada.")

    total_productos = contar_productos_activos_por_categoria(categoria_id)

    if total_productos > 0:
        raise HTTPException(
            status_code=409,
            detail=(
                f"No se puede desactivar la categoría porque tiene "
                f"{total_productos} producto(s) activo(s) asociado(s)."
            ),
        )

    desactivado = desactivar_categoria(categoria_id)

    if not desactivado:
        raise HTTPException(status_code=404, detail="Categoría no encontrada.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="DESACTIVAR",
        modulo="CATALOGO",
        resultado="EXITOSO",
        descripcion=f"Categoría desactivada: ID {categoria_id} ({categoria['nombre']})",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return MensajeResponse(mensaje="Categoría desactivada correctamente.")


def reactivar_categoria(
    categoria_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> CategoriaResponse:
    categoria_actual = obtener_categoria_por_id(categoria_id)

    if categoria_actual is None:
        raise HTTPException(status_code=404, detail="Categoría no encontrada.")

    categoria = activar_categoria(categoria_id)

    if categoria is None:
        raise HTTPException(status_code=404, detail="Categoría no encontrada.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="ACTIVAR",
        modulo="CATALOGO",
        resultado="EXITOSO",
        descripcion=f"Categoría reactivada: ID {categoria_id} ({categoria['nombre']})",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return construir_categoria_response(categoria)


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

def obtener_tallas(tipo_prenda: str | None = None) -> list[TallaResponse]:
    tallas = listar_tallas(tipo_prenda=tipo_prenda)
    return [construir_talla_response(t) for t in tallas]


def obtener_talla(talla_id: int) -> TallaResponse:
    talla = obtener_talla_por_id(talla_id)

    if talla is None:
        raise HTTPException(status_code=404, detail="Talla no encontrada.")

    return construir_talla_response(talla)


def registrar_talla(
    request: CrearTallaRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> TallaResponse:
    if obtener_talla_por_nombre_y_tipo(request.nombre, request.tipo_prenda) is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Ya existe una talla '{request.nombre.strip()}' para prendas tipo {request.tipo_prenda}.",
        )

    talla = crear_talla(
        nombre=request.nombre.strip(),
        descripcion=request.descripcion,
        tipo_prenda=request.tipo_prenda,
        ancho_cm=request.ancho_cm,
        largo_cm=request.largo_cm,
    )
    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="CREAR",
        modulo="CATALOGO",
        resultado="EXITOSO",
        descripcion=f"Talla creada: {request.nombre.strip()}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return construir_talla_response(talla)


def editar_talla(
    talla_id: int,
    request: ActualizarTallaRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> TallaResponse:
    actual = obtener_talla_por_id(talla_id)

    if actual is None:
        raise HTTPException(status_code=404, detail="Talla no encontrada.")

    existente = obtener_talla_por_nombre_y_tipo(request.nombre, request.tipo_prenda)
    if existente is not None and int(existente["id"]) != talla_id:
        raise HTTPException(
            status_code=409,
            detail=f"Ya existe otra talla '{request.nombre.strip()}' para prendas tipo {request.tipo_prenda}.",
        )

    talla = actualizar_talla(
        talla_id=talla_id,
        nombre=request.nombre.strip(),
        descripcion=request.descripcion,
        tipo_prenda=request.tipo_prenda,
        ancho_cm=request.ancho_cm,
        largo_cm=request.largo_cm,
    )

    if talla is None:
        raise HTTPException(status_code=404, detail="Talla no encontrada.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="ACTUALIZAR",
        modulo="CATALOGO",
        resultado="EXITOSO",
        descripcion=f"Talla actualizada: ID {talla_id} ({request.nombre.strip()})",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return construir_talla_response(talla)


def eliminar_talla(
    talla_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    talla = obtener_talla_por_id(talla_id)

    if talla is None or talla["activo"] is not True:
        raise HTTPException(status_code=404, detail="Talla no encontrada.")

    total_variantes = contar_variantes_activas_por_talla(talla_id)

    if total_variantes > 0:
        raise HTTPException(
            status_code=409,
            detail=(
                f"No se puede desactivar la talla porque tiene "
                f"{total_variantes} variante(s) activa(s) asociada(s)."
            ),
        )

    desactivado = desactivar_talla(talla_id)

    if not desactivado:
        raise HTTPException(status_code=404, detail="Talla no encontrada.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="DESACTIVAR",
        modulo="CATALOGO",
        resultado="EXITOSO",
        descripcion=f"Talla desactivada: ID {talla_id} ({talla['nombre']})",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return MensajeResponse(mensaje="Talla desactivada correctamente.")


def reactivar_talla(
    talla_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> TallaResponse:
    talla_actual = obtener_talla_por_id(talla_id)

    if talla_actual is None:
        raise HTTPException(status_code=404, detail="Talla no encontrada.")

    talla = activar_talla(talla_id)

    if talla is None:
        raise HTTPException(status_code=404, detail="Talla no encontrada.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="ACTIVAR",
        modulo="CATALOGO",
        resultado="EXITOSO",
        descripcion=f"Talla reactivada: ID {talla_id} ({talla['nombre']})",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return construir_talla_response(talla)


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

def obtener_colores() -> list[ColorResponse]:
    colores = listar_colores()
    return [construir_color_response(c) for c in colores]


def obtener_color(color_id: int) -> ColorResponse:
    color = obtener_color_por_id(color_id)

    if color is None:
        raise HTTPException(status_code=404, detail="Color no encontrado.")

    return construir_color_response(color)


def registrar_color(
    request: CrearColorRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> ColorResponse:
    if obtener_color_por_nombre(request.nombre) is not None:
        raise HTTPException(
            status_code=409,
            detail="Ya existe un color con ese nombre.",
        )

    color = crear_color(
        nombre=request.nombre.strip(),
        codigo_hex=request.codigo_hex,
    )
    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="CREAR",
        modulo="CATALOGO",
        resultado="EXITOSO",
        descripcion=f"Color creado: {request.nombre.strip()}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return construir_color_response(color)


def editar_color(
    color_id: int,
    request: ActualizarColorRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> ColorResponse:
    actual = obtener_color_por_id(color_id)

    if actual is None:
        raise HTTPException(status_code=404, detail="Color no encontrado.")

    existente = obtener_color_por_nombre(request.nombre)
    if existente is not None and int(existente["id"]) != color_id:
        raise HTTPException(
            status_code=409,
            detail="Ya existe otro color con ese nombre.",
        )

    color = actualizar_color(
        color_id=color_id,
        nombre=request.nombre.strip(),
        codigo_hex=request.codigo_hex,
    )

    if color is None:
        raise HTTPException(status_code=404, detail="Color no encontrado.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="ACTUALIZAR",
        modulo="CATALOGO",
        resultado="EXITOSO",
        descripcion=f"Color actualizado: ID {color_id} ({request.nombre.strip()})",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return construir_color_response(color)


def eliminar_color(
    color_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    color = obtener_color_por_id(color_id)

    if color is None or color["activo"] is not True:
        raise HTTPException(status_code=404, detail="Color no encontrado.")

    total_variantes = contar_variantes_activas_por_color(color_id)

    if total_variantes > 0:
        raise HTTPException(
            status_code=409,
            detail=(
                f"No se puede desactivar el color porque tiene "
                f"{total_variantes} variante(s) activa(s) asociada(s)."
            ),
        )

    desactivado = desactivar_color(color_id)

    if not desactivado:
        raise HTTPException(status_code=404, detail="Color no encontrado.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="DESACTIVAR",
        modulo="CATALOGO",
        resultado="EXITOSO",
        descripcion=f"Color desactivado: ID {color_id} ({color['nombre']})",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return MensajeResponse(mensaje="Color desactivado correctamente.")


def reactivar_color(
    color_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> ColorResponse:
    color_actual = obtener_color_por_id(color_id)

    if color_actual is None:
        raise HTTPException(status_code=404, detail="Color no encontrado.")

    color = activar_color(color_id)

    if color is None:
        raise HTTPException(status_code=404, detail="Color no encontrado.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="ACTIVAR",
        modulo="CATALOGO",
        resultado="EXITOSO",
        descripcion=f"Color reactivado: ID {color_id} ({color['nombre']})",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return construir_color_response(color)


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

def obtener_marcas() -> list[MarcaResponse]:
    marcas = listar_marcas()
    return [construir_marca_response(m) for m in marcas]


def obtener_marca(marca_id: int) -> MarcaResponse:
    marca = obtener_marca_por_id(marca_id)

    if marca is None:
        raise HTTPException(status_code=404, detail="Marca no encontrada.")

    return construir_marca_response(marca)


def registrar_marca(
    request: CrearMarcaRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MarcaResponse:
    if obtener_marca_por_nombre(request.nombre) is not None:
        raise HTTPException(
            status_code=409,
            detail="Ya existe una marca con ese nombre.",
        )

    marca = crear_marca(
        nombre=request.nombre.strip(),
        descripcion=request.descripcion,
    )
    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="CREAR",
        modulo="CATALOGO",
        resultado="EXITOSO",
        descripcion=f"Marca creada: {request.nombre.strip()}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return construir_marca_response(marca)


def editar_marca(
    marca_id: int,
    request: ActualizarMarcaRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MarcaResponse:
    actual = obtener_marca_por_id(marca_id)

    if actual is None:
        raise HTTPException(status_code=404, detail="Marca no encontrada.")

    existente = obtener_marca_por_nombre(request.nombre)
    if existente is not None and int(existente["id"]) != marca_id:
        raise HTTPException(
            status_code=409,
            detail="Ya existe otra marca con ese nombre.",
        )

    marca = actualizar_marca(
        marca_id=marca_id,
        nombre=request.nombre.strip(),
        descripcion=request.descripcion,
    )

    if marca is None:
        raise HTTPException(status_code=404, detail="Marca no encontrada.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="ACTUALIZAR",
        modulo="CATALOGO",
        resultado="EXITOSO",
        descripcion=f"Marca actualizada: ID {marca_id} ({request.nombre.strip()})",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return construir_marca_response(marca)


def eliminar_marca(
    marca_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    marca = obtener_marca_por_id(marca_id)

    if marca is None or marca["activo"] is not True:
        raise HTTPException(status_code=404, detail="Marca no encontrada.")

    total_productos = contar_productos_activos_por_marca(marca_id)

    if total_productos > 0:
        raise HTTPException(
            status_code=409,
            detail=(
                f"No se puede desactivar la marca porque tiene "
                f"{total_productos} producto(s) activo(s) asociado(s)."
            ),
        )

    desactivado = desactivar_marca(marca_id)

    if not desactivado:
        raise HTTPException(status_code=404, detail="Marca no encontrada.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="DESACTIVAR",
        modulo="CATALOGO",
        resultado="EXITOSO",
        descripcion=f"Marca desactivada: ID {marca_id} ({marca['nombre']})",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return MensajeResponse(mensaje="Marca desactivada correctamente.")


def reactivar_marca(
    marca_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MarcaResponse:
    marca_actual = obtener_marca_por_id(marca_id)

    if marca_actual is None:
        raise HTTPException(status_code=404, detail="Marca no encontrada.")

    marca = activar_marca(marca_id)

    if marca is None:
        raise HTTPException(status_code=404, detail="Marca no encontrada.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="ACTIVAR",
        modulo="CATALOGO",
        resultado="EXITOSO",
        descripcion=f"Marca reactivada: ID {marca_id} ({marca['nombre']})",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return construir_marca_response(marca)


def construir_marca_response(marca: dict[str, object]) -> MarcaResponse:
    return MarcaResponse(
        id=int(marca["id"]),
        nombre=str(marca["nombre"]),
        descripcion=str(marca["descripcion"]) if marca["descripcion"] is not None else None,
        activo=bool(marca["activo"]),
        fecha_creacion=marca["fecha_creacion"],
    )
