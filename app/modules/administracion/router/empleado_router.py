from fastapi import APIRouter, Depends
from app.modules.autenticacion.dependencies.admin_required import requerir_admin

from app.modules.administracion.dependencies.empleado_access import (
    requerir_admin_o_encargado,
)
from app.modules.administracion.schemas.empleado.empleado_request import (
    ActivarEmpleadoRequest,
    ActualizarEmpleadoRequest,
    AsignarUsuarioEmpleadoRequest,
    CrearUsuarioEmpleadoRequest,
)
from app.modules.administracion.schemas.empleado.empleado_response import (
    EmpleadoResponse,
    MensajeResponse,
)
from app.modules.administracion.services.empleado_service import (
    asignar_usuario_empleado,
    editar_empleado,
    eliminar_empleado,
    obtener_empleado,
    obtener_empleados,
    reactivar_empleado,
    registrar_usuario_empleado,
)

router = APIRouter(
    prefix="/api/v1",
    tags=["Empleados"],
)


@router.get("/empleados", response_model=list[EmpleadoResponse])
def listar_empleados_endpoint(
    incluir_inactivos: bool = False,
    usuario_actual: dict[str, object] = Depends(requerir_admin_o_encargado),
) -> list[EmpleadoResponse]:
    return obtener_empleados(usuario_actual, incluir_inactivos)


@router.get('/empleados/usuarios-disponibles')
def usuarios_disponibles(actor=Depends(requerir_admin)):
    from app.modules.autenticacion.repositories.perfil_repository import _transaccion
    with _transaccion() as cur:
        cur.execute('''SELECT u.id,u.nombre,u.apellido,u.username FROM usuario u
            WHERE u.empresa_id=%s AND u.activo
            AND NOT EXISTS(SELECT 1 FROM empleado e WHERE e.usuario_id=u.id)
            AND NOT EXISTS(SELECT 1 FROM usuario_rol ur JOIN rol r ON r.id=ur.rol_id
                WHERE ur.usuario_id=u.id AND ur.activo AND r.activo AND r.nombre IN ('ADMINISTRADOR','ADMIN_SAAS'))
            ORDER BY u.nombre,u.id''', (actor['empresa_id'],))
        return [dict(r) for r in cur.fetchall()]


@router.get("/empleados/{empleado_id}", response_model=EmpleadoResponse)
def obtener_empleado_endpoint(
    empleado_id: int,
    usuario_actual: dict[str, object] = Depends(requerir_admin_o_encargado),
) -> EmpleadoResponse:
    return obtener_empleado(empleado_id, usuario_actual)


@router.post("/empleados/asignar-usuario", response_model=EmpleadoResponse)
def asignar_usuario_empleado_endpoint(
    request: AsignarUsuarioEmpleadoRequest,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> EmpleadoResponse:
    return asignar_usuario_empleado(request, usuario_actual)


@router.post("/empleados/crear-usuario", response_model=EmpleadoResponse)
def crear_usuario_empleado_endpoint(
    request: CrearUsuarioEmpleadoRequest,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> EmpleadoResponse:
    return registrar_usuario_empleado(request, usuario_actual)


@router.put("/empleados/{empleado_id}", response_model=EmpleadoResponse)
def actualizar_empleado_endpoint(
    empleado_id: int,
    request: ActualizarEmpleadoRequest,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> EmpleadoResponse:
    return editar_empleado(empleado_id, request, usuario_actual)


@router.patch("/empleados/{empleado_id}/desactivar", response_model=MensajeResponse)
def desactivar_empleado_endpoint(
    empleado_id: int,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> MensajeResponse:
    return eliminar_empleado(empleado_id, usuario_actual)


@router.patch("/empleados/{empleado_id}/activar", response_model=EmpleadoResponse)
def activar_empleado_endpoint(
    empleado_id: int,
    request: ActivarEmpleadoRequest,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> EmpleadoResponse:
    return reactivar_empleado(empleado_id, request, usuario_actual)
