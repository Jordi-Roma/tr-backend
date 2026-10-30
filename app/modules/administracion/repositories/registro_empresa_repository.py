"""Solicitudes públicas: alta atómica pendiente, sin acceso SaaS ni envío de correo."""
import hmac

from fastapi import HTTPException

from app.modules.autenticacion.repositories.perfil_repository import _transaccion
from app.modules.administracion.repositories.empresa_saas_repository import auditar


def planes_publicos():
    with _transaccion() as cur:
        cur.execute("""SELECT id,nombre,limites,funciones FROM plan
            WHERE activo AND publico AND codigo <> 'STYLEAR_LEGADO'
              AND coalesce((limites->>'usuarios')::int,1) >= 1 ORDER BY id""")
        return [dict(fila) for fila in cur.fetchall()]


def registrar(datos, password_hash, huella, origen_hash):
    with _transaccion() as cur:
        for ambito in ('registro-clave:'+str(datos.clave_solicitud), 'registro-origen:'+origen_hash):
            cur.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', (ambito,))
        cur.execute('SELECT empresa_id,huella_alta FROM solicitud_registro_empresa WHERE id=%s', (str(datos.clave_solicitud),))
        anterior = cur.fetchone()
        if anterior:
            if not hmac.compare_digest(anterior['huella_alta'], huella):
                raise ValueError('La solicitud ya se utilizó con otros datos.')
            cur.execute('SELECT id,codigo,nombre,estado FROM empresa WHERE id=%s', (anterior['empresa_id'],))
            return dict(cur.fetchone())
        cur.execute("""SELECT count(*) AS n FROM solicitud_registro_empresa
            WHERE origen_hash=%s AND fecha_creacion>CURRENT_TIMESTAMP-INTERVAL '1 hour'""", (origen_hash,))
        if cur.fetchone()['n'] >= 20:
            raise HTTPException(429, 'Se alcanzó el límite de solicitudes. Inténtalo más tarde.', headers={'Retry-After':'3600'})
        cur.execute("""SELECT id FROM plan WHERE id=%s AND activo AND publico
            AND codigo<>'STYLEAR_LEGADO' AND coalesce((limites->>'usuarios')::int,1)>=1 FOR SHARE""", (datos.plan_id,))
        if not cur.fetchone():
            raise ValueError('El plan ya no está disponible para registro. Elige otro plan.')
        cur.execute("""INSERT INTO empresa(codigo,nombre,estado) VALUES(%s,%s,'PENDIENTE')
            RETURNING id,codigo,nombre,estado""", (datos.empresa_codigo,datos.empresa_nombre))
        empresa = dict(cur.fetchone())
        cur.execute("""INSERT INTO suscripcion(empresa_id,plan_id,estado)
            VALUES(%s,%s,'PENDIENTE')""", (empresa['id'],datos.plan_id))
        cur.execute("""INSERT INTO usuario(empresa_id,nombre,apellido,username,correo,password_hash)
            VALUES(%s,%s,%s,%s,%s,%s) RETURNING id""",
            (empresa['id'],datos.nombre,datos.apellido,datos.username,datos.correo,password_hash))
        usuario = cur.fetchone()['id']
        cur.execute("""INSERT INTO usuario_rol(usuario_id,rol_id)
            SELECT %s,id FROM rol WHERE nombre='ADMINISTRADOR' AND activo RETURNING rol_id""", (usuario,))
        if not cur.fetchone():
            raise ValueError('No está disponible el rol administrador de empresa.')
        cur.execute("""INSERT INTO solicitud_registro_empresa
            (id,empresa_id,correo_contacto,responsable,origen_hash,huella_alta) VALUES(%s,%s,%s,%s,%s,%s)""",
            (str(datos.clave_solicitud),empresa['id'],datos.correo,f'{datos.nombre} {datos.apellido}',origen_hash,huella))
        auditar(cur, usuario, 'REGISTRO_PUBLICO_EMPRESA', empresa['id'])
        return empresa
