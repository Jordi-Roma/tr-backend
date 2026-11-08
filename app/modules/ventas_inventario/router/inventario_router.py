from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.contexto_empresa import exigir_empresa_id
from app.modules.autenticacion.dependencies.usuario_actual import obtener_usuario_actual
from app.modules.autenticacion.repositories.perfil_repository import _transaccion

from app.modules.administracion.dependencies.empleado_access import (
    requerir_admin_o_encargado,
    requerir_admin_o_encargado_o_cajero,
)
from app.modules.ventas_inventario.schemas.inventario.inventario_schemas import (
    ActualizarStockMinimoRequest,
    CrearTransferenciaRequest,
    CrearVentaPresencialRequest,
    CrearVentaLocalRequest,
    InventarioResponse,
    MovimientoInventarioRequest,
    MovimientoInventarioResponse,
    TransferenciaResponse,
    VentaPresencialResponse,
)
from app.modules.ventas_inventario.services.inventario_service import (
    actualizar_stock_minimo_service,
    crear_transferencia_service,
    crear_venta_service,
    listar_movimientos_service,
    listar_transferencias_service,
    listar_ventas_service,
    obtener_inventario_service,
    obtener_transferencia_service,
    obtener_venta_service,
    registrar_movimiento_service,
    _sucursal_permitida,
)

router = APIRouter(tags=["Ventas e inventario"])


@router.get('/api/v1/inventario/proveedores-opciones')
def proveedores_para_entrada(actor=Depends(requerir_admin_o_encargado)):
    """Selector mínimo de inventario; no concede acceso a la gestión CU08."""
    from app.core.contexto_empresa import exigir_empresa_id
    from app.modules.autenticacion.repositories.perfil_repository import _transaccion
    with _transaccion() as cur:
        cur.execute('SELECT id,nombre,activo FROM proveedor WHERE empresa_id=%s AND activo ORDER BY nombre,id', (exigir_empresa_id(actor),))
        return [dict(r) for r in cur.fetchall()]


@router.get("/api/v1/inventario", response_model=list[InventarioResponse])
def listar_inventario_endpoint(
    sucursal_id: int | None = None,
    producto_id: int | None = None,
    producto_variante_id: int | None = None,
    categoria_id: int | None = None,
    talla_id: int | None = None,
    color_id: int | None = None,
    solo_bajo_stock: bool = False,
    usuario_actual: dict[str, object] = Depends(requerir_admin_o_encargado_o_cajero),
) -> list[InventarioResponse]:
    return obtener_inventario_service(
        usuario_actual,
        {
            "sucursal_id": sucursal_id,
            "producto_id": producto_id,
            "producto_variante_id": producto_variante_id,
            "categoria_id": categoria_id,
            "talla_id": talla_id,
            "color_id": color_id,
            "solo_bajo_stock": solo_bajo_stock,
        },
    )


@router.patch("/api/v1/inventario/{inventario_id}/stock-minimo", response_model=InventarioResponse)
def actualizar_stock_minimo_endpoint(
    inventario_id: int,
    request: ActualizarStockMinimoRequest,
    usuario_actual: dict[str, object] = Depends(requerir_admin_o_encargado),
) -> InventarioResponse:
    return actualizar_stock_minimo_service(usuario_actual, inventario_id, request)


@router.get("/api/v1/movimientos-inventario", response_model=list[MovimientoInventarioResponse])
def listar_movimientos_endpoint(
    sucursal_id: int | None = None,
    producto_variante_id: int | None = None,
    tipo: str | None = None,
    usuario_actual: dict[str, object] = Depends(requerir_admin_o_encargado),
) -> list[MovimientoInventarioResponse]:
    return listar_movimientos_service(
        usuario_actual,
        {"sucursal_id": sucursal_id, "producto_variante_id": producto_variante_id, "tipo": tipo},
    )


@router.post("/api/v1/movimientos-inventario", response_model=MovimientoInventarioResponse)
def registrar_movimiento_endpoint(
    request: MovimientoInventarioRequest,
    usuario_actual: dict[str, object] = Depends(requerir_admin_o_encargado),
) -> MovimientoInventarioResponse:
    return registrar_movimiento_service(usuario_actual, request)


@router.get("/api/v1/transferencias-stock", response_model=list[TransferenciaResponse])
def listar_transferencias_endpoint(
    sucursal_id: int | None = None,
    usuario_actual: dict[str, object] = Depends(requerir_admin_o_encargado),
) -> list[TransferenciaResponse]:
    return listar_transferencias_service(usuario_actual, sucursal_id)


@router.post("/api/v1/transferencias-stock", response_model=TransferenciaResponse)
def crear_transferencia_endpoint(
    request: CrearTransferenciaRequest,
    usuario_actual: dict[str, object] = Depends(requerir_admin_o_encargado),
) -> TransferenciaResponse:
    return crear_transferencia_service(usuario_actual, request)


