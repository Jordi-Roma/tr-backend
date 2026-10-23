from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import verificar_token_acceso
from app.core.contexto_empresa import exigir_empresa_id, resolver_empresa_por_codigo
from app.core.plan_empresa import exigir_funcion_empresa
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

    usuario = obtener_usuario_por_id(usuario_id)
    if usuario is None or usuario.get("activo") is not True:
        return None
    empresa_id = usuario.get("empresa_id")
    if payload.get("empresa_id") != empresa_id:
        return None
    if empresa_id is None or usuario.get("empresa_estado") not in {"ACTIVA", "SUSPENDIDA"}:
        return None
    if not sesion_esta_activa(sesion_id, usuario_id, empresa_id):
        return None

    return usuario


@router.post("/chat", response_model=AsistenteChatResponse)
def chat_asistente(
    request: AsistenteChatRequest,
    usuario_actual: dict[str, object] | None = Depends(obtener_usuario_opcional),
    x_empresa_codigo: str | None = Header(default=None, alias="X-Empresa-Codigo"),
) -> AsistenteChatResponse:
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

