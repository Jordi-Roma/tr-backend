from fastapi import APIRouter, Depends

from app.modules.administracion.schemas.promocion.promocion_request import PromocionRequest
from app.modules.administracion.schemas.promocion.promocion_response import PromocionResponse
from app.modules.administracion.services.promocion_service import (
    activar_promocion,
    desactivar_promocion,
    editar_promocion,
    obtener_promocion,
    obtener_promociones,
    registrar_promocion,
)
from app.modules.autenticacion.dependencies.admin_required import requerir_admin

router = APIRouter(
    prefix="/api/v1/promociones",
    tags=["Promociones"],
)


@router.get("", response_model=list[PromocionResponse])
def listar_promociones_endpoint(
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> list[PromocionResponse]:
    return obtener_promociones()


@router.post("", response_model=PromocionResponse)
def crear_promocion_endpoint(
    request: PromocionRequest,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> PromocionResponse:
    return registrar_promocion(request)


@router.get("/{promocion_id}", response_model=PromocionResponse)
def obtener_promocion_endpoint(
    promocion_id: int,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> PromocionResponse:
    return obtener_promocion(promocion_id)


@router.put("/{promocion_id}", response_model=PromocionResponse)
def actualizar_promocion_endpoint(
    promocion_id: int,
    request: PromocionRequest,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> PromocionResponse:
    return editar_promocion(promocion_id, request)


@router.patch("/{promocion_id}/desactivar", response_model=PromocionResponse)
def desactivar_promocion_endpoint(
    promocion_id: int,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> PromocionResponse:
    return desactivar_promocion(promocion_id)


@router.patch("/{promocion_id}/activar", response_model=PromocionResponse)
def activar_promocion_endpoint(
    promocion_id: int,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> PromocionResponse:
    return activar_promocion(promocion_id)
