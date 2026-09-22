from psycopg2.extras import RealDictCursor

from app.database.connection import get_connection


def listar_proveedores() -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT
                p.id,
                p.nombre,
                p.nit,
                p.telefono,
                p.correo,
                p.direccion,
                p.activo,
                p.fecha_creacion,
                COALESCE(
                    ARRAY_AGG(pu.usuario_id ORDER BY pu.usuario_id)
                        FILTER (WHERE pu.usuario_id IS NOT NULL AND pu.activo = TRUE),
                    ARRAY[]::BIGINT[]
                ) AS usuarios_ids
            FROM proveedor p
            LEFT JOIN proveedor_usuario pu
                ON pu.proveedor_id = p.id
                AND pu.activo = TRUE
            GROUP BY p.id
            ORDER BY p.nombre ASC;
            """
        )
        return [dict(proveedor) for proveedor in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def obtener_proveedor_por_id(proveedor_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT
                p.id,
                p.nombre,
                p.nit,
                p.telefono,
                p.correo,
                p.direccion,
                p.activo,
                p.fecha_creacion,
                COALESCE(
                    ARRAY_AGG(pu.usuario_id ORDER BY pu.usuario_id)
                        FILTER (WHERE pu.usuario_id IS NOT NULL AND pu.activo = TRUE),
                    ARRAY[]::BIGINT[]
                ) AS usuarios_ids
            FROM proveedor p
            LEFT JOIN proveedor_usuario pu
                ON pu.proveedor_id = p.id
                AND pu.activo = TRUE
            WHERE p.id = %s
            GROUP BY p.id
            LIMIT 1;
            """,
            (proveedor_id,),
        )
        proveedor = cursor.fetchone()

        if proveedor is None:
            return None

        return dict(proveedor)
    finally:
        cursor.close()
        connection.close()


def obtener_proveedor_por_nit(nit: str) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nit
            FROM proveedor
            WHERE nit = %s
            LIMIT 1;
            """,
            (nit,),
        )
        proveedor = cursor.fetchone()

        if proveedor is None:
            return None

        return dict(proveedor)
    finally:
        cursor.close()
        connection.close()


def crear_proveedor(
    nombre: str,
    nit: str | None,
    telefono: str | None,
    correo: str | None,
    direccion: str | None,
) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            INSERT INTO proveedor (nombre, nit, telefono, correo, direccion)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, nombre, nit, telefono, correo, direccion, activo, fecha_creacion, ARRAY[]::BIGINT[] AS usuarios_ids;
            """,
            (nombre, nit, telefono, correo, direccion),
        )
        proveedor = cursor.fetchone()
        connection.commit()
        return dict(proveedor)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def actualizar_proveedor(
    proveedor_id: int,
    nombre: str,
    telefono: str | None,
    correo: str | None,
    direccion: str | None,
) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE proveedor
            SET nombre = %s,
                telefono = %s,
                correo = %s,
                direccion = %s
            WHERE id = %s
            RETURNING id, nombre, nit, telefono, correo, direccion, activo, fecha_creacion,
                ARRAY(
                    SELECT usuario_id
                    FROM proveedor_usuario
                    WHERE proveedor_id = proveedor.id AND activo = TRUE
                    ORDER BY usuario_id
                ) AS usuarios_ids;
            """,
            (nombre, telefono, correo, direccion, proveedor_id),
        )
        proveedor = cursor.fetchone()

        if proveedor is None:
            connection.rollback()
            return None

        connection.commit()
        return dict(proveedor)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def desactivar_proveedor(proveedor_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE proveedor
            SET activo = FALSE
            WHERE id = %s
                AND activo = TRUE
            RETURNING id;
            """,
            (proveedor_id,),
        )
        proveedor = cursor.fetchone()

        if proveedor is None:
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


