from email.message import EmailMessage
import smtplib

from app.core.config import SMTP_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER


def enviar_correo(destinatario: str, asunto: str, contenido: str) -> None:
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASSWORD or not SMTP_FROM:
        raise ValueError("La configuracion SMTP no esta completa.")

    mensaje = EmailMessage()
    mensaje["From"] = SMTP_FROM
    mensaje["To"] = destinatario
    mensaje["Subject"] = asunto
    mensaje.set_content(contenido)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.send_message(mensaje)
