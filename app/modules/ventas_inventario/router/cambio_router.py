from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from app.modules.autenticacion.dependencies.usuario_actual import obtener_usuario_actual
from app.modules.autenticacion.repositories.perfil_repository import _transaccion
from app.modules.ventas_inventario.services import cambio_service as s

router = APIRouter(prefix='/api/v1/posventa/cambios', tags=['Cambios de prendas'])

@router.get('/elegibles')
def elegibles(actor=Depends(obtener_usuario_actual)):
    return s.elegibles(actor)

@router.get('')
def listar(gestion: bool=False, actor=Depends(obtener_usuario_actual)):
    return s.listar(actor,gestion)

@router.post('',status_code=201)
def solicitar(datos:s.Solicitud,actor=Depends(obtener_usuario_actual)):
    return s.solicitar(actor,datos)

@router.patch('/{cid}/revision')
def revisar(cid:int,datos:s.Revision,actor=Depends(obtener_usuario_actual)):
    return s.revisar(actor,cid,datos)

@router.get('/{cid}/opciones')
def opciones(cid:int,actor=Depends(obtener_usuario_actual)):
    return s.opciones(actor,cid)

@router.post('/{cid}/cotizar')
def cotizar(cid:int,datos:s.Cotizacion,actor=Depends(obtener_usuario_actual)):
    return s.cotizar(actor,cid,datos)

@router.post('/{cid}/aceptar')
def aceptar(cid:int,datos:s.Aceptacion,actor=Depends(obtener_usuario_actual)):
    return s.aceptar(actor,cid,datos)

@router.post('/{cid}/cancelar')
def cancelar(cid:int,datos:s.Version,actor=Depends(obtener_usuario_actual)):
    return s.cancelar(actor,cid,datos.version)

@router.post('/{cid}/devolucion')
def convertir(cid:int,datos:s.Version,actor=Depends(obtener_usuario_actual)):
    return s.convertir(actor,cid,datos.version)

class Pago(s.Version):
    medio:str=Field(pattern='^(STRIPE|QR_BCP)$')

@router.post('/{cid}/pago')
def pago(cid:int,datos:Pago,actor=Depends(obtener_usuario_actual)):
    return s.crear_pago(actor,cid,datos.version,datos.medio)

@router.post('/{cid}/reintegro')
def reintegro(cid:int,actor=Depends(obtener_usuario_actual)):
    return s.reembolsar(actor,cid)

class Efectivo(BaseModel):
    referencia:str=Field(min_length=3,max_length=255)

    @field_validator('referencia')
    @classmethod
    def referencia_valida(cls, v):
        if len(v.strip())<3:raise ValueError('Registra la referencia del recibo de caja.')
        return v.strip()

@router.post('/{cid}/reintegro-efectivo')
def efectivo(cid:int,datos:Efectivo,actor=Depends(obtener_usuario_actual)):
    from app.modules.ventas_inventario.repositories.devolucion_repository import registrar_reembolso_manual
    with _transaccion() as cur:
        c=s._acceso(cur,actor,cid,True)
        if c['estado']=='LISTO':return s._detalle(cur,cid,c['empresa_id'])
        if c['estado']!='ESPERA_REINTEGRO':raise HTTPException(409,'No hay reintegro de cambio pendiente.')
    if c['estado_devolucion']!='REEMBOLSADA':
        registrar_reembolso_manual(cid,actor['id'],'EFECTIVO',datos.referencia,None,c['empresa_id'])
    with _transaccion() as cur:
        c=s._acceso(cur,actor,cid,True)
        if c['estado_devolucion']=='REEMBOLSADA' and c['estado']=='ESPERA_REINTEGRO':s._actualizar(cur,cid,'LISTO')
        return s._detalle(cur,cid,c['empresa_id'])

@router.post('/{cid}/completar')
def completar(cid:int,datos:s.Entrega,actor=Depends(obtener_usuario_actual)):
    return s.completar(actor,cid,datos)
