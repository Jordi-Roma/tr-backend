from psycopg2.extras import RealDictCursor

from app.database.connection import get_connection


def listar_roles() -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT
                r.id,
                r.nombre,
                r.descripcion,
                r.activo,
                COUNT(rp.permiso_id) FILTER (
                    WHERE rp.activo = TRUE
                        AND p.activo = TRUE
                ) AS cantidad_permisos
            FROM rol r
            LEFT JOIN rol_permiso rp
                ON rp.rol_id = r.id
            LEFT JOIN permiso p
                ON p.id = rp.permiso_id
            WHERE r.activo = TRUE
            GROUP BY r.id, r.nombre, r.descripcion, r.activo
            ORDER BY r.id ASC;
            """
        )
        return [dict(rol) for rol in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def obtener_rol_por_id(rol_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, descripcion, activo
            FROM rol
            WHERE id = %s
            LIMIT 1;
            """,
            (rol_id,),
        )
        rol = cursor.fetchone()

        if rol is None:
            return None

        return dict(rol)
    finally:
        cursor.close()
        connection.close()


def obtener_rol_por_nombre(nombre: str) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, descripcion, activo
            FROM rol
            WHERE nombre = %s
            LIMIT 1;
            """,
            (nombre,),
        )
        rol = cursor.fetchone()

        if rol is None:
            return None

        return dict(rol)
    finally:
        cursor.close()
        connection.close()


def crear_rol(
    nombre: str,
    descripcion: str | None,
    usuario_id: int,
) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            INSERT INTO rol (nombre, descripcion)
            VALUES (%s, %s)
            RETURNING id, nombre, descripcion, activo;
            """,
            (nombre, descripcion),
        )
        rol = cursor.fetchone()

        registrar_bitacora_con_cursor(
            cursor,
            usuario_id,
            "CREACION_ROL",
            "Creacion de rol.",
        )

        connection.commit()
        return dict(rol)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def actualizar_rol(
    rol_id: int,
    nombre: str,
    descripcion: str | None,
    usuario_id: int,
) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE rol
            SET nombre = %s,
                descripcion = %s
            WHERE id = %s
                AND activo = TRUE
            RETURNING id, nombre, descripcion, activo;
            """,
            (nombre, descripcion, rol_id),
        )
        rol = cursor.fetchone()

        if rol is None:
            connection.rollback()
            return None

        registrar_bitacora_con_cursor(
            cursor,
            usuario_id,
            "ACTUALIZACION_ROL",
            "Actualizacion de rol.",
        )

        connection.commit()
        return dict(rol)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def desactivar_rol(rol_id: int, usuario_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE rol
            SET activo = FALSE
            WHERE id = %s
                AND activo = TRUE;
            """,
            (rol_id,),
        )
        desactivado = cursor.rowcount > 0

        if desactivado:
            registrar_bitacora_con_cursor(
                cursor,
                usuario_id,
                "DESACTIVACION_ROL",
                "Desactivacion de rol.",
            )
            connection.commit()
        else:
            connection.rollback()

        return desactivado
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def activar_rol(rol_id: int, usuario_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE rol
            SET activo = TRUE
            WHERE id = %s;
            """,
            (rol_id,),
        )
        activado = cursor.rowcount > 0

        if activado:
            registrar_bitacora_con_cursor(
                cursor,
                usuario_id,
                "ACTIVACION_ROL",
                "Activacion de rol.",
            )
            connection.commit()
        else:
            connection.rollback()

        return activado
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def listar_permisos() -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, modulo, accion, descripcion, activo
            FROM permiso
            WHERE activo = TRUE
            ORDER BY modulo ASC, accion ASC, id ASC;
            """
        )
        return [dict(permiso) for permiso in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def listar_permisos_de_rol(rol_id: int) -> list[int]:
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT rp.permiso_id
            FROM rol_permiso rp
            INNER JOIN permiso p
                ON p.id = rp.permiso_id
            WHERE rp.rol_id = %s
                AND rp.activo = TRUE
                AND p.activo = TRUE
            ORDER BY rp.permiso_id ASC;
            """,
            (rol_id,),
        )
        return [int(row[0]) for row in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def reemplazar_permisos_de_rol(
    rol_id: int,
    permiso_ids: list[int],
    usuario_id: int,
) -> list[int]:
    permiso_ids_unicos = sorted(set(permiso_ids))
    connection = get_connection()
    cursor = connection.cursor()

    try:
        if permiso_ids_unicos:
            cursor.execute(
                """
                SELECT id
                FROM permiso
                WHERE activo = TRUE
                    AND id = ANY(%s);
                """,
                (permiso_ids_unicos,),
            )
            permisos_validos = {int(row[0]) for row in cursor.fetchall()}
        else:
            permisos_validos = set()

        if len(permisos_validos) != len(permiso_ids_unicos):
            raise ValueError("Uno o mas permisos no existen o estan inactivos.")

        cursor.execute(
            """
            UPDATE rol_permiso
            SET activo = FALSE
            WHERE rol_id = %s;
            """,
            (rol_id,),
        )

        for permiso_id in permiso_ids_unicos:
            cursor.execute(
                """
                INSERT INTO rol_permiso (rol_id, permiso_id, activo)
                VALUES (%s, %s, TRUE)
                ON CONFLICT (rol_id, permiso_id)
                DO UPDATE SET
                    activo = TRUE,
                    fecha_asignacion = CURRENT_TIMESTAMP;
                """,
                (rol_id, permiso_id),
            )

        registrar_bitacora_con_cursor(
            cursor,
            usuario_id,
            "ACTUALIZACION_PERMISOS_ROL",
            "Actualizacion de permisos asignados a un rol.",
        )

        connection.commit()
        return permiso_ids_unicos
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def obtener_permiso_por_id(permiso_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, modulo, accion, descripcion, activo
            FROM permiso
            WHERE id = %s
            LIMIT 1;
            """,
            (permiso_id,),
        )
        permiso = cursor.fetchone()

        if permiso is None:
            return None

        return dict(permiso)
    finally:
        cursor.close()
        connection.close()