@router.get("/api/v1/transferencias-stock/{transferencia_id}", response_model=TransferenciaResponse)
def obtener_transferencia_endpoint(
    transferencia_id: int,
    usuario_actual: dict[str, object] = Depends(requerir_admin_o_encargado),
) -> TransferenciaResponse:
    return obtener_transferencia_service(usuario_actual, transferencia_id)


@router.get("/api/v1/ventas-presenciales", response_model=list[VentaPresencialResponse])
def listar_ventas_endpoint(
    sucursal_id: int | None = None,
    usuario_actual: dict[str, object] = Depends(requerir_admin_o_encargado_o_cajero),
    limite: int | None = Query(default=None, ge=1, le=100),
) -> list[VentaPresencialResponse]:
    return listar_ventas_service(usuario_actual, sucursal_id, limite)


@router.post("/api/v1/ventas-presenciales", response_model=VentaPresencialResponse)
def crear_venta_endpoint(
    request: CrearVentaPresencialRequest,
    usuario_actual: dict[str, object] = Depends(requerir_admin_o_encargado_o_cajero),
) -> VentaPresencialResponse:
    return crear_venta_service(usuario_actual, request)


@router.post("/api/v1/ventas-presenciales/offline", response_model=VentaPresencialResponse)
def sincronizar_venta_local(
    request: CrearVentaLocalRequest,
    usuario_actual: dict[str, object] = Depends(requerir_admin_o_encargado_o_cajero),
) -> VentaPresencialResponse:
    return crear_venta_service(usuario_actual, request)


@router.get("/api/v1/operacion-movil/sucursales")
def sucursales_moviles(actor=Depends(obtener_usuario_actual)):
    roles = set(actor['roles'])
    if not roles.intersection({'CLIENTE', 'ADMINISTRADOR', 'ENCARGADO_SUCURSAL', 'CAJERO'}):
        raise HTTPException(403, 'Tu cuenta no tiene acceso a las operaciones móviles.')
    sucursal = None if 'CLIENTE' in roles and not roles.intersection(
        {'ADMINISTRADOR', 'ENCARGADO_SUCURSAL', 'CAJERO'}
    ) else _sucursal_permitida(actor, None)
    with _transaccion() as cur:
        cur.execute('''SELECT id,nombre FROM sucursal
            WHERE empresa_id=%s AND activo AND (%s::bigint IS NULL OR id=%s) ORDER BY id''',
            (exigir_empresa_id(actor), sucursal, sucursal))
        return [dict(row) for row in cur.fetchall()]


@router.get("/api/v1/operacion-movil/catalogo")
def catalogo_movil(
    sucursal_id: int = Query(gt=0),
    desde: int = Query(default=0, ge=0),
    actor=Depends(obtener_usuario_actual),
):
    if sucursal_id not in {row['id'] for row in sucursales_moviles(actor)}:
        raise HTTPException(403, 'No puedes consultar el catálogo de esta sucursal.')
    with _transaccion() as cur:
        cur.execute('''WITH pagina AS MATERIALIZED (
            SELECT v.id AS variante_id,p.id AS producto_id,p.nombre,t.nombre AS talla,
                   c.nombre AS color,greatest(i.stock_disponible-i.stock_reservado,0) AS stock,
                   v.empresa_id,i.sucursal_id
            FROM inventario_sucursal i
            JOIN producto_variante v ON v.id=i.producto_variante_id AND v.empresa_id=i.empresa_id AND v.activo
            JOIN producto p ON p.id=v.producto_id AND p.empresa_id=v.empresa_id AND p.activo
            JOIN categoria ca ON ca.id=p.categoria_id AND ca.empresa_id=p.empresa_id AND ca.activo
            LEFT JOIN talla t ON t.id=v.talla_id AND t.empresa_id=v.empresa_id
            LEFT JOIN color c ON c.id=v.color_id AND c.empresa_id=v.empresa_id
            WHERE i.empresa_id=%s AND i.sucursal_id=%s AND i.activo AND v.id>%s
            ORDER BY v.id LIMIT 101
        ) SELECT variante_id,producto_id,nombre,talla,color,stock,
                 (precio_catalogo(variante_id,empresa_id,sucursal_id)*100)::bigint AS precio_centavos
          FROM pagina ORDER BY variante_id''', (exigir_empresa_id(actor), sucursal_id, desde))
        filas = [dict(row) for row in cur.fetchall()]
    return {'items': filas[:100], 'siguiente': filas[99]['variante_id'] if len(filas) > 100 else None}


@router.get("/api/v1/ventas-presenciales/{venta_id}", response_model=VentaPresencialResponse)
def obtener_venta_endpoint(
    venta_id: int,
    usuario_actual: dict[str, object] = Depends(requerir_admin_o_encargado_o_cajero),
) -> VentaPresencialResponse:
    return obtener_venta_service(usuario_actual, venta_id)
