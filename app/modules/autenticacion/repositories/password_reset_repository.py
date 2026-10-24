import hmac

from app.modules.autenticacion.repositories.perfil_repository import _transaccion, invalidar_accesos


def obtener_usuario_por_identificador(identificador: str, empresa_id: int | None):
    with _transaccion() as cur:
        cur.execute("""
            SELECT u.id,u.nombre,u.apellido,u.username,u.correo,u.activo,u.version_acceso
            FROM usuario u
            WHERE u.empresa_id IS NOT DISTINCT FROM %s
              AND (LOWER(u.correo)=LOWER(%s) OR u.username=LOWER(%s))
              AND (%s::bigint IS NOT NULL OR EXISTS (
                SELECT 1 FROM usuario_rol ur JOIN rol r ON r.id=ur.rol_id
                WHERE ur.usuario_id=u.id AND ur.activo=TRUE AND r.activo=TRUE AND r.nombre='ADMIN_SAAS'))
            LIMIT 1
        """,(empresa_id,identificador,identificador,empresa_id))
        fila=cur.fetchone()
        return dict(fila) if fila else None


def guardar_token_reset(usuario_id: int,token_hash: str,minutos_expiracion: int,empresa_id: int | None,identidad_verificada: dict | None = None) -> bool:
    with _transaccion() as cur:
        cur.execute('SELECT id,username,correo,version_acceso FROM usuario WHERE id=%s AND empresa_id IS NOT DISTINCT FROM %s AND activo=TRUE FOR UPDATE',(usuario_id,empresa_id))
        actual = cur.fetchone()
        if not actual or (identidad_verificada is not None and any(
            actual[campo] != identidad_verificada[campo] for campo in ('username','correo')
        )) or (actual and identidad_verificada is not None and actual['version_acceso']!=identidad_verificada.get('version_acceso',0)):
            return False
        cur.execute("SELECT id FROM password_reset_token WHERE usuario_id=%s AND fecha_creacion>CURRENT_TIMESTAMP-INTERVAL '60 seconds' LIMIT 1",(usuario_id,))
        if cur.fetchone():
            return False
        cur.execute('UPDATE password_reset_token SET usado=TRUE,fecha_uso=CURRENT_TIMESTAMP WHERE usuario_id=%s AND usado=FALSE',(usuario_id,))
        cur.execute("""INSERT INTO password_reset_token(usuario_id,token_hash,fecha_expiracion)
            VALUES(%s,%s,CURRENT_TIMESTAMP+(%s * INTERVAL '1 minute'))""",(usuario_id,token_hash,minutos_expiracion))
        return True


def consumir_token_reset(usuario_id: int,token_hash: str,password_hash: str,empresa_id: int | None) -> bool:
    with _transaccion() as cur:
        cur.execute('SELECT id FROM usuario WHERE id=%s AND empresa_id IS NOT DISTINCT FROM %s AND activo=TRUE FOR UPDATE',(usuario_id,empresa_id))
        if not cur.fetchone():
            return False
        cur.execute("""SELECT id,token_hash,intentos FROM password_reset_token WHERE usuario_id=%s
            AND usado=FALSE AND fecha_expiracion>CURRENT_TIMESTAMP ORDER BY id DESC LIMIT 1 FOR UPDATE""",(usuario_id,))
        token=cur.fetchone()
        if not token:
            return False
        if token['intentos']>=5 or not hmac.compare_digest(token['token_hash'],token_hash):
            cur.execute("""UPDATE password_reset_token SET intentos=intentos+1,usado=(intentos+1>=5),
                fecha_uso=CASE WHEN intentos+1>=5 THEN CURRENT_TIMESTAMP ELSE fecha_uso END WHERE id=%s""",(token['id'],))
            return False
        cur.execute('UPDATE usuario SET password_hash=%s,intentos_fallidos=0,bloqueado_hasta=NULL WHERE id=%s',(password_hash,usuario_id))
        invalidar_accesos(cur,usuario_id,empresa_id)
        return True
