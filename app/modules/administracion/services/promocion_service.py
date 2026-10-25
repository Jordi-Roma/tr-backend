from app.modules.administracion.repositories import catalogo_comercial_repository as comercial
from fastapi import (
    HTTPException,
)
from app.core.contexto_empresa import (
    exigir_empresa_id,
)

from app.modules.administracion.repositories.promocion_repository import (
    listar_promociones,
    obtener_promocion_por_id,
)
from app.modules.administracion.schemas.promocion.promocion_request import (
    PromocionRequest,
)
from app.modules.administracion.schemas.promocion.promocion_response import (
    PromocionResponse,
)


def obtener_promociones(usuario_actual: dict[str, object]) -> list[PromocionResponse]:
    return [PromocionResponse(**promocion) for promocion in listar_promociones(exigir_empresa_id(usuario_actual))]


def obtener_promocion(promocion_id: int, usuario_actual: dict[str, object]) -> PromocionResponse:
    promocion = obtener_promocion_por_id(promocion_id, exigir_empresa_id(usuario_actual))
    if promocion is None:
        raise HTTPException(status_code=404, detail="Promocion no encontrada.")
    return PromocionResponse(**promocion)


def registrar_promocion(request: PromocionRequest, usuario_actual: dict[str, object]) -> PromocionResponse:
    rid = comercial.guardar_promocion(usuario_actual, request.model_dump())
    return obtener_promocion(rid, usuario_actual)


def editar_promocion(promocion_id: int, request: PromocionRequest, usuario_actual: dict[str, object]) -> PromocionResponse:
    rid = comercial.guardar_promocion(usuario_actual, request.model_dump(), promocion_id)
    return obtener_promocion(rid, usuario_actual)


def desactivar_promocion(promocion_id: int, usuario_actual: dict[str, object]) -> PromocionResponse:
    comercial.estado_promocion(usuario_actual, promocion_id, False)
    return obtener_promocion(promocion_id, usuario_actual)


def activar_promocion(promocion_id: int, usuario_actual: dict[str, object]) -> PromocionResponse:
    comercial.estado_promocion(usuario_actual, promocion_id, True)
    return obtener_promocion(promocion_id, usuario_actual)
