from decimal import Decimal

from fastapi import APIRouter, Query

from app.modules.catalogo.schemas.catalogo_publico.catalogo_publico_request import (
    CatalogoFiltros,
)
from app.modules.catalogo.schemas.catalogo_publico.catalogo_publico_response import (
    CatalogoDisponibilidadProductoResponse,
    CatalogoFiltrosResponse,
    CatalogoPrendaDetalleResponse,
    CatalogoPrendasResponse,
    CatalogoSucursalResponse,
)
from app.modules.catalogo.services.catalogo_publico_service import (
    listar_sucursales,
    listar_prendas,
    obtener_filtros,
    obtener_disponibilidad,
    obtener_prenda,
)

router = APIRouter(
    prefix="/api/v1/catalogo",
    tags=["Catalogo publico"],
)


@router.get("/prendas", response_model=CatalogoPrendasResponse)
def listar_prendas_endpoint(
    q: str | None = None,
    categoria_id: int | None = None,
    talla_id: int | None = None,
    color_id: int | None = None,
    temporada_id: int | None = None,
    coleccion_id: int | None = None,
    sucursal_id: int | None = None,
    precio_min: Decimal | None = None,
    precio_max: Decimal | None = None,
    orden: str = "relevancia",
    solo_disponibles: bool = False,
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=12, ge=1, le=60),
) -> CatalogoPrendasResponse:
    filtros = CatalogoFiltros(
        q=q,
        categoria_id=categoria_id,
        talla_id=talla_id,
        color_id=color_id,
        temporada_id=temporada_id,
        coleccion_id=coleccion_id,
        sucursal_id=sucursal_id,
        precio_min=precio_min,
        precio_max=precio_max,
        orden=orden,
        solo_disponibles=solo_disponibles,
        pagina=pagina,
        por_pagina=por_pagina,
    )
    return listar_prendas(filtros)


@router.get("/sucursales", response_model=list[CatalogoSucursalResponse])
def listar_sucursales_endpoint() -> list[CatalogoSucursalResponse]:
    return listar_sucursales()


@router.get("/filtros", response_model=CatalogoFiltrosResponse)
def obtener_filtros_endpoint() -> CatalogoFiltrosResponse:
    return obtener_filtros()


@router.get("/prendas/{producto_id}", response_model=CatalogoPrendaDetalleResponse)
def obtener_prenda_endpoint(
    producto_id: int,
    sucursal_id: int | None = None,
) -> CatalogoPrendaDetalleResponse:
    return obtener_prenda(producto_id, sucursal_id)


@router.get(
    "/prendas/{producto_id}/disponibilidad",
    response_model=CatalogoDisponibilidadProductoResponse,
)
def obtener_disponibilidad_endpoint(
    producto_id: int,
    talla_id: int | None = None,
    color_id: int | None = None,
    sucursal_id: int | None = None,
) -> CatalogoDisponibilidadProductoResponse:
    return obtener_disponibilidad(producto_id, talla_id, color_id, sucursal_id)
