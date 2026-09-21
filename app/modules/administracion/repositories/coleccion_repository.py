from psycopg2.extras import RealDictCursor
from app.database.connection import get_connection

def listar_colecciones() -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT c.id, c.temporada_id, t.nombre as temporada_nombre, c.nombre, c.descripcion, c.activo, c.fecha_creacion
            FROM coleccion c
            INNER JOIN temporada t ON c.temporada_id = t.id
            ORDER BY c.nombre ASC;
            """
        )
        return [dict(c) for c in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()

def obtener_coleccion_por_id(coleccion_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT c.id, c.temporada_id, t.nombre as temporada_nombre, c.nombre, c.descripcion, c.activo, c.fecha_creacion
            FROM coleccion c
            INNER JOIN temporada t ON c.temporada_id = t.id
            WHERE c.id = %s
            LIMIT 1;
            """,
            (coleccion_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row is not None else None
    finally:
        cursor.close()
        connection.close()

def obtener_coleccion_por_temporada_nombre(temporada_id: int, nombre: str) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT id
            FROM coleccion
            WHERE temporada_id = %s AND lower(nombre) = lower(%s)
            LIMIT 1;
            """,
            (temporada_id, nombre),
        )
        row = cursor.fetchone()
        return dict(row) if row is not None else None
    finally:
        cursor.close()
        connection.close()

def crear_coleccion(temporada_id: int, nombre: str, descripcion: str | None) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            INSERT INTO coleccion (temporada_id, nombre, descripcion)
            VALUES (%s, %s, %s)
            RETURNING id, temporada_id, nombre, descripcion, activo, fecha_creacion;
            """,
            (temporada_id, nombre, descripcion),
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

def actualizar_coleccion(coleccion_id: int, temporada_id: int, nombre: str, descripcion: str | None) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            UPDATE coleccion
            SET temporada_id = %s,
                nombre = %s,
                descripcion = %s
            WHERE id = %s
            RETURNING id, temporada_id, nombre, descripcion, activo, fecha_creacion;
            """,
            (temporada_id, nombre, descripcion, coleccion_id),
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

def cambiar_estado_coleccion(coleccion_id: int, activo: bool) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            UPDATE coleccion
            SET activo = %s
            WHERE id = %s
            RETURNING id, temporada_id, nombre, descripcion, activo, fecha_creacion;
            """,
            (activo, coleccion_id),
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
