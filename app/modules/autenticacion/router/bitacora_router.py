from datetime import datetime, time, date
from zoneinfo import ZoneInfo
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.contexto_empresa import exigir_empresa_id
from app.modules.autenticacion.autorizacion import exigir_permiso
from app.modules.autenticacion.dependencies.admin_required import requerir_admin_saas
from app.modules.autenticacion.repositories.bitacora_repository import (
    consultar_bitacora,
    obtener_registro_bitacora,
    opciones_bitacora,
)
from app.modules.autenticacion.schemas.bitacora.bitacora_schemas import (
    BitacoraListResponse,
    BitacoraDetalleResponse,
    construir_detalle,
)

router = APIRouter(prefix="/api/v1", tags=["Bitacora"])


def filtro(
    usuario_id: int | None = Query(None, gt=0),
    accion: str | None = Query(None, max_length=80),
    modulo: str | None = Query(None, max_length=80),
    resultado: Literal["EXITOSO", "FALLIDO", "BLOQUEADO"] | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(50, ge=1, le=200),
):
    def fecha(valor, fin=False):
        if not valor:
            return None
        try:
            if len(valor) == 10:
                d = date.fromisoformat(valor)
                return datetime.combine(
                    d, time.max if fin else time.min, tzinfo=ZoneInfo("America/La_Paz")
                )
            d = datetime.fromisoformat(valor.replace("Z", "+00:00"))
            return (
                d.replace(tzinfo=ZoneInfo("America/La_Paz")) if d.tzinfo is None else d
            )
        except (ValueError, TypeError):
            raise HTTPException(422, "Fecha inválida. Usa el formato ISO.")

    desde, hasta = fecha(fecha_desde), fecha(fecha_hasta, True)
    if desde and hasta and desde > hasta:
        raise HTTPException(422, "La fecha inicial no puede superar la final.")
    return dict(
        usuario_id=usuario_id,
        accion=accion,
        modulo=modulo,
        resultado=resultado,
        fecha_desde=desde,
        fecha_hasta=hasta,
        pagina=pagina,
        por_pagina=por_pagina,
    )


def consultar(empresa, filtros):
    registros, total = consultar_bitacora(empresa, **filtros)
    return BitacoraListResponse.construir(
        registros, total, filtros["pagina"], filtros["por_pagina"]
    )


def detalle(empresa, rid):
    registro = obtener_registro_bitacora(rid, empresa)
    if registro is None:
        raise HTTPException(404, "Registro de bitácora no encontrado.")
    return construir_detalle(registro)


@router.get("/bitacora", response_model=BitacoraListResponse)
def listar(filtros=Depends(filtro), actor=Depends(exigir_permiso("bitacora:ver"))):
    return consultar(exigir_empresa_id(actor), filtros)


@router.get("/bitacora/opciones")
def opciones(actor=Depends(exigir_permiso("bitacora:ver"))):
    return opciones_bitacora(exigir_empresa_id(actor))


@router.get("/bitacora/{rid}", response_model=BitacoraDetalleResponse)
def registro(rid: int, actor=Depends(exigir_permiso("bitacora:ver"))):
    return detalle(exigir_empresa_id(actor), rid)


@router.get("/saas/bitacora", response_model=BitacoraListResponse)
def listar_saas(filtros=Depends(filtro), actor=Depends(requerir_admin_saas)):
    return consultar(None, filtros)


@router.get("/saas/bitacora/opciones")
def opciones_saas(actor=Depends(requerir_admin_saas)):
    return opciones_bitacora(None)


@router.get("/saas/bitacora/{rid}", response_model=BitacoraDetalleResponse)
def registro_saas(rid: int, actor=Depends(requerir_admin_saas)):
    return detalle(None, rid)
