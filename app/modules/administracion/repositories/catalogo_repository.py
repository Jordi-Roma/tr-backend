from psycopg2.extras import RealDictCursor

from app.database.connection import get_connection


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORÍAS
# ═══════════════════════════════════════════════════════════════════════════

def listar_categorias(*, empresa_id: int) -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT c.id, c.categoria_padre_id, cp.nombre AS categoria_padre_nombre, 
                   c.nombre, c.descripcion, c.activo, c.fecha_creacion
            FROM categoria c
            LEFT JOIN categoria cp ON cp.id = c.categoria_padre_id
            WHERE c.empresa_id = %s
            ORDER BY c.nombre ASC;
            """,
            (empresa_id,),
        )
        return [dict(c) for c in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def obtener_categoria_por_id(categoria_id: int, *, empresa_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT c.id, c.categoria_padre_id, cp.nombre AS categoria_padre_nombre,
                   c.nombre, c.descripcion, c.activo, c.fecha_creacion
            FROM categoria c
            LEFT JOIN categoria cp ON cp.id = c.categoria_padre_id
            WHERE c.empresa_id = %s AND c.id = %s
            LIMIT 1;
            """,
            (empresa_id, categoria_id),
        )
        row = cursor.fetchone()
        return dict(row) if row is not None else None
    finally:
        cursor.close()
        connection.close()


def obtener_descendientes_categoria(categoria_id: int, *, empresa_id: int) -> list[int]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            WITH RECURSIVE descendientes AS (
                SELECT id FROM categoria WHERE empresa_id = %s AND id = %s
                UNION ALL
                SELECT c.id FROM categoria c
                INNER JOIN descendientes d ON c.categoria_padre_id = d.id AND c.empresa_id = %s
            )
            SELECT id FROM descendientes WHERE id != %s;
            """,
            (empresa_id, categoria_id, empresa_id, categoria_id),
        )
        return [c['id'] for c in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def obtener_categoria_por_nombre(nombre: str, *, empresa_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre
            FROM categoria
            WHERE empresa_id = %s AND lower(nombre) = lower(%s)
            LIMIT 1;
            """,
            (empresa_id, nombre),
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
    *,
    empresa_id: int,
) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            INSERT INTO categoria (categoria_padre_id, nombre, descripcion, empresa_id)
            VALUES (%s, %s, %s, %s)
            RETURNING id, categoria_padre_id, nombre, descripcion, activo, fecha_creacion;
            """,
            (categoria_padre_id, nombre, descripcion, empresa_id),
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
    *,
    empresa_id: int,
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
            WHERE empresa_id = %s AND id = %s
            RETURNING id, categoria_padre_id, nombre, descripcion, activo, fecha_creacion;
            """,
            (categoria_padre_id, nombre, descripcion, empresa_id, categoria_id),
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


def desactivar_categoria(categoria_id: int, *, empresa_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            WITH RECURSIVE descendientes AS (
                SELECT id FROM categoria WHERE empresa_id = %s AND id = %s
                UNION ALL
                SELECT c.id FROM categoria c
                INNER JOIN descendientes d ON c.categoria_padre_id = d.id AND c.empresa_id = %s
            )
            UPDATE categoria
            SET activo = FALSE
            WHERE empresa_id = %s AND id IN (SELECT id FROM descendientes)
              AND activo = TRUE
            RETURNING id;
            """,
            (empresa_id, categoria_id, empresa_id, empresa_id),
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


def activar_categoria(categoria_id: int, *, empresa_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            WITH RECURSIVE descendientes AS (
                SELECT id FROM categoria WHERE empresa_id = %s AND id = %s
                UNION ALL
                SELECT c.id FROM categoria c
                INNER JOIN descendientes d ON c.categoria_padre_id = d.id AND c.empresa_id = %s
            )
            UPDATE categoria
            SET activo = TRUE
            WHERE empresa_id = %s AND id IN (SELECT id FROM descendientes)
              AND activo = FALSE
            RETURNING id, categoria_padre_id, nombre, descripcion, activo, fecha_creacion;
            """,
            (empresa_id, categoria_id, empresa_id, empresa_id),
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


def contar_productos_activos_por_categoria(categoria_id: int, *, empresa_id: int) -> int:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM producto
            WHERE empresa_id = %s AND categoria_id = %s
                AND activo = TRUE;
            """,
            (empresa_id, categoria_id),
        )
        row = cursor.fetchone()
        return int(row["total"]) if row else 0
    finally:
        cursor.close()
        connection.close()


# ═══════════════════════════════════════════════════════════════════════════
# TALLAS
# ═══════════════════════════════════════════════════════════════════════════

def listar_tallas(tipo_prenda: str | None = None, *, empresa_id: int) -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        query = """
            SELECT id, nombre, descripcion, tipo_prenda, ancho_cm, largo_cm, activo, fecha_creacion
            FROM talla WHERE empresa_id = %s
        """
        params = [empresa_id]
        if tipo_prenda is not None:
            query += " AND tipo_prenda = %s "
            params.append(tipo_prenda.strip().upper())
            
        query += " ORDER BY tipo_prenda ASC, id ASC;"
        cursor.execute(query, tuple(params))
        return [dict(t) for t in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def obtener_talla_por_id(talla_id: int, *, empresa_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, descripcion, tipo_prenda, ancho_cm, largo_cm, activo, fecha_creacion
            FROM talla
            WHERE empresa_id = %s AND id = %s
            LIMIT 1;
            """,
            (empresa_id, talla_id),
        )
        row = cursor.fetchone()
        return dict(row) if row is not None else None
    finally:
        cursor.close()
        connection.close()


