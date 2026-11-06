"""CU25: administración privada de respaldos; nunca se sirven desde /static."""

from uuid import UUID
from datetime import date
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.core.contexto_empresa import exigir_empresa_id
from app.modules.autenticacion.dependencies.admin_required import requerir_admin, requerir_admin_o_saas, requerir_admin_saas
from app.modules.administracion.services import respaldo_service as servicio

router = APIRouter(prefix="/api/v1/saas/respaldos", tags=["Respaldos SaaS"])
router_empresa = APIRouter(prefix="/api/v1/respaldos", tags=["Respaldos de empresa"])


class CrearRespaldo(BaseModel):
    empresa_id: int | None = Field(default=None, gt=0)


class RestaurarRespaldo(BaseModel):
    confirmacion: str


class ProgramarRespaldo(BaseModel):
    activa: bool = True
    fecha_inicio: date
    hora_local: str = Field(default="02:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    zona_horaria: str = Field(default="America/La_Paz", min_length=1, max_length=80)


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


@router_empresa.get("")
def listar_empresa(actor: dict = Depends(requerir_admin)):
    return servicio.listar_respaldos(exigir_empresa_id(actor))


@router_empresa.post("", status_code=201)
def crear_empresa(actor: dict = Depends(requerir_admin)):
    return servicio.crear_respaldo(int(actor["id"]), exigir_empresa_id(actor), "MANUAL")


@router_empresa.get("/programacion")
def ver_programacion(actor: dict = Depends(requerir_admin)):
    return servicio.obtener_programacion(exigir_empresa_id(actor))


@router_empresa.put("/programacion")
def editar_programacion(request: ProgramarRespaldo, actor: dict = Depends(requerir_admin)):
    return servicio.guardar_programacion(exigir_empresa_id(actor), int(actor["id"]), request.activa,
                                         request.fecha_inicio, request.hora_local, request.zona_horaria)


@router_empresa.post("/{respaldo_id}/previsualizar")
def previsualizar_empresa(respaldo_id: UUID, actor: dict = Depends(requerir_admin_o_saas)):
    empresa_id = exigir_empresa_id(actor)
    return servicio.previsualizar_restauracion(respaldo_id, int(actor["id"]), empresa_id)


@router_empresa.post("/{respaldo_id}/restaurar")
def restaurar_empresa(respaldo_id: UUID, request: RestaurarRespaldo, actor: dict = Depends(requerir_admin_o_saas)):
    empresa_id = exigir_empresa_id(actor)
    return servicio.restaurar_respaldo(respaldo_id, int(actor["id"]), request.confirmacion, empresa_id)


@router_empresa.delete("/{respaldo_id}")
def eliminar_empresa(respaldo_id: UUID, actor: dict = Depends(requerir_admin_o_saas)):
    return servicio.eliminar_respaldo(respaldo_id, int(actor["id"]), exigir_empresa_id(actor))
