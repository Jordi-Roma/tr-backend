"""Bandeja propia y registro privado de instalaciones FCM."""
import os
from uuid import UUID
from fastapi import HTTPException
from pydantic import BaseModel, Field
from typing import Literal
from app.core.contexto_empresa import exigir_empresa_id
from app.modules.autenticacion.repositories.perfil_repository import _transaccion


class DispositivoRequest(BaseModel):
    instalacion_id: UUID
    token: str = Field(min_length=20,max_length=4096)
    plataforma: Literal['android','ios','web']


def listar(actor):
    with _transaccion() as cur:
        cur.execute('''SELECT n.* FROM notificacion_usuario n WHERE empresa_id=%s AND usuario_id=%s ORDER BY id DESC LIMIT 100''',
                    (exigir_empresa_id(actor),actor['id']))
        return [dict(f) for f in cur.fetchall()]


def leer(actor,nid):
    with _transaccion() as cur:
        cur.execute('UPDATE notificacion_usuario SET leida=TRUE WHERE id=%s AND empresa_id=%s AND usuario_id=%s RETURNING id',
                    (nid,exigir_empresa_id(actor),actor['id']))
        if not cur.fetchone():raise HTTPException(404,'Notificación no encontrada.')
    return {'mensaje':'Notificación leída.'}


def registrar(actor,datos):
    with _transaccion() as cur:
        cur.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('push:'+str(datos.instalacion_id),))
        # Una instalación vuelve a vincularse al cambiar de cuenta. El UUID permanece privado en el dispositivo.
        cur.execute('SELECT id,instalacion_id FROM dispositivo_push WHERE token=%s FOR UPDATE',(datos.token,))
        previo = cur.fetchone()
        if previo and str(previo['instalacion_id'])!=str(datos.instalacion_id):
            raise HTTPException(409,'El token ya pertenece a otra instalación.')
        cur.execute('''INSERT INTO dispositivo_push(empresa_id,usuario_id,instalacion_id,token,plataforma,version_acceso,sesion_id)
            VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(instalacion_id) DO UPDATE SET empresa_id=EXCLUDED.empresa_id,
            usuario_id=EXCLUDED.usuario_id,token=EXCLUDED.token,plataforma=EXCLUDED.plataforma,
            version_acceso=EXCLUDED.version_acceso,sesion_id=EXCLUDED.sesion_id,activo=TRUE,actualizado_en=CURRENT_TIMESTAMP''',
            (exigir_empresa_id(actor),actor['id'],str(datos.instalacion_id),datos.token,datos.plataforma,actor.get('version_acceso',0),actor['_sesion_id']))
    return {'mensaje':'Instalación vinculada a la sesión actual.'}


def retirar(actor,instalacion):
    with _transaccion() as cur:
        cur.execute('UPDATE dispositivo_push SET activo=FALSE WHERE instalacion_id=%s AND empresa_id=%s AND usuario_id=%s',
                    (str(instalacion),exigir_empresa_id(actor),actor['id']))
    return {'mensaje':'Instalación desvinculada.'}


def estado():
    return {'push_configurado':bool(os.getenv('STYLEAR_FIREBASE_PROJECT_ID') and os.getenv('STYLEAR_FIREBASE_CREDENTIALS')),
            'bandeja_disponible':True}
