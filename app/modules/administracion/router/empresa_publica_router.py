"""Datos minimos de una empresa para enlaces y seleccion publica."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.contexto_empresa import listar_empresas_publicas, resolver_empresa_por_codigo


router = APIRouter(prefix="/api/v1/empresas", tags=["Empresas"])


class EmpresaPublicaResponse(BaseModel):
    id: int
    codigo: str
    nombre: str
    estado: str


@router.get("/publicas", response_model=list[EmpresaPublicaResponse])
def obtener_directorio_publico() -> list[EmpresaPublicaResponse]:
    return [EmpresaPublicaResponse(**empresa) for empresa in listar_empresas_publicas()]


@router.get("/publica/{codigo}", response_model=EmpresaPublicaResponse)
def obtener_empresa_publica(codigo: str) -> EmpresaPublicaResponse:
    empresa = resolver_empresa_por_codigo(codigo)
    if empresa is None or empresa["estado"] not in {"ACTIVA", "SUSPENDIDA"}:
        raise HTTPException(status_code=404, detail="Empresa no encontrada.")
    return EmpresaPublicaResponse(**empresa)
