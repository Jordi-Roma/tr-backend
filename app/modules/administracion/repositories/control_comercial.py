"""Bloqueos compartidos con CU04 para cambios de vínculos y roles comerciales."""
from fastapi import HTTPException
from app.core.plan_empresa import exigir_operaciones_empresa
from app.modules.autenticacion.repositories.administracion_acceso_repository import LOCK_ACCESOS, validar_actor
from app.modules.autenticacion.repositories.perfil_repository import invalidar_accesos


def preparar_escritura(cur, usuario_id, empresa_id, permiso, nueva=True):
    cur.execute('SELECT pg_advisory_xact_lock(%s)', (LOCK_ACCESOS,))
    cur.execute('SELECT id FROM empresa WHERE id=%s FOR UPDATE', (empresa_id,))
    if not cur.fetchone():
        raise HTTPException(404, 'Empresa no encontrada.')
    cur.execute('SELECT id,empresa_id,version_acceso FROM usuario WHERE id=%s', (usuario_id,))
    actor = cur.fetchone()
    if not actor or actor['empresa_id'] != empresa_id:
        raise HTTPException(403, 'Administrador fuera de la empresa.')
    validar_actor(cur, dict(actor), permiso)
    if nueva:
        exigir_operaciones_empresa(empresa_id, cur)


def validar_cuenta_comercial(cur, usuario_id, empresa_id):
    cur.execute('SELECT id FROM usuario WHERE id=%s AND empresa_id=%s AND activo FOR UPDATE', (usuario_id, empresa_id))
    if not cur.fetchone():
        raise HTTPException(404, 'Usuario activo no encontrado en su empresa.')
    cur.execute("""SELECT 1 FROM usuario_rol ur JOIN rol r ON r.id=ur.rol_id
        WHERE ur.usuario_id=%s AND ur.activo AND r.activo
        AND r.nombre IN ('ADMINISTRADOR','ADMIN_SAAS')""", (usuario_id,))
    if cur.fetchone():
        raise HTTPException(409, 'Las cuentas administrativas se gestionan desde Usuarios, no desde estos vínculos.')


def asignar_rol(cur, usuario_id, nombre):
    cur.execute('SELECT id FROM rol WHERE nombre=%s AND activo', (nombre,))
    rol = cur.fetchone()
    if not rol:
        raise HTTPException(409, 'El rol solicitado no está disponible.')
    cur.execute('''INSERT INTO usuario_rol(usuario_id,rol_id,activo) VALUES(%s,%s,TRUE)
        ON CONFLICT(usuario_id,rol_id) DO UPDATE SET activo=TRUE''', (usuario_id, rol['id']))


def retirar_rol_proveedor_sin_vinculo(cur, usuario_id, empresa_id):
    cur.execute('''SELECT 1 FROM proveedor_usuario pu JOIN proveedor p
        ON p.id=pu.proveedor_id AND p.empresa_id=pu.empresa_id
        WHERE pu.usuario_id=%s AND pu.empresa_id=%s AND pu.activo AND p.activo''', (usuario_id, empresa_id))
    if not cur.fetchone():
        cur.execute("""UPDATE usuario_rol ur SET activo=FALSE FROM rol r
            WHERE r.id=ur.rol_id AND r.nombre='PROVEEDOR' AND ur.usuario_id=%s""", (usuario_id,))
    invalidar_accesos(cur, usuario_id, empresa_id)
