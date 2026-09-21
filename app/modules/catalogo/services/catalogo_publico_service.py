from fastapi import HTTPException, status

from app.modules.catalogo.repositories.catalogo_publico_repository import (
    listar_sucursales_catalogo,
    listar_prendas_catalogo,
    obtener_filtros_catalogo,
    obtener_disponibilidad_producto,
    obtener_prenda_catalogo,
)
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


def listar_prendas(filtros: CatalogoFiltros) -> CatalogoPrendasResponse:
    items, total = listar_prendas_catalogo(filtros.model_dump())
    return CatalogoPrendasResponse(
        items=items,
        total=total,
        pagina=filtros.pagina,
        por_pagina=filtros.por_pagina,
    )


def obtener_prenda(producto_id: int, sucursal_id: int | None = None) -> CatalogoPrendaDetalleResponse:
    prenda = obtener_prenda_catalogo(producto_id, sucursal_id)

    if prenda is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prenda no encontrada en el catalogo.",
        )

    return CatalogoPrendaDetalleResponse(**prenda)


def obtener_disponibilidad(
    producto_id: int,
    talla_id: int | None = None,
    color_id: int | None = None,
    sucursal_id: int | None = None,
) -> CatalogoDisponibilidadProductoResponse:
    prenda = obtener_prenda_catalogo(producto_id)

    if prenda is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prenda no encontrada en el catalogo.",
        )

    return CatalogoDisponibilidadProductoResponse(
        producto_id=producto_id,
        disponibilidad=obtener_disponibilidad_producto(producto_id, talla_id, color_id, sucursal_id),
    )


def listar_sucursales() -> list[CatalogoSucursalResponse]:
    return [CatalogoSucursalResponse(**row) for row in listar_sucursales_catalogo()]


def obtener_filtros() -> CatalogoFiltrosResponse:
    return CatalogoFiltrosResponse(**obtener_filtros_catalogo())
