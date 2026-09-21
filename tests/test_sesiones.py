import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.modules.autenticacion.dependencies import usuario_actual


def test_token_de_sesion_cerrada_es_rechazado(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        usuario_actual,
        "verificar_token_acceso",
        lambda _token: {"sub": "7", "sid": "19"},
    )
    monkeypatch.setattr(usuario_actual, "sesion_esta_activa", lambda _sid, _uid: False)

    with pytest.raises(HTTPException) as error:
        usuario_actual.obtener_usuario_actual(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials="token-cerrado")
        )

    assert error.value.status_code == 401


def test_token_sin_identificador_de_sesion_es_rechazado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        usuario_actual,
        "verificar_token_acceso",
        lambda _token: {"sub": "7"},
    )

    with pytest.raises(HTTPException) as error:
        usuario_actual.obtener_usuario_actual(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials="token-antiguo")
        )

    assert error.value.status_code == 401
