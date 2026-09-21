from psycopg2.extras import RealDictCursor

from app.database.connection import get_connection


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORÍAS
# ═══════════════════════════════════════════════════════════════════════════

def listar_categorias() -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT c.id, c.categoria_padre_id, cp.nombre AS categoria_padre_nombre, 
                   c.nombre, c.descripcion, c.activo, c.fecha_creacion
            FROM categoria c
            LEFT JOIN categoria cp ON cp.id = c.categoria_padre_id
            ORDER BY c.nombre ASC;
            """
        )
        return [dict(c) for c in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def obtener_categoria_por_id(categoria_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT c.id, c.categoria_padre_id, cp.nombre AS categoria_padre_nombre,
                   c.nombre, c.descripcion, c.activo, c.fecha_creacion
            FROM categoria c
            LEFT JOIN categoria cp ON cp.id = c.categoria_padre_id
            WHERE c.id = %s
            LIMIT 1;
            """,
            (categoria_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row is not None else None
    finally:
        cursor.close()
        connection.close()


def obtener_descendientes_categoria(categoria_id: int) -> list[int]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            WITH RECURSIVE descendientes AS (
                SELECT id FROM categoria WHERE id = %s
                UNION ALL
                SELECT c.id FROM categoria c
                INNER JOIN descendientes d ON c.categoria_padre_id = d.id
            )
            SELECT id FROM descendientes WHERE id != %s;
            """,
            (categoria_id, categoria_id),
        )
        return [c['id'] for c in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def obtener_categoria_por_nombre(nombre: str) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre
            FROM categoria
            WHERE lower(nombre) = lower(%s)
            LIMIT 1;
            """,
            (nombre,),
        )
        row = cursor.fetchone()
        return dict(row) if row is not None else None
    finally:
        cursor.close()
        connection.close()


def crear_categoria(
    categoria_padre_id: int | None,
    nombre: str,
    descripcion: str | None,
) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            INSERT INTO categoria (categoria_padre_id, nombre, descripcion)
            VALUES (%s, %s, %s)
            RETURNING id, categoria_padre_id, nombre, descripcion, activo, fecha_creacion;
            """,
            (categoria_padre_id, nombre, descripcion),
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


def actualizar_categoria(
    categoria_id: int,
    categoria_padre_id: int | None,
    nombre: str,
    descripcion: str | None,
) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE categoria
            SET categoria_padre_id = %s,
                nombre = %s,
                descripcion = %s
            WHERE id = %s
            RETURNING id, categoria_padre_id, nombre, descripcion, activo, fecha_creacion;
            """,
            (categoria_padre_id, nombre, descripcion, categoria_id),
        )
        row = cursor.fetchone()

        if row is None:
            connection.rollback()
            return None

        connection.commit()
        return dict(row)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def desactivar_categoria(categoria_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            WITH RECURSIVE descendientes AS (
                SELECT id FROM categoria WHERE id = %s
                UNION ALL
                SELECT c.id FROM categoria c
                INNER JOIN descendientes d ON c.categoria_padre_id = d.id
            )
            UPDATE categoria
            SET activo = FALSE
            WHERE id IN (SELECT id FROM descendientes)
              AND activo = TRUE
            RETURNING id;
            """,
            (categoria_id,),
        )
        rows = cursor.fetchall()

        if not rows:
            connection.rollback()
            return False

        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def activar_categoria(categoria_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            WITH RECURSIVE descendientes AS (
                SELECT id FROM categoria WHERE id = %s
                UNION ALL
                SELECT c.id FROM categoria c
                INNER JOIN descendientes d ON c.categoria_padre_id = d.id
            )
            UPDATE categoria
            SET activo = TRUE
            WHERE id IN (SELECT id FROM descendientes)
              AND activo = FALSE
            RETURNING id, categoria_padre_id, nombre, descripcion, activo, fecha_creacion;
            """,
            (categoria_id,),
        )
        rows = cursor.fetchall()
        
        # Obtenemos la categoría raíz que fue activada (para mantener compatibilidad con el retorno)
        row = next((r for r in rows if r['id'] == categoria_id), None)

        if row is None:
            connection.rollback()
            return None

        connection.commit()
        return dict(row)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def contar_productos_activos_por_categoria(categoria_id: int) -> int:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM producto
            WHERE categoria_id = %s
                AND activo = TRUE;
            """,
            (categoria_id,),
        )
        row = cursor.fetchone()
        return int(row["total"]) if row else 0
    finally:
        cursor.close()
        connection.close()


# ═══════════════════════════════════════════════════════════════════════════
# TALLAS
# ═══════════════════════════════════════════════════════════════════════════

def listar_tallas(tipo_prenda: str | None = None) -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        query = """
            SELECT id, nombre, descripcion, tipo_prenda, ancho_cm, largo_cm, activo, fecha_creacion
            FROM talla
        """
        params = []
        if tipo_prenda is not None:
            query += " WHERE tipo_prenda = %s "
            params.append(tipo_prenda.strip().upper())
            
        query += " ORDER BY tipo_prenda ASC, id ASC;"
        cursor.execute(query, tuple(params))
        return [dict(t) for t in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def obtener_talla_por_id(talla_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, descripcion, tipo_prenda, ancho_cm, largo_cm, activo, fecha_creacion
            FROM talla
            WHERE id = %s
            LIMIT 1;
            """,
            (talla_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row is not None else None
    finally:
        cursor.close()
        connection.close()


def obtener_talla_por_nombre(nombre: str) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, tipo_prenda
            FROM talla
            WHERE lower(nombre) = lower(%s)
            LIMIT 1;
            """,
            (nombre,),
        )
        row = cursor.fetchone()
        return dict(row) if row is not None else None
    finally:
        cursor.close()
        connection.close()


def obtener_talla_por_nombre_y_tipo(nombre: str, tipo_prenda: str) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, tipo_prenda
            FROM talla
            WHERE lower(nombre) = lower(%s) AND tipo_prenda = %s
            LIMIT 1;
            """,
            (nombre, tipo_prenda.strip().upper()),
        )
        row = cursor.fetchone()
        return dict(row) if row is not None else None
    finally:
        cursor.close()
        connection.close()