def obtener_permiso_por_nombre(nombre: str) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, modulo, accion, descripcion, activo
            FROM permiso
            WHERE nombre = %s
            LIMIT 1;
            """,
            (nombre,),
        )
        permiso = cursor.fetchone()

        if permiso is None:
            return None

        return dict(permiso)
    finally:
        cursor.close()
        connection.close()


def obtener_permiso_por_modulo_accion(
    modulo: str,
    accion: str,
) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, modulo, accion, descripcion, activo
            FROM permiso
            WHERE modulo = %s
                AND accion = %s
            LIMIT 1;
            """,
            (modulo, accion),
        )
        permiso = cursor.fetchone()

        if permiso is None:
            return None

        return dict(permiso)
    finally:
        cursor.close()
        connection.close()


def crear_permiso(
    nombre: str,
    modulo: str,
    accion: str,
    descripcion: str | None,
    usuario_id: int,
) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            INSERT INTO permiso (nombre, modulo, accion, descripcion)
            VALUES (%s, %s, %s, %s)
            RETURNING id, nombre, modulo, accion, descripcion, activo;
            """,
            (nombre, modulo, accion, descripcion),
        )
        permiso = cursor.fetchone()

        registrar_bitacora_con_cursor(
            cursor,
            usuario_id,
            "CREACION_PERMISO",
            "Creacion de permiso.",
        )

        connection.commit()
        return dict(permiso)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def desactivar_permiso(permiso_id: int, usuario_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE permiso
            SET activo = FALSE
            WHERE id = %s
                AND activo = TRUE;
            """,
            (permiso_id,),
        )
        desactivado = cursor.rowcount > 0

        if desactivado:
            registrar_bitacora_con_cursor(
                cursor,
                usuario_id,
                "DESACTIVACION_PERMISO",
                "Desactivacion de permiso.",
            )
            connection.commit()
        else:
            connection.rollback()

        return desactivado
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def activar_permiso(permiso_id: int, usuario_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE permiso
            SET activo = TRUE
            WHERE id = %s;
            """,
            (permiso_id,),
        )
        activado = cursor.rowcount > 0

        if activado:
            registrar_bitacora_con_cursor(
                cursor,
                usuario_id,
                "ACTIVACION_PERMISO",
                "Activacion de permiso.",
            )
            connection.commit()
        else:
            connection.rollback()

        return activado
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def asignar_permiso_a_rol(
    rol_id: int,
    permiso_id: int,
    usuario_id: int,
) -> bool:
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE rol_permiso
            SET activo = TRUE
            WHERE rol_id = %s
                AND permiso_id = %s;
            """,
            (rol_id, permiso_id),
        )

        if cursor.rowcount == 0:
            cursor.execute(
                """
                INSERT INTO rol_permiso (rol_id, permiso_id, activo)
                VALUES (%s, %s, TRUE);
                """,
                (rol_id, permiso_id),
            )

        registrar_bitacora_con_cursor(
            cursor,
            usuario_id,
            "ASIGNACION_PERMISO_ROL",
            "Asignacion de permiso a rol.",
        )

        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def desactivar_permiso_de_rol(
    rol_id: int,
    permiso_id: int,
    usuario_id: int,
) -> bool:
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE rol_permiso
            SET activo = FALSE
            WHERE rol_id = %s
                AND permiso_id = %s
                AND activo = TRUE;
            """,
            (rol_id, permiso_id),
        )
        desactivado = cursor.rowcount > 0

        if desactivado:
            registrar_bitacora_con_cursor(
                cursor,
                usuario_id,
                "DESACTIVACION_PERMISO_ROL",
                "Desactivacion de permiso de rol.",
            )
            connection.commit()
        else:
            connection.rollback()

        return desactivado
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def activar_permiso_de_rol(
    rol_id: int,
    permiso_id: int,
    usuario_id: int,
) -> bool:
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE rol_permiso
            SET activo = TRUE
            WHERE rol_id = %s
                AND permiso_id = %s;
            """,
            (rol_id, permiso_id),
        )

        if cursor.rowcount == 0:
            cursor.execute(
                """
                INSERT INTO rol_permiso (rol_id, permiso_id, activo)
                VALUES (%s, %s, TRUE);
                """,
                (rol_id, permiso_id),
            )

        registrar_bitacora_con_cursor(
            cursor,
            usuario_id,
            "ACTIVACION_PERMISO_ROL",
            "Activacion de permiso de rol.",
        )

        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def registrar_bitacora_con_cursor(
    cursor: RealDictCursor,
    usuario_id: int,
    accion: str,
    descripcion: str,
) -> None:
    cursor.execute(
        """
        INSERT INTO bitacora (
            usuario_id,
            accion,
            modulo,
            descripcion,
            resultado
        )
        VALUES (%s, %s, %s, %s, %s);
        """,
        (
            usuario_id,
            accion,
            "AUTENTICACION",
            descripcion,
            "EXITOSO",
        ),
    )
