from fastapi import APIRouter, Depends
from decimal import Decimal
from pydantic import BaseModel,Field
from app.modules.autenticacion.dependencies.usuario_actual import obtener_usuario_actual
from app.modules.autenticacion.dependencies.admin_required import requerir_admin
from app.core.contexto_empresa import exigir_empresa_id
from app.modules.ventas_inventario.services import posventa_service as s
from app.modules.ventas_inventario.schemas.devolucion.devolucion_response import DevolucionResponse
router=APIRouter(prefix='/api/v1/posventa',tags=['Políticas y devoluciones'])
@router.get('/politica')
def politica(actor=Depends(obtener_usuario_actual)):return s.politica(exigir_empresa_id(actor))
@router.put('/politica')
def guardar(datos:s.Politica,actor=Depends(requerir_admin)):return s.guardar(actor,datos)
class Aceptacion(BaseModel):
    monto:Decimal=Field(gt=0,max_digits=12,decimal_places=2)
@router.post('/devoluciones/{did}/aceptar',response_model=DevolucionResponse)
def aceptar(did:int,datos:Aceptacion,actor=Depends(obtener_usuario_actual)):return s.aceptar(actor,did,datos.monto)