def crear_talla(
    nombre: str,
    descripcion: str | None,
    tipo_prenda: str = "SUPERIOR",
    ancho_cm: float | None = None,
    largo_cm: float | None = None,
) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            INSERT INTO talla (nombre, descripcion, tipo_prenda, ancho_cm, largo_cm)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, nombre, descripcion, tipo_prenda, ancho_cm, largo_cm, activo, fecha_creacion;
            """,
            (nombre, descripcion, tipo_prenda.strip().upper(), ancho_cm, largo_cm),
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


def actualizar_talla(
    talla_id: int,
    nombre: str,
    descripcion: str | None,
    tipo_prenda: str = "SUPERIOR",
    ancho_cm: float | None = None,
    largo_cm: float | None = None,
) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE talla
            SET nombre = %s,
                descripcion = %s,
                tipo_prenda = %s,
                ancho_cm = %s,
                largo_cm = %s
            WHERE id = %s
            RETURNING id, nombre, descripcion, tipo_prenda, ancho_cm, largo_cm, activo, fecha_creacion;
            """,
            (nombre, descripcion, tipo_prenda.strip().upper(), ancho_cm, largo_cm, talla_id),
        )
        row = cursor.fetchone()

        if row is None:
            connection.rollback()
            return None

        connection.commit()
        return dict(row)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def desactivar_talla(talla_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE talla
            SET activo = FALSE
            WHERE id = %s
                AND activo = TRUE
            RETURNING id;
            """,
            (talla_id,),
        )
        row = cursor.fetchone()

        if row is None:
            connection.rollback()
            return False

        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def activar_talla(talla_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE talla
            SET activo = TRUE
            WHERE id = %s
            RETURNING id, nombre, descripcion, activo, fecha_creacion;
            """,
            (talla_id,),
        )
        row = cursor.fetchone()

        if row is None:
            connection.rollback()
            return None

        connection.commit()
        return dict(row)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def contar_variantes_activas_por_talla(talla_id: int) -> int:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM producto_variante
            WHERE talla_id = %s
                AND activo = TRUE;
            """,
            (talla_id,),
        )
        row = cursor.fetchone()
        return int(row["total"]) if row else 0
    finally:
        cursor.close()
        connection.close()


# ═══════════════════════════════════════════════════════════════════════════
# COLORES
# ═══════════════════════════════════════════════════════════════════════════

def listar_colores() -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, codigo_hex, activo, fecha_creacion
            FROM color
            ORDER BY nombre ASC;
            """
        )
        return [dict(c) for c in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def obtener_color_por_id(color_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, codigo_hex, activo, fecha_creacion
            FROM color
            WHERE id = %s
            LIMIT 1;
            """,
            (color_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row is not None else None
    finally:
        cursor.close()
        connection.close()


def obtener_color_por_nombre(nombre: str) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre
            FROM color
            WHERE lower(nombre) = lower(%s)
            LIMIT 1;
            """,
            (nombre,),
        )
        row = cursor.fetchone()
        return dict(row) if row is not None else None
    finally:
        cursor.close()
        connection.close()


def crear_color(
    nombre: str,
    codigo_hex: str | None,
) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            INSERT INTO color (nombre, codigo_hex)
            VALUES (%s, %s)
            RETURNING id, nombre, codigo_hex, activo, fecha_creacion;
            """,
            (nombre, codigo_hex),
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


def actualizar_color(
    color_id: int,
    nombre: str,
    codigo_hex: str | None,
) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE color
            SET nombre = %s,
                codigo_hex = %s
            WHERE id = %s
            RETURNING id, nombre, codigo_hex, activo, fecha_creacion;
            """,
            (nombre, codigo_hex, color_id),
        )
        row = cursor.fetchone()

        if row is None:
            connection.rollback()
            return None

        connection.commit()
        return dict(row)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def desactivar_color(color_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE color
            SET activo = FALSE
            WHERE id = %s
                AND activo = TRUE
            RETURNING id;
            """,
            (color_id,),
        )
        row = cursor.fetchone()

        if row is None:
            connection.rollback()
            return False

        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def activar_color(color_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE color
            SET activo = TRUE
            WHERE id = %s
            RETURNING id, nombre, codigo_hex, activo, fecha_creacion;
            """,
            (color_id,),
        )
        row = cursor.fetchone()

        if row is None:
            connection.rollback()
            return None

        connection.commit()
        return dict(row)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def contar_variantes_activas_por_color(color_id: int) -> int:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM producto_variante
            WHERE color_id = %s
                AND activo = TRUE;
            """,
            (color_id,),
        )
        row = cursor.fetchone()
        return int(row["total"]) if row else 0
    finally:
        cursor.close()
        connection.close()


# ═══════════════════════════════════════════════════════════════════════════
# MARCAS
# ═══════════════════════════════════════════════════════════════════════════

def listar_marcas() -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, descripcion, activo, fecha_creacion
            FROM marca
            ORDER BY nombre ASC;
            """
        )
        return [dict(c) for c in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def obtener_marca_por_id(marca_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, descripcion, activo, fecha_creacion
            FROM marca
            WHERE id = %s
            LIMIT 1;
            """,
            (marca_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row is not None else None
    finally:
        cursor.close()
        connection.close()


def obtener_marca_por_nombre(nombre: str) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre
            FROM marca
            WHERE lower(nombre) = lower(%s)
            LIMIT 1;
            """,
            (nombre,),
        )
        row = cursor.fetchone()
        return dict(row) if row is not None else None
    finally:
        cursor.close()
        connection.close()


def crear_marca(
    nombre: str,
    descripcion: str | None,
) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            INSERT INTO marca (nombre, descripcion)
            VALUES (%s, %s)
            RETURNING id, nombre, descripcion, activo, fecha_creacion;
            """,
            (nombre, descripcion),
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


def actualizar_marca(
    marca_id: int,
    nombre: str,
    descripcion: str | None,
) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE marca
            SET nombre = %s,
                descripcion = %s
            WHERE id = %s
            RETURNING id, nombre, descripcion, activo, fecha_creacion;
            """,
            (nombre, descripcion, marca_id),
        )
        row = cursor.fetchone()

        if row is None:
            connection.rollback()
            return None

        connection.commit()
        return dict(row)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def desactivar_marca(marca_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE marca
            SET activo = FALSE
            WHERE id = %s
                AND activo = TRUE
            RETURNING id;
            """,
            (marca_id,),
        )
        row = cursor.fetchone()

        if row is None:
            connection.rollback()
            return False

        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def activar_marca(marca_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE marca
            SET activo = TRUE
            WHERE id = %s
            RETURNING id, nombre, descripcion, activo, fecha_creacion;
            """,
            (marca_id,),
        )
        row = cursor.fetchone()

        if row is None:
            connection.rollback()
            return None

        connection.commit()
        return dict(row)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def contar_productos_activos_por_marca(marca_id: int) -> int:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM producto
            WHERE marca_id = %s
                AND activo = TRUE;
            """,
            (marca_id,),
        )
        row = cursor.fetchone()
        return int(row["total"]) if row else 0
    finally:
        cursor.close()
        connection.close()
