from decimal import Decimal
from pydantic import BaseModel


class CatalogoTallaResponse(BaseModel):
    id: int
    nombre: str


class CatalogoColorResponse(BaseModel):
    id: int
    nombre: str
    hex: str | None = None


class CatalogoDisponibilidadResponse(BaseModel):
    sucursal_id: int
    sucursal: str
    ciudad: str
    variante_id: int
    talla_id: int | None = None
    talla: str | None = None
    color_id: int | None = None
    color: str | None = None
    stock_disponible: int
    stock_reservado: int
    disponible: bool


class CatalogoVarianteResponse(BaseModel):
    id: int
    sku: str
    talla_id: int | None = None
    talla: str | None = None
    color_id: int | None = None
    color: str | None = None
    color_hex: str | None = None
    precio_vigente: Decimal | None = None
    precio_final: Decimal | None = None
    tiene_promocion: bool
    stock_total: int
    activo: bool


class CatalogoPrendaItemResponse(BaseModel):
    producto_id: int
    nombre: str
    descripcion: str | None = None
    categoria_id: int
    categoria: str
    marca_id: int | None = None
    marca: str | None = None
    material: str | None = None
    genero: str | None = None
    precio_vigente: Decimal | None = None
    precio_final: Decimal | None = None
    tiene_promocion: bool
    stock_total: int
    tallas: list[CatalogoTallaResponse]
    colores: list[CatalogoColorResponse]
    imagen_principal: str | None = None
    activo: bool


class CatalogoPrendasResponse(BaseModel):
    items: list[CatalogoPrendaItemResponse]
    total: int
    pagina: int
    por_pagina: int


class CatalogoPrendaDetalleResponse(CatalogoPrendaItemResponse):
    colecciones: list[str]
    variantes: list[CatalogoVarianteResponse]
    disponibilidad: list[CatalogoDisponibilidadResponse]


class CatalogoDisponibilidadProductoResponse(BaseModel):
    producto_id: int
    disponibilidad: list[CatalogoDisponibilidadResponse]


class CatalogoSucursalResponse(BaseModel):
    id: int
    nombre: str
    ciudad: str
    latitud: Decimal | None = None
    longitud: Decimal | None = None


class CatalogoOpcionResponse(BaseModel):
    id: int
    nombre: str


class CatalogoFiltrosResponse(BaseModel):
    categorias: list[CatalogoOpcionResponse]
    tallas: list[CatalogoOpcionResponse]
    colores: list[CatalogoColorResponse]
    temporadas: list[CatalogoOpcionResponse]
    colecciones: list[CatalogoOpcionResponse]
    sucursales: list[CatalogoSucursalResponse]
