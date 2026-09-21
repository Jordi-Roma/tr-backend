from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field

from app.modules.catalogo.schemas.catalogo_publico.catalogo_publico_response import CatalogoPrendaItemResponse
from app.modules.catalogo.repositories.catalogo_publico_repository import obtener_prenda_catalogo
from app.modules.autenticacion.dependencies.usuario_actual import obtener_usuario_actual
from app.modules.inteligencia.repositories import recomendacion_repository as repo
from app.modules.inteligencia.schemas.recomendacion.recomendacion_schemas import (
    PreferenciasIAResponse,
    RecomendacionPrendaResponse,
)
from app.modules.inteligencia.services.recomendacion_service import (
    cliente_id_obligatorio,
    indexar_productos,
    recomendar_desde_producto,
    recomendar_para_cliente,
)

router = APIRouter(prefix='/api/v1/recomendaciones', tags=['Recomendaciones IA'])


class PreferenciasIA(PreferenciasIAResponse):
    categorias: list[int] = Field(default_factory=list, max_length=10)


@router.get('/producto/{producto_id}', response_model=list[RecomendacionPrendaResponse])
def recomendaciones_producto(producto_id: int, sucursal_id: int | None = Query(None, gt=0),
                             talla_id: int | None = Query(None, gt=0),
                             limite: int = Query(6, ge=1, le=12)):
    return recomendar_desde_producto(producto_id, sucursal_id, talla_id, limite)


@router.get('/para-mi', response_model=list[RecomendacionPrendaResponse])
def recomendaciones_para_mi(limite: int = Query(8, ge=1, le=12), usuario: dict = Depends(obtener_usuario_actual)):
    return recomendar_para_cliente(cliente_id_obligatorio(usuario), limite)


@router.get('/preferencias', response_model=PreferenciasIA)
def leer_preferencias(usuario: dict = Depends(obtener_usuario_actual)):
    return repo.obtener_preferencias(cliente_id_obligatorio(usuario))


@router.put('/preferencias', response_model=PreferenciasIA)
def actualizar_preferencias(preferencias: PreferenciasIA, usuario: dict = Depends(obtener_usuario_actual)):
    if any(id_ <= 0 for id_ in preferencias.categorias) or not repo.categorias_validas(preferencias.categorias):
        raise HTTPException(status_code=422, detail='Categoría no válida.')
    return repo.guardar_preferencias(cliente_id_obligatorio(usuario),
                                    sorted(set(preferencias.categorias)), preferencias.usar_historial)


def _favoritos_items(cliente_id: int) -> list[dict]:
    return [item for producto_id in repo.listar_favoritos(cliente_id)
            if (item := obtener_prenda_catalogo(producto_id)) is not None]


@router.get('/favoritos', response_model=list[CatalogoPrendaItemResponse])
def favoritos(usuario: dict = Depends(obtener_usuario_actual)):
    return _favoritos_items(cliente_id_obligatorio(usuario))


@router.put('/favoritos/{producto_id}', response_model=list[CatalogoPrendaItemResponse])
def agregar_favorito(producto_id: int, usuario: dict = Depends(obtener_usuario_actual)):
    cliente_id = cliente_id_obligatorio(usuario)
    repo.guardar_favorito(cliente_id, producto_id)
    return _favoritos_items(cliente_id)


@router.delete('/favoritos/{producto_id}', response_model=list[CatalogoPrendaItemResponse])
def eliminar_favorito(producto_id: int, usuario: dict = Depends(obtener_usuario_actual)):
    cliente_id = cliente_id_obligatorio(usuario)
    repo.quitar_favorito(cliente_id, producto_id)
    return _favoritos_items(cliente_id)


@router.post('/indexar')
def indexar(usuario: dict = Depends(obtener_usuario_actual)):
    if 'ADMINISTRADOR' not in usuario.get('roles', []):
        raise HTTPException(status_code=403, detail='Solo administradores pueden indexar productos.')
    return indexar_productos()
