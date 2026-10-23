from fastapi import HTTPException

from app.core.security import hashear_password, verificar_password
from app.modules.autenticacion.repositories import perfil_repository as repo
from app.modules.autenticacion.schemas.perfil.perfil_request import (
    ActualizarDireccionRequest, ActualizarPerfilRequest, CambiarPasswordRequest,
    CrearDireccionRequest, DesactivarCuentaRequest,
)
from app.modules.autenticacion.schemas.perfil.perfil_response import (
    DireccionResponse, ListaDireccionesResponse, MensajeResponse, PerfilResponse,
)


def obtener_perfil(usuario_actual: dict[str, object]) -> PerfilResponse:
    perfil=repo.obtener_perfil_cliente(int(usuario_actual["id"]),usuario_actual["empresa_id"])
    if perfil is None:
        raise HTTPException(404,"Perfil no encontrado.")
    return PerfilResponse(**perfil)


def actualizar_perfil(usuario_actual: dict[str, object], request: ActualizarPerfilRequest,
    direccion_ip: str | None = None,user_agent: str | None = None) -> PerfilResponse:
    perfil=repo.actualizar_perfil_cliente(int(usuario_actual["id"]),request.nombre,request.apellido,
        request.telefono,usuario_actual["empresa_id"],request.username,request.correo,request.password_actual)
    if perfil is None:
        raise HTTPException(404,"Perfil no encontrado.")
    return PerfilResponse(**perfil)


def cambiar_password(usuario_actual: dict[str, object],request: CambiarPasswordRequest,
    direccion_ip: str | None = None,user_agent: str | None = None) -> MensajeResponse:
    if request.password_nuevo!=request.confirmar_password_nuevo:
        raise HTTPException(400,"Las contraseñas nuevas no coinciden.")
    uid=int(usuario_actual["id"]); eid=usuario_actual["empresa_id"]
    anterior=repo.obtener_password_hash(uid,eid)
    if anterior is None:
        raise HTTPException(404,"Usuario no encontrado.")
    if not verificar_password(request.password_actual,anterior):
        raise HTTPException(400,"La contraseña actual es incorrecta.")
    try:
        nuevo=hashear_password(request.password_nuevo)
    except ValueError as error:
        raise HTTPException(400,str(error)) from error
    if not repo.actualizar_password_hash(uid,nuevo,eid,anterior):
        raise HTTPException(404,"Usuario no encontrado.")
    return MensajeResponse(mensaje="Contraseña actualizada. Inicia sesión nuevamente.")


def desactivar_cuenta(usuario_actual: dict[str, object],request: DesactivarCuentaRequest) -> MensajeResponse:
    if request.confirmacion!="DESACTIVAR MI CUENTA":
        raise HTTPException(400,"Confirma explícitamente la desactivación de tu cuenta.")
    if usuario_actual["empresa_id"] is None or set(usuario_actual["roles"])!={"CLIENTE"}:
        raise HTTPException(403,"Esta opción corresponde a las cuentas de cliente.")
    repo.desactivar_cuenta_cliente(int(usuario_actual["id"]),int(usuario_actual["empresa_id"]),request.password_actual)
    return MensajeResponse(mensaje="Cuenta desactivada. Tu historial se conserva.")


def listar_direcciones(usuario_actual: dict[str, object]) -> ListaDireccionesResponse:
    filas=repo.listar_direcciones_cliente(int(usuario_actual["id"]),usuario_actual["empresa_id"])
    return ListaDireccionesResponse(direcciones=[DireccionResponse(**f) for f in filas])


def _guardar_direccion(usuario_actual,request,direccion_id):
    fila=repo.guardar_direccion_cliente(int(usuario_actual["id"]),usuario_actual["empresa_id"],
        direccion_id,request.ciudad_id,request.direccion,request.referencia,request.es_principal)
    return DireccionResponse(**fila)


def crear_direccion(usuario_actual: dict[str, object],request: CrearDireccionRequest) -> DireccionResponse:
    return _guardar_direccion(usuario_actual,request,None)


def actualizar_direccion(usuario_actual: dict[str, object],direccion_id: int,request: ActualizarDireccionRequest) -> DireccionResponse:
    return _guardar_direccion(usuario_actual,request,direccion_id)


def desactivar_direccion(usuario_actual: dict[str, object],direccion_id: int) -> MensajeResponse:
    if not repo.desactivar_direccion_cliente(int(usuario_actual["id"]),direccion_id,usuario_actual["empresa_id"]):
        raise HTTPException(404,"Dirección no encontrada.")
    return MensajeResponse(mensaje="Dirección desactivada correctamente.")
