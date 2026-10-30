"""Contrato Resend y flujos reales de servicio, sin red ni base de negocio."""

import base64
import json
from unittest.mock import Mock

import pytest
import requests
from fastapi import HTTPException

from app.core import email
from app.modules.autenticacion.services import password_reset_service as reset
from app.modules.autenticacion.schemas.password_reset.password_reset_request import SolicitarPasswordResetRequest
from app.modules.ventas_inventario.services import nota_venta_service as notas


@pytest.fixture(autouse=True)
def aislado(monkeypatch):
    # Fallar si alguna prueba intenta acceder a SMTP, HTTPS o PostgreSQL reales.
    def prohibido(*args, **kwargs):
        raise AssertionError("No se permiten conexiones reales en estas pruebas.")
    monkeypatch.setattr(email.requests, "post", prohibido)
    monkeypatch.setattr(email.smtplib, "SMTP", prohibido)
    import psycopg2
    monkeypatch.setattr(psycopg2, "connect", prohibido)
    for nombre, valor in {
        "MAIL_PROVIDER": "resend", "MAIL_TO_OVERRIDE": "central@example.invalid",
        "RESEND_API_KEY": "re_prueba_ficticia", "RESEND_FROM": "StyleAR <onboarding@resend.dev>",
        "SMTP_HOST": "smtp.example.invalid", "SMTP_USER": "smtp@example.invalid",
        "SMTP_PASSWORD": "ficticia", "SMTP_FROM": "smtp@example.invalid",
    }.items():
        monkeypatch.setattr(email, nombre, valor)


@pytest.fixture
def proveedor(monkeypatch):
    respuesta = requests.Response()
    respuesta.status_code = 200
    respuesta._content = b'{"id":"correo-aceptado"}'
    respuesta._content_consumed = True
    post = Mock(return_value=respuesta)
    monkeypatch.setattr(email.requests, "post", post)
    return post, respuesta


def test_texto_solo_al_destino_fijo_sin_copia_al_cliente(proveedor):
    post, _ = proveedor
    email.enviar_correo("cliente@example.invalid", "Recuperación", "Codigo: 123456")
    args, kwargs = post.call_args
    assert args == ("https://api.resend.com/emails",)
    assert kwargs["headers"]["Authorization"] == "Bearer re_prueba_ficticia"
    assert kwargs["timeout"] == (5, 20) and kwargs["allow_redirects"] is False
    assert kwargs["json"] == {
        "from": "StyleAR <onboarding@resend.dev>", "to": ["central@example.invalid"],
        "subject": "Recuperación", "text": "Codigo: 123456",
    }
    post.assert_called_once()


def test_pdf_bytes_y_nombre_empresa_como_emisor(proveedor):
    post, _ = proveedor
    pdf = b"%PDF-1.4\ncontenido ficticio\x00\xff"
    email.enviar_correo_con_adjunto(None, "Nota 1", "Comprobante", pdf, "nota.pdf", "Tienda Roma")
    payload = post.call_args.kwargs["json"]
    assert payload["to"] == ["central@example.invalid"]
    assert payload["from"] == "Tienda Roma <onboarding@resend.dev>"
    adjunto = payload["attachments"][0]
    assert base64.b64decode(adjunto["content"]) == pdf
    assert adjunto["filename"] == "nota.pdf" and adjunto["content_type"] == "application/pdf"


@pytest.mark.parametrize("variable", ["RESEND_API_KEY", "RESEND_FROM", "MAIL_TO_OVERRIDE"])
def test_config_incompleta_no_envia_ni_hace_fallback(monkeypatch, variable):
    monkeypatch.setattr(email, variable, "")
    with pytest.raises(ValueError):
        email.enviar_correo("cliente@example.invalid", "Asunto", "Contenido")


@pytest.mark.parametrize("destino", [
    "sin-arroba", "a@example.invalid,b@example.invalid", "a@example.invalid; b@example.invalid",
    "a@example.invalid\r\nBcc: b@example.invalid", "Nombre <a@example.invalid>",
])
def test_destino_fijo_invalido_no_envia(monkeypatch, destino):
    monkeypatch.setattr(email, "MAIL_TO_OVERRIDE", destino)
    with pytest.raises(ValueError):
        email.enviar_correo("cliente@example.invalid", "Asunto", "Contenido")


