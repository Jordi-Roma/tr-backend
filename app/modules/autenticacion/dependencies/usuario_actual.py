from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import verificar_token_acceso
from app.modules.autenticacion.repositories.usuario_repository import (
    obtener_usuario_por_id,
)
from app.modules.autenticacion.repositories.sesion_repository import sesion_esta_activa

bearer_scheme = HTTPBearer()


def obtener_usuario_actual(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
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

    if not sesion_esta_activa(sesion_id, usuario_id):
        raise HTTPException(
            status_code=401,
            detail="La sesion cerro o expiro.",
        )

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

    return usuario