def activar_proveedor(proveedor_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE proveedor
            SET activo = TRUE
            WHERE id = %s
            RETURNING id, nombre, nit, telefono, correo, direccion, activo, fecha_creacion,
                ARRAY(
                    SELECT usuario_id
                    FROM proveedor_usuario
                    WHERE proveedor_id = proveedor.id AND activo = TRUE
                    ORDER BY usuario_id
                ) AS usuarios_ids;
            """,
            (proveedor_id,),
        )
        proveedor = cursor.fetchone()

        if proveedor is None:
            connection.rollback()
            return None

        connection.commit()
        return dict(proveedor)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def vincular_usuario_proveedor(proveedor_id: int, usuario_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute("SELECT id FROM proveedor WHERE id = %s AND activo = TRUE;", (proveedor_id,))
        if cursor.fetchone() is None:
            connection.rollback()
            return False

        cursor.execute("SELECT id FROM usuario WHERE id = %s AND activo = TRUE;", (usuario_id,))
        if cursor.fetchone() is None:
            connection.rollback()
            return False

        cursor.execute(
            """
            INSERT INTO proveedor_usuario (proveedor_id, usuario_id, activo)
            VALUES (%s, %s, TRUE)
            ON CONFLICT (proveedor_id, usuario_id) DO UPDATE
            SET activo = TRUE;
            """,
            (proveedor_id, usuario_id),
        )
        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def desvincular_usuario_proveedor(proveedor_id: int, usuario_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE proveedor_usuario
            SET activo = FALSE
            WHERE proveedor_id = %s
              AND usuario_id = %s
              AND activo = TRUE
            RETURNING proveedor_id;
            """,
            (proveedor_id, usuario_id),
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


def obtener_proveedor_por_usuario(usuario_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT p.id, p.nombre, p.nit, p.telefono, p.correo, p.direccion, p.activo, p.fecha_creacion
            FROM proveedor_usuario pu
            JOIN proveedor p ON p.id = pu.proveedor_id
            WHERE pu.usuario_id = %s
              AND pu.activo = TRUE
              AND p.activo = TRUE
            ORDER BY p.id ASC
            LIMIT 1;
            """,
            (usuario_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        cursor.close()
        connection.close()


def listar_productos_proveedor_panel(proveedor_id: int) -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT
                p.id AS producto_id,
                p.nombre,
                ca.nombre AS categoria,
                m.nombre AS marca,
                p.material,
                p.genero,
                pp.costo_referencia,
                p.activo,
                COUNT(pv.id)::INT AS variantes
            FROM producto_proveedor pp
            JOIN producto p ON p.id = pp.producto_id
            JOIN categoria ca ON ca.id = p.categoria_id
            LEFT JOIN marca m ON m.id = p.marca_id
            LEFT JOIN producto_variante pv
                ON pv.producto_id = p.id
                AND pv.activo = TRUE
            WHERE pp.proveedor_id = %s
              AND pp.activo = TRUE
            GROUP BY p.id, ca.nombre, m.nombre, pp.costo_referencia
            ORDER BY p.nombre ASC;
            """,
            (proveedor_id,),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def listar_stock_proveedor_panel(proveedor_id: int) -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT
                inv.sucursal_id,
                s.nombre AS sucursal,
                ci.nombre AS ciudad,
                p.id AS producto_id,
                p.nombre AS producto,
                pv.id AS producto_variante_id,
                pv.sku,
                t.nombre AS talla,
                co.nombre AS color,
                inv.stock_disponible,
                inv.stock_reservado,
                (inv.stock_disponible - inv.stock_reservado)::INT AS stock_real,
                inv.stock_minimo,
                ((inv.stock_disponible - inv.stock_reservado) <= inv.stock_minimo) AS bajo_stock
            FROM producto_proveedor pp
            JOIN producto p ON p.id = pp.producto_id
            JOIN producto_variante pv ON pv.producto_id = p.id
            JOIN talla t ON t.id = pv.talla_id
            JOIN color co ON co.id = pv.color_id
            JOIN inventario_sucursal inv
                ON inv.producto_variante_id = pv.id
                AND inv.activo = TRUE
            JOIN sucursal s ON s.id = inv.sucursal_id
            JOIN ciudad ci ON ci.id = s.ciudad_id
            WHERE pp.proveedor_id = %s
              AND pp.activo = TRUE
              AND p.activo = TRUE
              AND pv.activo = TRUE
            ORDER BY ci.nombre ASC, s.nombre ASC, p.nombre ASC, t.nombre ASC, co.nombre ASC;
            """,
            (proveedor_id,),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def listar_entregas_proveedor_panel(proveedor_id: int) -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT
                mi.id,
                mi.fecha_movimiento,
                s.nombre AS sucursal,
                ci.nombre AS ciudad,
                p.id AS producto_id,
                p.nombre AS producto,
                pv.id AS producto_variante_id,
                pv.sku,
                t.nombre AS talla,
                co.nombre AS color,
                mi.cantidad,
                mi.stock_anterior,
                mi.stock_nuevo,
                mi.motivo
            FROM movimiento_inventario mi
            JOIN producto_variante pv ON pv.id = mi.producto_variante_id
            JOIN producto p ON p.id = pv.producto_id
            JOIN talla t ON t.id = pv.talla_id
            JOIN color co ON co.id = pv.color_id
            JOIN sucursal s ON s.id = mi.sucursal_id
            JOIN ciudad ci ON ci.id = s.ciudad_id
            WHERE mi.proveedor_id = %s
              AND mi.tipo = 'ENTRADA'
              AND mi.activo = TRUE
            ORDER BY mi.fecha_movimiento DESC, mi.id DESC;
            """,
            (proveedor_id,),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()
