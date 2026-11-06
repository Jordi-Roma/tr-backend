from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.contexto_empresa import exigir_empresa_id, resolver_empresa_por_codigo
from app.core.plan_empresa import exigir_funcion_empresa
from app.modules.inteligencia.schemas.asistente.asistente_schemas import (
    AsistenteChatRequest,
    AsistenteChatResponse,
)
from app.modules.inteligencia.services.asistente_service import responder_chat_asistente
from app.modules.autenticacion.dependencies.usuario_actual import obtener_usuario_actual
from collections import OrderedDict, deque
from threading import Lock
from time import monotonic

router = APIRouter(prefix="/api/v1/asistente", tags=["Asistente virtual IA"])
optional_bearer = HTTPBearer(auto_error=False)
_solicitudes = OrderedDict()
_cerrojo = Lock()


def limitar_solicitudes(clave, ahora=None):
    """Protección técnica local por proceso; no es una cuota comercial."""
    ahora = monotonic() if ahora is None else ahora
    with _cerrojo:
        while _solicitudes and next(iter(_solicitudes.values()))[-1] <= ahora-60:
            _solicitudes.popitem(last=False)
        cola = _solicitudes.pop(clave, deque())
        while cola and cola[0] <= ahora-60:
            cola.popleft()
        if len(cola) >= 60:
            _solicitudes[clave] = cola
            raise HTTPException(429, 'Demasiadas consultas. Intenta de nuevo en un minuto.', headers={'Retry-After':'60'})
        cola.append(ahora)
        _solicitudes[clave] = cola
        if len(_solicitudes)>4096:
            _solicitudes.popitem(last=False)


def obtener_usuario_opcional(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer),
) -> dict[str, object] | None:
    if credentials is None:
        if request.headers.get('Authorization'):
            raise HTTPException(401, 'La autorización no es válida.')
        return None
    usuario = obtener_usuario_actual(credentials, request)
    if usuario.get('empresa_id') is None or 'ADMIN_SAAS' in usuario.get('roles', []):
        raise HTTPException(403, 'El asistente requiere una empresa.')
    return usuario


@router.post("/chat", response_model=AsistenteChatResponse)
def chat_asistente(
    request: AsistenteChatRequest,
    conexion: Request,
    usuario_actual: dict[str, object] | None = Depends(obtener_usuario_opcional),
    x_empresa_codigo: str | None = Header(default=None, alias="X-Empresa-Codigo"),
) -> AsistenteChatResponse:
    # No confiar en X-Forwarded-For enviado por el cliente.
    limitar_solicitudes(conexion.client.host if conexion.client else 'desconocido')
    if usuario_actual is not None:
        empresa_id = exigir_empresa_id(usuario_actual)
        if x_empresa_codigo and x_empresa_codigo.lower() != str(usuario_actual.get("empresa_codigo", "")).lower():
            raise HTTPException(status_code=403, detail="La empresa indicada no corresponde a la sesión.")
    else:
        if not x_empresa_codigo:
            raise HTTPException(status_code=400, detail="Debe indicar el codigo de empresa.")
        empresa = resolver_empresa_por_codigo(x_empresa_codigo)
        if empresa is None or empresa["estado"] not in {"ACTIVA", "SUSPENDIDA"}:
            raise HTTPException(status_code=404, detail="Empresa no encontrada.")
        empresa_id = int(empresa["id"])
    exigir_funcion_empresa(empresa_id, "asistente", permitir_consulta=True)
    return responder_chat_asistente(request, usuario_actual, empresa_id)

