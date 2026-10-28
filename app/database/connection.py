import psycopg2
from psycopg2.extensions import connection

from app.core.config import DATABASE_URL


def get_connection() -> connection:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL no esta configurada.")

    # Las fechas de precios, promociones y citas usan el mismo día comercial
    # que el control de suscripciones, incluso si Railway tiene zona UTC.
    return psycopg2.connect(DATABASE_URL, options='-c timezone=America/La_Paz')
