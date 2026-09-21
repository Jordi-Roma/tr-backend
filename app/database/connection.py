import psycopg2
from psycopg2.extensions import connection

from app.core.config import DATABASE_URL


def get_connection() -> connection:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL no esta configurada.")

    return psycopg2.connect(DATABASE_URL)
