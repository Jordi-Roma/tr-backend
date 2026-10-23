from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.contexto_empresa import exigir_empresa_id
from app.modules.autenticacion.dependencies.admin_required import requerir_admin, requerir_admin_saas
from app.modules.autenticacion.repositories.bitacora_repository import (
    contar_bitacora,
    listar_bitacora,
    obtener_registro_bitacora,
)
from app.modules.autenticacion.schemas.bitacora.bitacora_schemas import (
    BitacoraDetalleResponse,
    BitacoraListResponse,
    construir_detalle,
)

router = APIRouter(
    prefix="/api/v1",
    tags=["Bitacora"],
)


@router.get("/bitacora", response_model=BitacoraListResponse)
def listar_bitacora_endpoint(
    usuario_id: int | None = Query(default=None),
    accion: str | None = Query(default=None),
    modulo: str | None = Query(default=None),
    resultado: str | None = Query(default=None),
    fecha_desde: str | None = Query(default=None),
    fecha_hasta: str | None = Query(default=None),
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=50, ge=1, le=200),
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> BitacoraListResponse:
    empresa_id = exigir_empresa_id(usuario_actual)
    registros = listar_bitacora(
        empresa_id=empresa_id,
        usuario_id=usuario_id,
        accion=accion,
        modulo=modulo,
        resultado=resultado,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        pagina=pagina,
        por_pagina=por_pagina,
    )
    total = contar_bitacora(
        empresa_id=empresa_id,
        usuario_id=usuario_id,
        accion=accion,
        modulo=modulo,
        resultado=resultado,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )
    return BitacoraListResponse.construir(
        registros=registros,
        total=total,
        pagina=pagina,
        por_pagina=por_pagina,
    )


@router.get("/bitacora/{registro_id}", response_model=BitacoraDetalleResponse)
def obtener_bitacora_endpoint(
    registro_id: int,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> BitacoraDetalleResponse:
    registro = obtener_registro_bitacora(registro_id, exigir_empresa_id(usuario_actual))

    if registro is None:
        raise HTTPException(status_code=404, detail="Registro de bitacora no encontrado.")

    return construir_detalle(registro)


@router.get("/saas/bitacora", response_model=BitacoraListResponse)
def listar_bitacora_plataforma(
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=50, ge=1, le=200),
    usuario_actual: dict[str, object] = Depends(requerir_admin_saas),
) -> BitacoraListResponse:
    registros = listar_bitacora(empresa_id=None, pagina=pagina, por_pagina=por_pagina)
    total = contar_bitacora(empresa_id=None)
    return BitacoraListResponse.construir(registros, total, pagina, por_pagina)


@router.get("/saas/bitacora/{registro_id}", response_model=BitacoraDetalleResponse)
def obtener_bitacora_plataforma(
    registro_id: int,
    usuario_actual: dict[str, object] = Depends(requerir_admin_saas),
) -> BitacoraDetalleResponse:
    registro = obtener_registro_bitacora(registro_id, None)
    if registro is None:
        raise HTTPException(status_code=404, detail="Registro de bitacora no encontrado.")
    return construir_detalle(registro)
