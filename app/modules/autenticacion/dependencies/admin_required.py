from fastapi import Depends, HTTPException

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

    return usuario_actual
