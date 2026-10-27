from psycopg2.extras import RealDictCursor
from app.database.connection import get_connection

def listar_colecciones(empresa_id: int) -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT c.id, c.temporada_id, t.nombre as temporada_nombre, c.nombre, c.descripcion, c.activo, c.fecha_creacion
            FROM coleccion c
            INNER JOIN temporada t ON c.temporada_id = t.id AND t.empresa_id = c.empresa_id
            WHERE c.empresa_id = %s
            ORDER BY c.nombre ASC;
            """, (empresa_id,)
        )
        return [dict(c) for c in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()

def obtener_coleccion_por_id(coleccion_id: int, empresa_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT c.id, c.temporada_id, t.nombre as temporada_nombre, c.nombre, c.descripcion, c.activo, c.fecha_creacion
            FROM coleccion c
            INNER JOIN temporada t ON c.temporada_id = t.id AND t.empresa_id = c.empresa_id
            WHERE c.id = %s AND c.empresa_id = %s
            LIMIT 1;
            """,
            (coleccion_id, empresa_id),
        )
        row = cursor.fetchone()
        return dict(row) if row is not None else None
    finally:
        cursor.close()
        connection.close()

def obtener_coleccion_por_temporada_nombre(temporada_id: int, nombre: str, empresa_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT id
            FROM coleccion
            WHERE temporada_id = %s AND public.normalizar_nombre_catalogo(nombre) COLLATE "C" = public.normalizar_nombre_catalogo(%s) COLLATE "C" AND empresa_id = %s
            LIMIT 1;
            """,
            (temporada_id, nombre, empresa_id),
        )
        row = cursor.fetchone()
        return dict(row) if row is not None else None
    finally:
        cursor.close()
        connection.close()

def crear_coleccion(temporada_id: int, nombre: str, descripcion: str | None, empresa_id: int) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            INSERT INTO coleccion (temporada_id, nombre, descripcion, empresa_id)
            SELECT t.id, %s, %s, t.empresa_id FROM temporada t
            WHERE t.id = %s AND t.empresa_id = %s AND t.activo = TRUE
            RETURNING id, temporada_id, nombre, descripcion, activo, fecha_creacion;
            """,
            (nombre, descripcion, temporada_id, empresa_id),
        )
        row = cursor.fetchone()
        connection.commit()
        return dict(row) if row is not None else None
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

def actualizar_coleccion(coleccion_id: int, temporada_id: int, nombre: str, descripcion: str | None,
                         empresa_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            UPDATE coleccion
            SET temporada_id = %s,
                nombre = %s,
                descripcion = %s
            WHERE id = %s AND empresa_id = %s
              AND EXISTS (SELECT 1 FROM temporada t WHERE t.id = %s AND t.empresa_id = %s AND t.activo = TRUE)
            RETURNING id, temporada_id, nombre, descripcion, activo, fecha_creacion;
            """,
            (temporada_id, nombre, descripcion, coleccion_id, empresa_id, temporada_id, empresa_id),
        )
        row = cursor.fetchone()
        connection.commit()
        return dict(row) if row is not None else None
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

def cambiar_estado_coleccion(coleccion_id: int, activo: bool, empresa_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            UPDATE coleccion
            SET activo = %s
            WHERE id = %s AND empresa_id = %s
            RETURNING id, temporada_id, nombre, descripcion, activo, fecha_creacion;
            """,
            (activo, coleccion_id, empresa_id),
        )
        row = cursor.fetchone()
        connection.commit()
        return dict(row) if row is not None else None
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()
