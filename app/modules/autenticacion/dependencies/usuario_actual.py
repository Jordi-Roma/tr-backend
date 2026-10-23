from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import verificar_token_acceso
from app.modules.autenticacion.repositories.usuario_repository import (
    obtener_usuario_por_id,
)
from app.modules.autenticacion.repositories.sesion_repository import sesion_esta_activa

bearer_scheme = HTTPBearer()


def obtener_usuario_actual(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    request: Request = None,
) -> dict[str, object]:
    token = credentials.credentials

    try:
        payload = verificar_token_acceso(token)
    except ValueError as error:
        raise HTTPException(
            status_code=401,
            detail="Token invalido o expirado.",
        ) from error

    usuario_id_token = payload.get("sub")

    try:
        usuario_id = int(str(usuario_id_token))
    except (TypeError, ValueError) as error:
        raise HTTPException(
            status_code=401,
            detail="Token invalido.",
        ) from error

    sesion_id_token = payload.get("sid")

    try:
        sesion_id = int(str(sesion_id_token))
    except (TypeError, ValueError) as error:
        raise HTTPException(
            status_code=401,
            detail="Token sin sesion asociada.",
        ) from error

    if "empresa_id" not in payload:
        raise HTTPException(status_code=401, detail="Token sin contexto de empresa.")
    empresa_id_token = payload["empresa_id"]
    if empresa_id_token is not None and (
        not isinstance(empresa_id_token, int) or empresa_id_token <= 0
    ):
        raise HTTPException(status_code=401, detail="Contexto de empresa invalido.")
    if not sesion_esta_activa(sesion_id, usuario_id, empresa_id_token):
        raise HTTPException(status_code=401, detail="La sesion cerro o expiro.")

    usuario = obtener_usuario_por_id(usuario_id)

    if usuario is None:
        raise HTTPException(
            status_code=401,
            detail="Usuario no encontrado.",
        )

    if usuario["activo"] is not True:
        raise HTTPException(
            status_code=403,
            detail="Usuario inactivo.",
        )

    empresa_id = usuario.get("empresa_id")
    if empresa_id_token != empresa_id:
        raise HTTPException(status_code=401, detail="Contexto de empresa invalido.")
    if empresa_id is None:
        if "ADMIN_SAAS" not in usuario.get("roles", []):
            raise HTTPException(status_code=403, detail="Cuenta sin empresa asignada.")
    elif usuario.get("empresa_estado") not in {"ACTIVA", "SUSPENDIDA"} or "ADMIN_SAAS" in usuario.get("roles", []):
        raise HTTPException(status_code=403, detail="Empresa no activa o cuenta invalida.")

    if empresa_id is not None and request is not None:
        codigo_solicitado = request.headers.get("X-Empresa-Codigo")
        if codigo_solicitado and codigo_solicitado.strip().lower() != usuario.get("empresa_codigo"):
            raise HTTPException(status_code=403, detail="La empresa indicada no corresponde a la sesión.")
        from app.core.permisos_empresa import es_operacion_nueva
        from app.core.plan_empresa import exigir_operaciones_empresa
        if es_operacion_nueva(request.method, request.url.path):
            exigir_operaciones_empresa(int(empresa_id))

    return usuario
