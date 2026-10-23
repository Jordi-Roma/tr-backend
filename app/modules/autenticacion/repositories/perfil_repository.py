from contextlib import contextmanager

from fastapi import HTTPException
from psycopg2.errors import UniqueViolation
from psycopg2.extras import RealDictCursor

from app.database.connection import get_connection
from app.core.security import verificar_password


@contextmanager
def _transaccion():
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _usuario(cur, usuario_id, empresa_id, bloquear=False):
    cur.execute("""
        SELECT u.*, c.id AS cliente_id, c.telefono, e.codigo AS empresa_codigo
        FROM usuario u
        LEFT JOIN cliente c ON c.usuario_id=u.id AND c.empresa_id=u.empresa_id AND c.activo=TRUE
        LEFT JOIN empresa e ON e.id=u.empresa_id
        WHERE u.id=%s AND u.empresa_id IS NOT DISTINCT FROM %s AND u.activo=TRUE
    """ + (" FOR UPDATE OF u" if bloquear else ""), (usuario_id, empresa_id))
    fila=cur.fetchone()
    return dict(fila) if fila else None


def _roles(cur, usuario_id):
    cur.execute("""SELECT r.nombre FROM usuario_rol ur JOIN rol r ON r.id=ur.rol_id
        WHERE ur.usuario_id=%s AND ur.activo=TRUE AND r.activo=TRUE ORDER BY r.nombre""", (usuario_id,))
    return [r['nombre'] for r in cur.fetchall()]


def _auditar(cur, usuario_id, empresa_id, accion):
    cur.execute("""INSERT INTO bitacora(usuario_id,empresa_id,accion,modulo,descripcion,resultado)
        VALUES(%s,%s,%s,'PERFIL',%s,'EXITOSO')""", (usuario_id,empresa_id,accion,accion.replace('_',' ').capitalize()))


def invalidar_accesos(cur, usuario_id, empresa_id):
    cur.execute("""UPDATE sesion SET activa=FALSE,fecha_cierre=CURRENT_TIMESTAMP
        WHERE usuario_id=%s AND empresa_id IS NOT DISTINCT FROM %s AND activa=TRUE""", (usuario_id,empresa_id))
    cur.execute("""UPDATE password_reset_token SET usado=TRUE,fecha_uso=CURRENT_TIMESTAMP
        WHERE usuario_id=%s AND usado=FALSE""", (usuario_id,))
    cur.execute('UPDATE token_recuperacion SET utilizado=TRUE WHERE usuario_id=%s', (usuario_id,))


def obtener_perfil_cliente(usuario_id: int, empresa_id: int | None):
    with _transaccion() as cur:
        fila=_usuario(cur,usuario_id,empresa_id)
        if fila:
            fila['roles']=_roles(cur,usuario_id)
        return fila


def actualizar_perfil_cliente(usuario_id,nombre,apellido,telefono,empresa_id,username=None,correo=None,password_actual=None):
    try:
        with _transaccion() as cur:
            fila=_usuario(cur,usuario_id,empresa_id,True)
            if not fila:
                return None
            nuevo_usuario=username if username is not None else fila['username']
            nuevo_correo=correo if correo is not None else fila['correo']
            cambia_acceso=nuevo_usuario!=fila['username'] or nuevo_correo!=fila['correo']
            if cambia_acceso and (not password_actual or not verificar_password(password_actual,fila['password_hash'])):
                raise HTTPException(400,'Confirma tu contraseña actual para cambiar usuario o correo.')
            cur.execute('UPDATE usuario SET nombre=%s,apellido=%s,username=%s,correo=%s WHERE id=%s',
                (nombre,apellido,nuevo_usuario,nuevo_correo,usuario_id))
            if fila['cliente_id']:
                cur.execute('UPDATE cliente SET telefono=%s WHERE id=%s AND empresa_id=%s',(telefono,fila['cliente_id'],empresa_id))
            if cambia_acceso:
                invalidar_accesos(cur,usuario_id,empresa_id)
            _auditar(cur,usuario_id,empresa_id,'ACTUALIZAR_PERFIL')
        resultado=obtener_perfil_cliente(usuario_id,empresa_id)
        if resultado is not None:
            resultado['sesion_revocada']=cambia_acceso
        return resultado
    except UniqueViolation as error:
        raise HTTPException(409,'Ese usuario o correo ya está registrado. Elige otro.') from error


def obtener_password_hash(usuario_id,empresa_id):
    with _transaccion() as cur:
        fila=_usuario(cur,usuario_id,empresa_id)
        return fila['password_hash'] if fila else None


