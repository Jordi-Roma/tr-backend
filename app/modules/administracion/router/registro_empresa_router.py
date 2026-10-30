from fastapi import APIRouter, Request

from app.modules.administracion.repositories.registro_empresa_repository import planes_publicos
from app.modules.administracion.schemas.registro_empresa import RegistroEmpresaRequest
from app.modules.administracion.services import registro_empresa_service as servicio

router = APIRouter(prefix='/api/v1/empresas/registro', tags=['Registro de empresas'])


@router.get('/planes')
def planes():
    return planes_publicos()


@router.post('', status_code=201)
def registrar(datos: RegistroEmpresaRequest, request: Request):
    return servicio.registrar(datos, request.client.host if request.client else 'desconocido')
