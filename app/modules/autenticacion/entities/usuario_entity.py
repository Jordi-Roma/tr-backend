from dataclasses import dataclass


@dataclass
class UsuarioEntity:
    id: int | None
    nombre: str
    apellido: str
    username: str
    correo: str
    password_hash: str
    activo: bool = True
