"""Resolucion y validacion del alcance de empresa de cada peticion."""

import re

from fastapi import Header, HTTPException, Request
from psycopg2.extras import RealDictCursor

from app.database.connection import get_connection


_CODIGO_EMPRESA = re.compile(r"^[a-z0-9][a-z0-9-]{1,39}$")


def normalizar_codigo_empresa(codigo: str) -> str:
    normalizado = codigo.strip().lower()
    if not _CODIGO_EMPRESA.fullmatch(normalizado):
        raise ValueError("El codigo de empresa no es valido.")
    return normalizado


def resolver_empresa_por_codigo(codigo: str) -> dict[str, object] | None:
    """El codigo es un selector publico, nunca una autorizacion privada."""
    try:
        normalizado = normalizar_codigo_empresa(codigo)
    except ValueError:
        return None

    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT id, codigo, nombre, estado
                FROM empresa
                WHERE codigo = %s
                LIMIT 1;
                """,
                (normalizado,),
            )
            empresa = cursor.fetchone()
            return dict(empresa) if empresa is not None else None
    finally:
        connection.close()


def exigir_empresa_id(usuario_actual: dict[str, object]) -> int:
    """Devuelve la empresa verificada por autenticacion, no una enviada por el cliente."""
    empresa_id = usuario_actual.get("empresa_id")
    if empresa_id is None:
        raise HTTPException(status_code=403, detail="Esta operacion requiere una cuenta de empresa.")
    try:
        return int(empresa_id)
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=403, detail="Contexto de empresa invalido.") from error


def exigir_empresa_publica(
    x_empresa_codigo: str | None = Header(default=None, alias="X-Empresa-Codigo"),
    request: Request = None,
) -> int:
    """Resuelve el catalogo publico sin crear una empresa por defecto implicita."""
    if not x_empresa_codigo:
        raise HTTPException(status_code=400, detail="Debe indicar el codigo de empresa.")
    empresa = resolver_empresa_por_codigo(x_empresa_codigo)
    if empresa is None or empresa["estado"] not in {"ACTIVA", "SUSPENDIDA"}:
        raise HTTPException(status_code=404, detail="Empresa no encontrada.")
    if request is not None:
        from app.core.permisos_empresa import es_operacion_nueva
        from app.core.plan_empresa import exigir_operaciones_empresa
        if es_operacion_nueva(request.method, request.url.path):
            exigir_operaciones_empresa(int(empresa["id"]))
    return int(empresa["id"])
