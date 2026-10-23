from fastapi import Depends, HTTPException

from app.core.contexto_empresa import exigir_empresa_id
from app.modules.autenticacion.dependencies.usuario_actual import obtener_usuario_actual


def requerir_admin(
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> dict[str, object]:
    roles = [str(rol) for rol in usuario_actual.get("roles", [])]

    if "ADMINISTRADOR" not in roles:
        raise HTTPException(
            status_code=403,
            detail="No tiene permisos para realizar esta accion.",
        )

    exigir_empresa_id(usuario_actual)

    return usuario_actual


def requerir_admin_saas(
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> dict[str, object]:
    if usuario_actual.get("empresa_id") is not None or "ADMIN_SAAS" not in usuario_actual.get("roles", []):
        raise HTTPException(status_code=403, detail="Acceso exclusivo del administrador SaaS.")
    return usuario_actual


def requerir_admin_o_saas(
    usuario_actual: dict[str, object] = Depends(obtener_usuario_actual),
) -> dict[str, object]:
    roles = usuario_actual.get("roles", [])
    if usuario_actual.get("empresa_id") is None:
        return requerir_admin_saas(usuario_actual)
    if "ADMINISTRADOR" not in roles:
        raise HTTPException(status_code=403, detail="No tiene permisos para realizar esta accion.")
    return usuario_actual
