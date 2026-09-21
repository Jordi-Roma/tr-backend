from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import verificar_token_acceso
from app.modules.autenticacion.repositories.sesion_repository import sesion_esta_activa
from app.modules.autenticacion.repositories.usuario_repository import obtener_usuario_por_id
from app.modules.inteligencia.schemas.asistente.asistente_schemas import (
    AsistenteChatRequest,
    AsistenteChatResponse,
)
from app.modules.inteligencia.services.asistente_service import responder_chat_asistente

router = APIRouter(prefix="/api/v1/asistente", tags=["Asistente virtual IA"])
optional_bearer = HTTPBearer(auto_error=False)


def obtener_usuario_opcional(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer),
) -> dict[str, object] | None:
    if credentials is None:
        return None

    try:
        payload = verificar_token_acceso(credentials.credentials)
        usuario_id = int(str(payload.get("sub")))
        sesion_id = int(str(payload.get("sid")))
    except Exception:
        return None

    if not sesion_esta_activa(sesion_id, usuario_id):
        return None

    usuario = obtener_usuario_por_id(usuario_id)
    if usuario is None or usuario.get("activo") is not True:
        return None

    return usuario


@router.post("/chat", response_model=AsistenteChatResponse)
def chat_asistente(
    request: AsistenteChatRequest,
    usuario_actual: dict[str, object] | None = Depends(obtener_usuario_opcional),
) -> AsistenteChatResponse:
    return responder_chat_asistente(request, usuario_actual)