@pytest.mark.parametrize("status", [301, 302, 400, 401, 403, 422, 429, 500, 503])
def test_rechazos_no_son_exitos_ni_exponen_cuerpo_ni_reintentan(proveedor, status):
    post, respuesta = proveedor
    respuesta.status_code = status
    respuesta._content = b'"re_prueba_ficticia Codigo: 123456"'
    with pytest.raises(OSError) as error:
        email.enviar_correo("cliente@example.invalid", "Asunto", "Codigo: 123456")
    assert f"HTTP {status}" in str(error.value)
    assert "re_prueba" not in str(error.value) and "123456" not in str(error.value)
    post.assert_called_once()


@pytest.mark.parametrize("cuerpo", [b"no json", b"{}", b"null", b"[]"])
def test_respuesta_sin_confirmacion_no_reporta_exito(proveedor, cuerpo):
    _, respuesta = proveedor
    respuesta._content = cuerpo
    with pytest.raises(OSError):
        email.enviar_correo("cliente@example.invalid", "Asunto", "Contenido")


def test_timeout_no_hace_fallback_ni_expone_error_original(monkeypatch):
    post = Mock(side_effect=requests.Timeout("re_prueba_ficticia Codigo: 123456"))
    monkeypatch.setattr(email.requests, "post", post)
    with pytest.raises(OSError) as error:
        email.enviar_correo("cliente@example.invalid", "Asunto", "Contenido")
    assert "123456" not in str(error.value) and "re_prueba" not in str(error.value)
    assert error.value.__suppress_context__
    post.assert_called_once()


def test_proveedor_invalido_no_intenta_conectar(monkeypatch):
    monkeypatch.setattr(email, "MAIL_PROVIDER", "otro")
    with pytest.raises(ValueError, match="MAIL_PROVIDER"):
        email.enviar_correo("cliente@example.invalid", "Asunto", "Contenido")


@pytest.mark.parametrize("fijo", ["", "central@example.invalid"])
def test_compatibilidad_smtp_respeta_destino_y_pdf(monkeypatch, fijo):
    monkeypatch.setattr(email, "MAIL_PROVIDER", "smtp")
    monkeypatch.setattr(email, "MAIL_TO_OVERRIDE", fijo)
    smtp = Mock()
    conexion = Mock()
    conexion.__enter__ = Mock(return_value=smtp)
    conexion.__exit__ = Mock(return_value=False)
    fabrica = Mock(return_value=conexion)
    monkeypatch.setattr(email.smtplib, "SMTP", fabrica)
    email.enviar_correo_con_adjunto("cliente@example.invalid", "Nota", "Contenido", b"%PDF", "nota.pdf", "Roma")
    fabrica.assert_called_once_with("smtp.example.invalid", email.SMTP_PORT, timeout=20)
    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once_with("smtp@example.invalid", "ficticia")
    mensaje = smtp.send_message.call_args.args[0]
    assert mensaje["To"] == (fijo or "cliente@example.invalid")
    assert mensaje["Cc"] is None and mensaje["Bcc"] is None
    assert list(mensaje.iter_attachments())[0].get_payload(decode=True) == b"%PDF"


@pytest.fixture
def cuenta(monkeypatch):
    usuario = {"id": 7, "username": "ana", "correo": "ana@example.invalid", "activo": True}
    monkeypatch.setattr(reset, "SECRET_KEY", "clave-ficticia-local")
    monkeypatch.setattr(reset, "resolver_empresa_por_codigo", Mock(return_value={"id": 10, "estado": "ACTIVA", "nombre": "Roma"}))
    monkeypatch.setattr(reset, "obtener_usuario_por_identificador", Mock(return_value=usuario))
    monkeypatch.setattr(reset, "guardar_token_reset", Mock(return_value=True))
    monkeypatch.setattr(reset.secrets, "randbelow", lambda _: 123456)
    monkeypatch.setattr(reset, "registrar_bitacora", Mock())
    return usuario


@pytest.mark.parametrize("empresa", ["roma", None])
def test_recuperacion_tenant_y_saas_real_usa_central(proveedor, cuenta, empresa):
    post, _ = proveedor
    r = reset.solicitar_reset_password(SolicitarPasswordResetRequest(identificador="ana", empresa_codigo=empresa))
    payload = post.call_args.kwargs["json"]
    assert payload["to"] == ["central@example.invalid"]
    assert "Codigo: 123456" in payload["text"] and cuenta["correo"] in payload["text"]
    assert ("Roma" if empresa else "Plataforma StyleAR") in payload["subject"]
    assert "correo de recepción configurado" in r.mensaje
    # La identidad y el aislamiento del token se conservan; solo cambia el envío.
    args = reset.guardar_token_reset.call_args.args
    assert args[0] == 7 and args[1] != "123456" and args[3] == (10 if empresa else None)
    assert reset.registrar_bitacora.call_args.kwargs["resultado"] == "EXITOSO"


