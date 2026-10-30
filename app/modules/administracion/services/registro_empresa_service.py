import hashlib
import hmac
import json

from fastapi import HTTPException
from psycopg2.errors import UniqueViolation

from app.core.config import SECRET_KEY
from app.core.security import hashear_password
from app.modules.administracion.repositories import registro_empresa_repository as repo


def _hash(valor):
    if not SECRET_KEY:
        raise HTTPException(503, 'El registro de empresas no está configurado.')
    return hmac.new(SECRET_KEY.encode(), valor.encode(), hashlib.sha256).hexdigest()


def registrar(datos, origen):
    huella = _hash('alta:'+json.dumps(datos.model_dump(mode='json', exclude={'confirmar_password'}), sort_keys=True, ensure_ascii=False))
    try:
        empresa = repo.registrar(datos, hashear_password(datos.password), huella, _hash('origen:'+origen))
    except UniqueViolation as error:
        raise HTTPException(409, 'El identificador de empresa, usuario o correo ya está registrado. Revisa esos datos.') from error
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    mensajes = {
        'PENDIENTE': 'Empresa registrada. Queda pendiente de aprobación por la administración de StyleAR.',
        'ACTIVA': 'La empresa ya fue aprobada. Puedes ingresar desde el directorio.',
        'SUSPENDIDA': 'La empresa está suspendida. Contacta con la administración de StyleAR.',
        'CANCELADA': 'La solicitud de esta empresa fue cancelada por la administración de StyleAR.',
    }
    return {'empresa':empresa, 'mensaje':mensajes[empresa['estado']]}
