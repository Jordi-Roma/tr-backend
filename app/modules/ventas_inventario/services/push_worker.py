"""Ejecutar: python -m app.modules.ventas_inventario.services.push_worker

Añadir --continuo para atender la cola cada 10 segundos mientras corre el proceso.
Sin credenciales, conserva la cola pendiente. FCM aceptado no significa entrega en teléfono.
"""
import os
import httpx
from app.modules.autenticacion.repositories.perfil_repository import _transaccion


def enviar_fcm(token,nid,empresa):
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    proyecto=os.environ['STYLEAR_FIREBASE_PROJECT_ID']
    cred=service_account.Credentials.from_service_account_file(os.environ['STYLEAR_FIREBASE_CREDENTIALS'],
        scopes=['https://www.googleapis.com/auth/firebase.messaging'])
    if cred.project_id != proyecto:
        raise ValueError('El proyecto Firebase no corresponde a las credenciales configuradas.')
    cred.refresh(Request())
    response=httpx.post(f'https://fcm.googleapis.com/v1/projects/{proyecto}/messages:send',timeout=10,
        headers={'Authorization':'Bearer '+cred.token},json={'message':{'token':token,
            'notification':{'title':'StyleAR','body':'Tienes una actualización. Abre la aplicación para consultarla.'},
            'data':{'notificacion_id':str(nid),'empresa_id':str(empresa)}}})
    if response.status_code==404 and any(d.get('errorCode')=='UNREGISTERED' for d in response.json().get('error',{}).get('details',[])):
        raise TokenRetirado()
    if response.status_code!=200:
        raise RuntimeError('FCM no aceptó el mensaje.')
    return response.json()['name']


class TokenRetirado(Exception):pass


def procesar(limite=20):
    if not os.getenv('STYLEAR_FIREBASE_PROJECT_ID') or not os.getenv('STYLEAR_FIREBASE_CREDENTIALS'):
        return {'estado':'SIN_CONFIGURAR','enviados':0}
    enviados=0
    vistos=[]
    for _ in range(limite):
        with _transaccion() as cur:
            cur.execute('''SELECT s.id,s.notificacion_id,s.dispositivo_id,n.usuario_id,n.empresa_id,d.token,
                d.usuario_id du,d.empresa_id de,d.activo,u.activo ua,d.version_acceso,u.version_acceso uv,
                EXISTS(SELECT 1 FROM sesion se WHERE se.id=d.sesion_id AND se.usuario_id=d.usuario_id AND se.empresa_id=d.empresa_id AND se.activa AND se.fecha_cierre IS NULL AND se.fecha_expiracion>CURRENT_TIMESTAMP) sesion_activa
                FROM salida_push s JOIN notificacion_usuario n ON n.id=s.notificacion_id
                JOIN dispositivo_push d ON d.id=s.dispositivo_id JOIN usuario u ON u.id=d.usuario_id
                WHERE s.estado IN ('PENDIENTE','FALLIDO') AND s.intentos<5 AND NOT(s.id=ANY(%s))
                ORDER BY s.intentos,s.id LIMIT 1 FOR UPDATE OF s,d SKIP LOCKED''',(vistos,))
            f=cur.fetchone()
            if not f:break
            vistos.append(f['id'])
            if not f['sesion_activa'] or not f['activo'] or not f['ua'] or f['usuario_id']!=f['du'] or f['empresa_id']!=f['de'] or f['version_acceso']!=f['uv']:
                cur.execute("UPDATE salida_push SET estado='OMITIDO' WHERE id=%s",(f['id'],));continue
            try:
                referencia=enviar_fcm(f['token'],f['notificacion_id'],f['empresa_id'])
                cur.execute("UPDATE salida_push SET estado='ENVIADO',intentos=intentos+1,proveedor_referencia=%s,ultimo_error=NULL WHERE id=%s",(referencia,f['id']))
                enviados+=1
            except TokenRetirado:
                cur.execute('UPDATE dispositivo_push SET activo=FALSE WHERE id=%s',(f['dispositivo_id'],))
                cur.execute("UPDATE salida_push SET estado='OMITIDO',intentos=intentos+1,ultimo_error='Token retirado por FCM.' WHERE id=%s",(f['id'],))
            except Exception:
                # No almacenar respuestas que puedan contener tokens ni credenciales.
                cur.execute("UPDATE salida_push SET estado='FALLIDO',intentos=intentos+1,ultimo_error='No se pudo confirmar la aceptación en FCM.' WHERE id=%s",(f['id'],))
    return {'estado':'PROCESADO','enviados':enviados}


def main():
    import argparse
    import time

    parser = argparse.ArgumentParser(description='Procesar avisos FCM pendientes de StyleAR.')
    parser.add_argument('--continuo', action='store_true', help='Mantener el trabajador atendiendo la cola.')
    parser.add_argument('--intervalo', type=int, default=10, help='Segundos entre lotes (1–3600).')
    args = parser.parse_args()
    if not 1 <= args.intervalo <= 3600:
        parser.error('--intervalo debe estar entre 1 y 3600 segundos.')
    try:
        while True:
            try:
                resultado = procesar()
            except Exception:
                # Un fallo transitorio de BD no termina el trabajador ni expone secretos.
                print('No se pudo procesar la cola; los avisos conservan su estado.', flush=True)
                if not args.continuo:
                    return 1
            else:
                print(resultado, flush=True)
                if not args.continuo:
                    return 0
                if resultado['estado'] == 'SIN_CONFIGURAR':
                    return 1
            time.sleep(args.intervalo)
    except KeyboardInterrupt:
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