def actualizar_password_hash(usuario_id,password_hash,empresa_id,hash_anterior):
    with _transaccion() as cur:
        fila=_usuario(cur,usuario_id,empresa_id,True)
        if not fila:
            return False
        if fila['password_hash']!=hash_anterior:
            raise HTTPException(409,'La contraseña cambió durante la operación. Vuelve a intentarlo.')
        cur.execute('UPDATE usuario SET password_hash=%s,intentos_fallidos=0,bloqueado_hasta=NULL WHERE id=%s',(password_hash,usuario_id))
        invalidar_accesos(cur,usuario_id,empresa_id)
        _auditar(cur,usuario_id,empresa_id,'CAMBIAR_CONTRASENA')
        return True


def desactivar_cuenta_cliente(usuario_id,empresa_id,password_actual):
    with _transaccion() as cur:
        fila=_usuario(cur,usuario_id,empresa_id,True)
        if not fila or not fila['cliente_id'] or set(_roles(cur,usuario_id))!={'CLIENTE'}:
            raise HTTPException(403,'Esta opción corresponde a las cuentas de cliente.')
        if not verificar_password(password_actual,fila['password_hash']):
            raise HTTPException(400,'La contraseña actual es incorrecta.')
        # La entidad cliente y su historial comercial permanecen intactos.
        cur.execute('UPDATE usuario SET activo=FALSE WHERE id=%s AND empresa_id=%s',(usuario_id,empresa_id))
        invalidar_accesos(cur,usuario_id,empresa_id)
        _auditar(cur,usuario_id,empresa_id,'DESACTIVAR_CUENTA')


def _cliente(cur,usuario_id,empresa_id):
    fila=_usuario(cur,usuario_id,empresa_id,True)
    if not fila or not fila['cliente_id']:
        raise HTTPException(404,'Cliente no encontrado.')
    return fila['cliente_id']


def listar_direcciones_cliente(usuario_id,empresa_id):
    with _transaccion() as cur:
        cliente_id=_cliente(cur,usuario_id,empresa_id)
        cur.execute('SELECT id,ciudad_id,direccion,referencia,es_principal FROM direccion_cliente WHERE cliente_id=%s AND activo=TRUE ORDER BY es_principal DESC,id',(cliente_id,))
        return [dict(r) for r in cur.fetchall()]


def guardar_direccion_cliente(usuario_id,empresa_id,direccion_id,ciudad_id,direccion,referencia,es_principal):
    with _transaccion() as cur:
        cliente_id=_cliente(cur,usuario_id,empresa_id)
        if direccion_id is not None:
            cur.execute('SELECT id FROM direccion_cliente WHERE id=%s AND cliente_id=%s AND activo=TRUE FOR UPDATE',(direccion_id,cliente_id))
            if not cur.fetchone():
                raise HTTPException(404,'Dirección no encontrada.')
        cur.execute('SELECT id FROM ciudad WHERE id=%s AND activo=TRUE',(ciudad_id,))
        if not cur.fetchone():
            raise HTTPException(400,'Selecciona una ciudad disponible.')
        if es_principal:
            cur.execute('UPDATE direccion_cliente SET es_principal=FALSE WHERE cliente_id=%s AND activo=TRUE',(cliente_id,))
        if direccion_id is None:
            cur.execute("""INSERT INTO direccion_cliente(cliente_id,ciudad_id,direccion,referencia,es_principal)
                VALUES(%s,%s,%s,%s,%s) RETURNING id,ciudad_id,direccion,referencia,es_principal""",(cliente_id,ciudad_id,direccion,referencia,es_principal))
        else:
            cur.execute("""UPDATE direccion_cliente SET ciudad_id=%s,direccion=%s,referencia=%s,es_principal=%s
                WHERE id=%s AND cliente_id=%s RETURNING id,ciudad_id,direccion,referencia,es_principal""",(ciudad_id,direccion,referencia,es_principal,direccion_id,cliente_id))
        resultado=dict(cur.fetchone())
        _auditar(cur,usuario_id,empresa_id,'GUARDAR_DIRECCION')
        return resultado


def desactivar_direccion_cliente(usuario_id,direccion_id,empresa_id):
    with _transaccion() as cur:
        cliente_id=_cliente(cur,usuario_id,empresa_id)
        cur.execute('UPDATE direccion_cliente SET activo=FALSE,es_principal=FALSE WHERE id=%s AND cliente_id=%s AND activo=TRUE',(direccion_id,cliente_id))
        if not cur.rowcount:
            return False
        _auditar(cur,usuario_id,empresa_id,'DESACTIVAR_DIRECCION')
        return True
