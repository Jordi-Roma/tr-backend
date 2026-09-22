from fastapi import HTTPException
from app.modules.autenticacion.repositories.bitacora_repository import registrar_bitacora
from app.modules.administracion.repositories.producto_repository import (
    actualizar_producto,
    crear_producto,
    desactivar_producto,
    activar_producto,
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
from app.modules.administracion.schemas.catalogo.catalogo_response import MensajeResponse

def obtener_productos() -> list[ProductoResponse]:
    productos = listar_productos()
    return [construir_producto_response(p) for p in productos]

def obtener_producto(producto_id: int) -> ProductoResponse:
    producto = obtener_producto_por_id(producto_id)
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
    
    imagenes = [
        {"url": i.url.strip(), "es_principal": i.es_principal}
        for i in request.imagenes
    ]
    
    producto_id = crear_producto(
        categoria_id=request.categoria_id,
        marca_id=request.marca_id,
        nombre=request.nombre.strip(),
        descripcion=request.descripcion.strip() if request.descripcion else None,
        material=request.material.strip() if request.material else None,
        genero=request.genero.strip().upper() if request.genero else None,
        colecciones_ids=request.colecciones_ids,
        proveedores_ids=request.proveedores_ids,
        imagenes=imagenes,
        tipo_prenda=request.tipo_prenda,
        tipo_corte=request.tipo_corte,
        ancho_base_cm=request.ancho_base_cm,
        largo_base_cm=request.largo_base_cm,
        modelo_3d_url=request.modelo_3d_url.strip() if request.modelo_3d_url else None,
    )

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="CREAR",
        modulo="PRODUCTOS",
        resultado="EXITOSO",
        descripcion=f"Producto creado: {request.nombre.strip()}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return obtener_producto(producto_id)

def editar_producto(
    producto_id: int,
    request: ActualizarProductoRequest,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> ProductoResponse:
    actual = obtener_producto_por_id(producto_id)
    if not actual:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")
        
    imagenes = [
        {"url": i.url.strip(), "es_principal": i.es_principal}
        for i in request.imagenes
    ]

    actualizado = actualizar_producto(
        producto_id=producto_id,
        categoria_id=request.categoria_id,
        marca_id=request.marca_id,
        nombre=request.nombre.strip(),
        descripcion=request.descripcion.strip() if request.descripcion else None,
        material=request.material.strip() if request.material else None,
        genero=request.genero.strip().upper() if request.genero else None,
        colecciones_ids=request.colecciones_ids,
        proveedores_ids=request.proveedores_ids,
        imagenes=imagenes,
        tipo_prenda=request.tipo_prenda,
        tipo_corte=request.tipo_corte,
        ancho_base_cm=request.ancho_base_cm,
        largo_base_cm=request.largo_base_cm,
        modelo_3d_url=request.modelo_3d_url.strip() if request.modelo_3d_url else None,
    )

    if not actualizado:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="ACTUALIZAR",
        modulo="PRODUCTOS",
        resultado="EXITOSO",
        descripcion=f"Producto actualizado: id={producto_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return obtener_producto(producto_id)

def eliminar_producto(
    producto_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> MensajeResponse:
    actual = obtener_producto_por_id(producto_id)
    if not actual:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")

    if not desactivar_producto(producto_id):
        raise HTTPException(status_code=404, detail="No se pudo desactivar el producto.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="DESACTIVAR",
        modulo="PRODUCTOS",
        resultado="EXITOSO",
        descripcion=f"Producto desactivado: id={producto_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return MensajeResponse(mensaje="Producto y sus variantes desactivados correctamente.")

def reactivar_producto(
    producto_id: int,
    usuario_actual: dict[str, object],
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> ProductoResponse:
    actual = obtener_producto_por_id(producto_id)
    if not actual:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")

    if not activar_producto(producto_id):
        raise HTTPException(status_code=404, detail="No se pudo reactivar el producto.")

    registrar_bitacora(
        usuario_id=int(usuario_actual["id"]),
        accion="ACTIVAR",
        modulo="PRODUCTOS",
        resultado="EXITOSO",
        descripcion=f"Producto activado: id={producto_id}",
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
    return obtener_producto(producto_id)

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
