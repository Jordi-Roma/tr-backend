from pydantic import BaseModel


class PasswordResetMensajeResponse(BaseModel):
    mensaje: str