def test_recuperacion_cuenta_inexistente_mismo_mensaje_sin_envio(monkeypatch, proveedor, cuenta):
    post, _ = proveedor
    solicitud = SolicitarPasswordResetRequest(identificador="ana", empresa_codigo="roma")
    esperado = reset.solicitar_reset_password(solicitud).mensaje
    post.reset_mock()
    reset.guardar_token_reset.reset_mock()
    monkeypatch.setattr(reset, "obtener_usuario_por_identificador", lambda *_: None)
    assert reset.solicitar_reset_password(solicitud).mensaje == esperado
    post.assert_not_called()
    reset.guardar_token_reset.assert_not_called()


def test_error_recuperacion_es_503_y_audita_fallo(proveedor, cuenta):
    _, respuesta = proveedor
    respuesta.status_code = 403
    with pytest.raises(HTTPException) as error:
        reset.solicitar_reset_password(SolicitarPasswordResetRequest(identificador="ana", empresa_codigo="roma"))
    assert error.value.status_code == 503
    assert "123456" not in error.value.detail and "re_prueba" not in error.value.detail
    assert reset.registrar_bitacora.call_args.kwargs["resultado"] == "FALLIDO"


@pytest.fixture
def nota(monkeypatch):
    datos = {"empresa": "Tienda Roma", "sucursal": "Centro", "direccion": "Calle de prueba",
             "fecha_venta": "2026-10-30T12:00:00-04:00", "codigo": "V-001", "cliente": None,
             "subtotal": "50", "descuento": "0", "total": "50", "metodo_pago": "EFECTIVO",
             "detalles": [{"producto": "Polera", "talla": "L", "color": "Azul", "cantidad": 1,
                           "precio_unitario": "50", "descuento": "0", "subtotal": "50"}]}
    nota = {"numero": 1, "datos": datos}
    monkeypatch.setattr(notas, "preparar_nota", Mock(return_value=nota))
    return nota


def test_nota_sin_correo_cliente_usa_central_y_pdf_de_empresa(proveedor, nota):
    from io import BytesIO
    from pypdf import PdfReader
    post, _ = proveedor
    r = notas.enviar_nota({"empresa_id": 10}, 1)
    payload = post.call_args.kwargs["json"]
    assert payload["to"] == ["central@example.invalid"]
    assert payload["from"] == "Tienda Roma <onboarding@resend.dev>"
    pdf = base64.b64decode(payload["attachments"][0]["content"])
    texto = "".join(p.extract_text() for p in PdfReader(BytesIO(pdf)).pages)
    assert "Tienda Roma" in texto and "NOTA DE VENTA" in texto
    assert "StyleAR" not in texto and "correo de recepción configurado" in r["mensaje"]


def test_nota_error_proveedor_no_modifica_nota_y_pdf_sigue_disponible(proveedor, nota):
    _, respuesta = proveedor
    respuesta.status_code = 429
    antes = json.dumps(nota)
    with pytest.raises(HTTPException) as error:
        notas.enviar_nota({"empresa_id": 10}, 1)
    assert error.value.status_code == 503
    assert "La venta sigue registrada" in error.value.detail
    assert json.dumps(nota) == antes and notas.generar_pdf(nota).startswith(b"%PDF")


def test_nota_sin_cliente_sigue_exigiendo_correo_en_modo_smtp_normal(monkeypatch, nota):
    monkeypatch.setattr(email, "MAIL_PROVIDER", "smtp")
    monkeypatch.setattr(email, "MAIL_TO_OVERRIDE", "")
    with pytest.raises(HTTPException) as error:
        notas.enviar_nota({"empresa_id": 10}, 1)
    assert error.value.status_code == 409


def test_autorizacion_empresa_y_sucursal_antes_de_enviar(monkeypatch, proveedor):
    post, _ = proveedor
    monkeypatch.setattr(notas, "obtener_venta_service", Mock(side_effect=HTTPException(404, "No encontrada")))
    obtener = Mock()
    monkeypatch.setattr(notas, "obtener_nota", obtener)
    with pytest.raises(HTTPException) as error:
        notas.enviar_nota({"empresa_id": 99}, 1)
    assert error.value.status_code == 404
    obtener.assert_not_called()
    post.assert_not_called()
