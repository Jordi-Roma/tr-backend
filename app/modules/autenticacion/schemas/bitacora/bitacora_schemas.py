import math
from datetime import datetime

from pydantic import BaseModel


class BitacoraItemResponse(BaseModel):
    id: int
    usuario_id: int | None
    usuario_username: str | None
    usuario_nombre: str | None
    usuario_apellido: str | None
    accion: str
    modulo: str
    descripcion: str | None
    resultado: str
    direccion_ip: str | None
    user_agent: str | None
    fecha: datetime


class BitacoraDetalleResponse(BitacoraItemResponse):
    usuario_correo: str | None


class BitacoraListResponse(BaseModel):
    registros: list[BitacoraItemResponse]
    total: int
    pagina: int
    por_pagina: int
    total_paginas: int

    @classmethod
    def construir(
        cls,
        registros: list[dict[str, object]],
        total: int,
        pagina: int,
        por_pagina: int,
    ) -> "BitacoraListResponse":
        total_paginas = max(1, math.ceil(total / por_pagina)) if total > 0 else 1
        return cls(
            registros=[_construir_item(r) for r in registros],
            total=total,
            pagina=pagina,
            por_pagina=por_pagina,
            total_paginas=total_paginas,
        )


def _construir_item(row: dict[str, object]) -> BitacoraItemResponse:
    return BitacoraItemResponse(
        id=int(row["id"]),
        usuario_id=int(row["usuario_id"]) if row.get("usuario_id") is not None else None,
        usuario_username=str(row["usuario_username"]) if row.get("usuario_username") else None,
        usuario_nombre=str(row["usuario_nombre"]) if row.get("usuario_nombre") else None,
        usuario_apellido=str(row["usuario_apellido"]) if row.get("usuario_apellido") else None,
        accion=str(row["accion"]),
        modulo=str(row["modulo"]),
        descripcion=str(row["descripcion"]) if row.get("descripcion") else None,
        resultado=str(row["resultado"]),
        direccion_ip=str(row["direccion_ip"]) if row.get("direccion_ip") else None,
        user_agent=str(row["user_agent"]) if row.get("user_agent") else None,
        fecha=row["fecha"],  # type: ignore[arg-type]
    )


def construir_detalle(row: dict[str, object]) -> BitacoraDetalleResponse:
    return BitacoraDetalleResponse(
        id=int(row["id"]),
        usuario_id=int(row["usuario_id"]) if row.get("usuario_id") is not None else None,
        usuario_username=str(row["usuario_username"]) if row.get("usuario_username") else None,
        usuario_nombre=str(row["usuario_nombre"]) if row.get("usuario_nombre") else None,
        usuario_apellido=str(row["usuario_apellido"]) if row.get("usuario_apellido") else None,
        usuario_correo=str(row["usuario_correo"]) if row.get("usuario_correo") else None,
        accion=str(row["accion"]),
        modulo=str(row["modulo"]),
        descripcion=str(row["descripcion"]) if row.get("descripcion") else None,
        resultado=str(row["resultado"]),
        direccion_ip=str(row["direccion_ip"]) if row.get("direccion_ip") else None,
        user_agent=str(row["user_agent"]) if row.get("user_agent") else None,
        fecha=row["fecha"],  # type: ignore[arg-type]
    )
