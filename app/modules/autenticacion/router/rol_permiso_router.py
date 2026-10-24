from fastapi import APIRouter, Depends, HTTPException
from typing import Literal
from app.modules.autenticacion.autorizacion import exigir_permiso
from app.modules.autenticacion.dependencies.admin_required import requerir_admin_saas
from app.modules.autenticacion.schemas.usuario_admin.usuario_admin_request import (
    PlantillaRequest,
)
from app.modules.autenticacion.repositories import (
    administracion_acceso_repository as acceso,
)

router = APIRouter(prefix="/api/v1", tags=["Roles y permisos"])


@router.get("/acceso/catalogos")
def catalogos(
    estado: Literal["ACTIVOS", "INACTIVOS", "TODOS"] = "ACTIVOS",
    actor=Depends(exigir_permiso("roles:ver")),
):
    return acceso.catalogos(actor, estado)


@router.get("/roles")
def roles(
    estado: Literal["ACTIVOS", "INACTIVOS", "TODOS"] = "ACTIVOS",
    actor=Depends(exigir_permiso("roles:ver")),
):
    return acceso.catalogos(actor, estado)["roles"]


@router.get("/permisos")
def permisos(actor=Depends(exigir_permiso("roles:ver"))):
    return acceso.catalogos(actor, "TODOS")["permisos"]


@router.get("/roles/{rid}/permisos")
def detalle(rid: int, actor=Depends(exigir_permiso("roles:ver"))):
    c = acceso.catalogos(actor, "TODOS")
    r = next((r for r in c["roles"] if r["id"] == rid), None)
    if r is None:
        raise HTTPException(404, "Rol no encontrado.")
    return {"rol": r, "permiso_ids": r["permiso_ids"]}


@router.put("/roles/{rid}")
@router.put("/roles/{rid}/permisos")
def editar(rid: int, datos: PlantillaRequest, actor=Depends(requerir_admin_saas)):
    return acceso.actualizar_plantilla(actor, rid, datos)


@router.patch("/roles/{rid}/activar")
def activar(
    rid: int, confirmar_global: bool = False, actor=Depends(requerir_admin_saas)
):
    return acceso.actualizar_plantilla(
        actor, rid, PlantillaRequest(activo=True, confirmar_global=confirmar_global)
    )


@router.patch("/roles/{rid}/desactivar")
def desactivar(
    rid: int, confirmar_global: bool = False, actor=Depends(requerir_admin_saas)
):
    return acceso.actualizar_plantilla(
        actor, rid, PlantillaRequest(activo=False, confirmar_global=confirmar_global)
    )


@router.post("/roles")
@router.post("/permisos")
@router.patch("/permisos/{pid}/activar")
@router.patch("/permisos/{pid}/desactivar")
@router.post("/roles/{rid}/permisos/{pid}")
@router.patch("/roles/{rid}/permisos/{pid}/activar")
@router.patch("/roles/{rid}/permisos/{pid}/desactivar")
def protegido(actor=Depends(requerir_admin_saas)):
    raise HTTPException(
        409,
        "El catálogo está protegido. Configura únicamente las capacidades señaladas en Roles y permisos.",
    )
