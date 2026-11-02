from fastapi import APIRouter, Depends
from app.core.contexto_empresa import exigir_empresa_publica, exigir_empresa_id
from app.modules.autenticacion.dependencies.admin_required import requerir_admin
from app.modules.autenticacion.dependencies.usuario_actual import obtener_usuario_actual
from app.modules.autenticacion.repositories.perfil_repository import _transaccion
from app.modules.reservas.services import mayorista_service as servicio
from app.modules.reservas.schemas.carrito.carrito_response import CarritoResponse

router = APIRouter(prefix='/api/v1/mayorista', tags=['Compra por mayor'])

@router.get('/productos/{pid}')
def opciones(pid: int, sucursal_id: int, empresa: int = Depends(exigir_empresa_publica)):
    with _transaccion() as cur:
        return servicio.opciones(cur,empresa,pid,sucursal_id)

@router.get('/productos/{pid}/configuracion')
def configuracion(pid: int, actor=Depends(requerir_admin)):
    with _transaccion() as cur:
        return servicio.configuracion(cur,exigir_empresa_id(actor),pid)

@router.put('/productos/{pid}/configuracion')
def configurar(pid: int, datos: servicio.PrecioRequest, actor=Depends(requerir_admin)):
    return servicio.guardar(actor,pid,datos)

@router.post('/paquetes', response_model=CarritoResponse)
def agregar(datos: servicio.PaqueteRequest, actor=Depends(obtener_usuario_actual)):
    return CarritoResponse(**servicio.agregar(actor,datos))
