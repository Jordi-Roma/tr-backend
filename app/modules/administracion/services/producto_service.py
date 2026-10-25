from app.modules.administracion.repositories import catalogo_comercial_repository as comercial
from fastapi import (
    HTTPException,
)
from app.core.contexto_empresa import (
    exigir_empresa_id,
)
from app.modules.administracion.repositories.producto_repository import (
    listar_productos,
    obtener_producto_por_id,
)
from app.modules.administracion.schemas.producto.producto_request import (
    ActualizarProductoRequest,
    CrearProductoRequest,
)
from app.modules.administracion.schemas.producto.producto_response import (
    ImagenProductoResponse,
    ProductoResponse,
)
from app.modules.administracion.schemas.catalogo.catalogo_response import (
    MensajeResponse,
)

def obtener_productos(usuario_actual: dict[str, object]) -> list[ProductoResponse]:
    productos = listar_productos(exigir_empresa_id(usuario_actual))
    return [construir_producto_response(p) for p in productos]

def obtener_producto(producto_id: int, usuario_actual: dict[str, object]) -> ProductoResponse:
    producto = obtener_producto_por_id(producto_id, exigir_empresa_id(usuario_actual))
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")
    return construir_producto_response(producto)

def registrar_producto(
    request: CrearProductoRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> ProductoResponse:
    
    # Podríamos añadir validación de categoría, proveedores, colecciones si quisiéramos,
    # pero el Foreign Key constraint tirará error 400/500 de psycopg si no existen.
    # En un sistema maduro, validaríamos acá.
    
    rid = comercial.guardar_producto(usuario_actual, request.model_dump(), ip=direccion_ip, ua=user_agent)
    return obtener_producto(rid, usuario_actual)

def editar_producto(
    producto_id: int,
    request: ActualizarProductoRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> ProductoResponse:
    rid = comercial.guardar_producto(usuario_actual, request.model_dump(), producto_id, ip=direccion_ip, ua=user_agent)
    return obtener_producto(rid, usuario_actual)

def eliminar_producto(
    producto_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    comercial.estado_producto(usuario_actual, producto_id, False, ip=direccion_ip, ua=user_agent)
    return MensajeResponse(mensaje="Registro desactivado; su historial se conserva.")

def reactivar_producto(
    producto_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> ProductoResponse:
    comercial.estado_producto(usuario_actual, producto_id, True, ip=direccion_ip, ua=user_agent)
    return obtener_producto(producto_id, usuario_actual)

def construir_producto_response(producto: dict[str, object]) -> ProductoResponse:
    imagenes = [
        ImagenProductoResponse(
            id=int(i["id"]),
            producto_id=int(i["producto_id"]),
            url=str(i["url"]),
            es_principal=bool(i["es_principal"]),
            activo=bool(i["activo"]),
            fecha_creacion=i["fecha_creacion"]
        )
        for i in producto["imagenes"]
    ]
    
    return ProductoResponse(
        id=int(producto["id"]),
        categoria_id=int(producto["categoria_id"]),
        categoria_nombre=str(producto["categoria_nombre"]),
        marca_id=int(producto["marca_id"]) if producto.get("marca_id") else None,
        marca_nombre=str(producto["marca_nombre"]) if producto.get("marca_nombre") else None,
        nombre=str(producto["nombre"]),
        descripcion=str(producto["descripcion"]) if producto["descripcion"] else None,
        material=str(producto["material"]) if producto["material"] else None,
        genero=str(producto["genero"]) if producto["genero"] else None,
        tipo_prenda=str(producto.get("tipo_prenda") or "SUPERIOR"),
        tipo_corte=str(producto.get("tipo_corte") or "REGULAR_FIT"),
        ancho_base_cm=float(producto.get("ancho_base_cm") or 53.0),
        largo_base_cm=float(producto.get("largo_base_cm") or 72.0),
        modelo_3d_url=str(producto["modelo_3d_url"]) if producto.get("modelo_3d_url") else None,
        activo=bool(producto["activo"]),
        fecha_creacion=producto["fecha_creacion"],
        colecciones_ids=list(producto["colecciones_ids"]),
        proveedores_ids=list(producto["proveedores_ids"]),
        imagenes=imagenes
    )
