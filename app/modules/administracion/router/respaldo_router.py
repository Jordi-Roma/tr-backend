"""CU25: administración privada de respaldos; nunca se sirven desde /static."""

from uuid import UUID
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.modules.autenticacion.dependencies.admin_required import requerir_admin_saas
from app.modules.administracion.services import respaldo_service as servicio

router = APIRouter(prefix="/api/v1/saas/respaldos", tags=["Respaldos SaaS"])


class CrearRespaldo(BaseModel):
    empresa_id: int | None = Field(default=None, gt=0)


class RestaurarRespaldo(BaseModel):
    confirmacion: str


@router.get("")
def listar(_: dict = Depends(requerir_admin_saas)):
    return servicio.listar_respaldos()


@router.post("", status_code=201)
def crear(request: CrearRespaldo, actor: dict = Depends(requerir_admin_saas)):
    return servicio.crear_respaldo(int(actor["id"]), request.empresa_id)


@router.post("/purgar-vencidos")
def purgar(actor: dict = Depends(requerir_admin_saas)):
    return servicio.purgar_vencidos(int(actor["id"]))


@router.post("/{respaldo_id}/previsualizar")
def previsualizar(respaldo_id: UUID, actor: dict = Depends(requerir_admin_saas)):
    return servicio.previsualizar_restauracion(respaldo_id, int(actor["id"]))


@router.post("/{respaldo_id}/restaurar")
def restaurar(respaldo_id: UUID, request: RestaurarRespaldo, actor: dict = Depends(requerir_admin_saas)):
    return servicio.restaurar_respaldo(respaldo_id, int(actor["id"]), request.confirmacion)


@router.delete("/{respaldo_id}")
def eliminar(respaldo_id: UUID, actor: dict = Depends(requerir_admin_saas)):
    return servicio.eliminar_respaldo(respaldo_id, int(actor["id"]))
