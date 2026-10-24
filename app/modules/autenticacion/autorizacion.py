"""Permisos configurables de CU04/CU05; el resto conserva su política vigente."""

from fastapi import Depends, HTTPException
from app.modules.autenticacion.dependencies.admin_required import requerir_admin_o_saas
from app.modules.autenticacion.repositories.perfil_repository import _transaccion

ROLES_BASE = frozenset(
    {
        "ADMIN_SAAS",
        "ADMINISTRADOR",
        "ENCARGADO_SUCURSAL",
        "CAJERO",
        "PROVEEDOR",
        "CLIENTE",
    }
)
CONFIGURABLES = {
    "usuarios:ver": "Consultar usuarios",
    "usuarios:crear": "Crear usuarios",
    "usuarios:editar": "Editar usuarios",
    "usuarios:desactivar": "Desactivar usuarios",
    "usuarios:activar": "Reactivar usuarios",
    "roles:ver": "Consultar roles y permisos",
    "roles:asignar": "Asignar roles comerciales",
    "roles:retirar": "Retirar roles comerciales",
    "bitacora:ver": "Consultar bitácora de empresa",
}


def permisos_cursor(cur, usuario_id):
    cur.execute(
        """SELECT DISTINCT p.accion FROM usuario_rol ur
        JOIN rol r ON r.id=ur.rol_id AND r.activo
        JOIN rol_permiso rp ON rp.rol_id=r.id AND rp.activo
        JOIN permiso p ON p.id=rp.permiso_id AND p.activo
        WHERE ur.usuario_id=%s AND ur.activo ORDER BY p.accion""",
        (usuario_id,),
    )
    return [r["accion"] for r in cur.fetchall()]


def capacidades(usuario):
    if usuario.get("empresa_id") is None and "ADMIN_SAAS" in usuario.get("roles", []):
        return list(CONFIGURABLES)
    with _transaccion() as cur:
        return permisos_cursor(cur, int(usuario["id"]))


def exigir_permiso(accion):
    def comprobar(usuario=Depends(requerir_admin_o_saas)):
        if usuario.get("empresa_id") is not None and accion not in capacidades(usuario):
            from app.modules.autenticacion.repositories.bitacora_repository import (
                registrar_bitacora,
            )

            registrar_bitacora(
                usuario["id"],
                "PERMISO_DENEGADO",
                "CONTROL_ACCESO",
                "BLOQUEADO",
                descripcion="Permiso requerido: " + accion,
                empresa_id=usuario.get("empresa_id"),
            )
            raise HTTPException(403, "No tiene el permiso necesario: " + accion)
        return usuario

    return comprobar
