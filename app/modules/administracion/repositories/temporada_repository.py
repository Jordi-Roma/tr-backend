from psycopg2.extras import RealDictCursor
from app.database.connection import get_connection

def listar_temporadas() -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT id, nombre, anio, activo, fecha_creacion
            FROM temporada
            ORDER BY nombre ASC;
            """
        )
        return [dict(c) for c in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()

def obtener_temporada_por_id(temporada_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT id, nombre, anio, activo, fecha_creacion
            FROM temporada
            WHERE id = %s
            LIMIT 1;
            """,
            (temporada_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row is not None else None
    finally:
        cursor.close()
        connection.close()

def obtener_temporada_por_nombre_anio(nombre: str, anio: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT id
            FROM temporada
            WHERE lower(nombre) = lower(%s) AND anio = %s
            LIMIT 1;
            """,
            (nombre, anio),
        )
        row = cursor.fetchone()
        return dict(row) if row is not None else None
    finally:
        cursor.close()
        connection.close()

def crear_temporada(nombre: str, anio: int) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            INSERT INTO temporada (nombre, anio)
            VALUES (%s, %s)
            RETURNING id, nombre, anio, activo, fecha_creacion;
            """,
            (nombre, anio),
        )
        row = cursor.fetchone()
        connection.commit()
        return dict(row)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

def actualizar_temporada(temporada_id: int, nombre: str, anio: int) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            UPDATE temporada
            SET nombre = %s,
                anio = %s
            WHERE id = %s
            RETURNING id, nombre, anio, activo, fecha_creacion;
            """,
            (nombre, anio, temporada_id),
        )
        row = cursor.fetchone()
        connection.commit()
        return dict(row)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

def cambiar_estado_temporada(temporada_id: int, activo: bool) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            UPDATE temporada
            SET activo = %s
            WHERE id = %s
            RETURNING id, nombre, anio, activo, fecha_creacion;
            """,
            (activo, temporada_id),
        )
        row = cursor.fetchone()
        connection.commit()
        return dict(row)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()
