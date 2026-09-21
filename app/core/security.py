from datetime import datetime, timedelta, timezone

from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext

from app.core.config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def validar_password_seguro(password: str) -> None:
    if len(password) < 8:
        raise ValueError("La contrasena debe tener al menos 8 caracteres.")

    if not any(caracter.islower() for caracter in password):
        raise ValueError("La contrasena debe tener al menos una letra minuscula.")

    if not any(caracter.isupper() for caracter in password):
        raise ValueError("La contrasena debe tener al menos una letra mayuscula.")

    if not any(caracter.isdigit() for caracter in password):
        raise ValueError("La contrasena debe tener al menos un numero.")

    if not any(not caracter.isalnum() for caracter in password):
        raise ValueError("La contrasena debe tener al menos un simbolo.")


def hashear_password(password: str) -> str:
    validar_password_seguro(password)
    return pwd_context.hash(password)


def verificar_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def crear_token_acceso(data: dict[str, object]) -> str:
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY no esta configurada.")

    datos_token = data.copy()
    fecha_expiracion = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    datos_token.update({"exp": fecha_expiracion})

    return jwt.encode(datos_token, SECRET_KEY, algorithm=ALGORITHM)


def verificar_token_acceso(token: str) -> dict[str, object]:
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY no esta configurada.")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except ExpiredSignatureError as error:
        raise ValueError("El token de acceso expiro.") from error
    except JWTError as error:
        raise ValueError("El token de acceso no es valido.") from error

    return dict(payload)