def obtener_talla_por_nombre(nombre: str, *, empresa_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, tipo_prenda
            FROM talla
            WHERE empresa_id = %s AND lower(nombre) = lower(%s)
            LIMIT 1;
            """,
            (empresa_id, nombre),
        )
        row = cursor.fetchone()
        return dict(row) if row is not None else None
    finally:
        cursor.close()
        connection.close()


def obtener_talla_por_nombre_y_tipo(nombre: str, tipo_prenda: str, *, empresa_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, tipo_prenda
            FROM talla
            WHERE empresa_id = %s AND lower(nombre) = lower(%s) AND tipo_prenda = %s
            LIMIT 1;
            """,
            (empresa_id, nombre, tipo_prenda.strip().upper()),
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
    *,
    empresa_id: int,
) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            INSERT INTO talla (nombre, descripcion, tipo_prenda, ancho_cm, largo_cm, empresa_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, nombre, descripcion, tipo_prenda, ancho_cm, largo_cm, activo, fecha_creacion;
            """,
            (nombre, descripcion, tipo_prenda.strip().upper(), ancho_cm, largo_cm, empresa_id),
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
    *,
    empresa_id: int,
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
            WHERE empresa_id = %s AND id = %s
            RETURNING id, nombre, descripcion, tipo_prenda, ancho_cm, largo_cm, activo, fecha_creacion;
            """,
            (nombre, descripcion, tipo_prenda.strip().upper(), ancho_cm, largo_cm, empresa_id, talla_id),
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


def desactivar_talla(talla_id: int, *, empresa_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE talla
            SET activo = FALSE
            WHERE empresa_id = %s AND id = %s
                AND activo = TRUE
            RETURNING id;
            """,
            (empresa_id, talla_id),
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


def activar_talla(talla_id: int, *, empresa_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE talla
            SET activo = TRUE
            WHERE empresa_id = %s AND id = %s
            RETURNING id, nombre, descripcion, activo, fecha_creacion;
            """,
            (empresa_id, talla_id),
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


def contar_variantes_activas_por_talla(talla_id: int, *, empresa_id: int) -> int:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM producto_variante
            WHERE empresa_id = %s AND talla_id = %s
                AND activo = TRUE;
            """,
            (empresa_id, talla_id),
        )
        row = cursor.fetchone()
        return int(row["total"]) if row else 0
    finally:
        cursor.close()
        connection.close()


# ═══════════════════════════════════════════════════════════════════════════
# COLORES
# ═══════════════════════════════════════════════════════════════════════════

def listar_colores(*, empresa_id: int) -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, codigo_hex, activo, fecha_creacion
            FROM color
            WHERE empresa_id = %s
            ORDER BY nombre ASC;
            """,
            (empresa_id,),
        )
        return [dict(c) for c in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def obtener_color_por_id(color_id: int, *, empresa_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, codigo_hex, activo, fecha_creacion
            FROM color
            WHERE empresa_id = %s AND id = %s
            LIMIT 1;
            """,
            (empresa_id, color_id),
        )
        row = cursor.fetchone()
        return dict(row) if row is not None else None
    finally:
        cursor.close()
        connection.close()


def obtener_color_por_nombre(nombre: str, *, empresa_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre
            FROM color
            WHERE empresa_id = %s AND lower(nombre) = lower(%s)
            LIMIT 1;
            """,
            (empresa_id, nombre),
        )
        row = cursor.fetchone()
        return dict(row) if row is not None else None
    finally:
        cursor.close()
        connection.close()


def crear_color(
    nombre: str,
    codigo_hex: str | None,
    *,
    empresa_id: int,
) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            INSERT INTO color (nombre, codigo_hex, empresa_id)
            VALUES (%s, %s, %s)
            RETURNING id, nombre, codigo_hex, activo, fecha_creacion;
            """,
            (nombre, codigo_hex, empresa_id),
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
    *,
    empresa_id: int,
) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE color
            SET nombre = %s,
                codigo_hex = %s
            WHERE empresa_id = %s AND id = %s
            RETURNING id, nombre, codigo_hex, activo, fecha_creacion;
            """,
            (nombre, codigo_hex, empresa_id, color_id),
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


def desactivar_color(color_id: int, *, empresa_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE color
            SET activo = FALSE
            WHERE empresa_id = %s AND id = %s
                AND activo = TRUE
            RETURNING id;
            """,
            (empresa_id, color_id),
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


def activar_color(color_id: int, *, empresa_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE color
            SET activo = TRUE
            WHERE empresa_id = %s AND id = %s
            RETURNING id, nombre, codigo_hex, activo, fecha_creacion;
            """,
            (empresa_id, color_id),
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


def contar_variantes_activas_por_color(color_id: int, *, empresa_id: int) -> int:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM producto_variante
            WHERE empresa_id = %s AND color_id = %s
                AND activo = TRUE;
            """,
            (empresa_id, color_id),
        )
        row = cursor.fetchone()
        return int(row["total"]) if row else 0
    finally:
        cursor.close()
        connection.close()


# ═══════════════════════════════════════════════════════════════════════════
# MARCAS
# ═══════════════════════════════════════════════════════════════════════════

def listar_marcas(*, empresa_id: int) -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, descripcion, activo, fecha_creacion
            FROM marca
            WHERE empresa_id = %s
            ORDER BY nombre ASC;
            """,
            (empresa_id,),
        )
        return [dict(c) for c in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def obtener_marca_por_id(marca_id: int, *, empresa_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, descripcion, activo, fecha_creacion
            FROM marca
            WHERE empresa_id = %s AND id = %s
            LIMIT 1;
            """,
            (empresa_id, marca_id),
        )
        row = cursor.fetchone()
        return dict(row) if row is not None else None
    finally:
        cursor.close()
        connection.close()


def obtener_marca_por_nombre(nombre: str, *, empresa_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre
            FROM marca
            WHERE empresa_id = %s AND lower(nombre) = lower(%s)
            LIMIT 1;
            """,
            (empresa_id, nombre),
        )
        row = cursor.fetchone()
        return dict(row) if row is not None else None
    finally:
        cursor.close()
        connection.close()


def crear_marca(
    nombre: str,
    descripcion: str | None,
    *,
    empresa_id: int,
) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            INSERT INTO marca (nombre, descripcion, empresa_id)
            VALUES (%s, %s, %s)
            RETURNING id, nombre, descripcion, activo, fecha_creacion;
            """,
            (nombre, descripcion, empresa_id),
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
    *,
    empresa_id: int,
) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE marca
            SET nombre = %s,
                descripcion = %s
            WHERE empresa_id = %s AND id = %s
            RETURNING id, nombre, descripcion, activo, fecha_creacion;
            """,
            (nombre, descripcion, empresa_id, marca_id),
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


def desactivar_marca(marca_id: int, *, empresa_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE marca
            SET activo = FALSE
            WHERE empresa_id = %s AND id = %s
                AND activo = TRUE
            RETURNING id;
            """,
            (empresa_id, marca_id),
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


def activar_marca(marca_id: int, *, empresa_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE marca
            SET activo = TRUE
            WHERE empresa_id = %s AND id = %s
            RETURNING id, nombre, descripcion, activo, fecha_creacion;
            """,
            (empresa_id, marca_id),
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


def contar_productos_activos_por_marca(marca_id: int, *, empresa_id: int) -> int:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM producto
            WHERE empresa_id = %s AND marca_id = %s
                AND activo = TRUE;
            """,
            (empresa_id, marca_id),
        )
        row = cursor.fetchone()
        return int(row["total"]) if row else 0
    finally:
        cursor.close()
        connection.close()
