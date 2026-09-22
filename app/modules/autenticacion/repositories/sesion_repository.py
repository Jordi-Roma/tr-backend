from psycopg2.extras import RealDictCursor

from app.core.config import ACCESS_TOKEN_EXPIRE_MINUTES
from app.database.connection import get_connection
from app.modules.autenticacion.repositories.bitacora_repository import registrar_bitacora


def obtener_usuario_para_login(identificador: str) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT
                id,
                nombre,
                apellido,
                username,
                correo,
                password_hash,
                intentos_fallidos,
                bloqueado_hasta,
                activo
            FROM usuario
            WHERE lower(correo) = lower(%s)
               OR username = lower(%s)
            LIMIT 1;
            """,
            (identificador, identificador),
        )
        usuario = cursor.fetchone()

        if usuario is None:
            return None

        usuario_dict = dict(usuario)
        usuario_id = usuario_dict["id"]

        cursor.execute(
            """
            SELECT r.nombre
            FROM rol r
            INNER JOIN usuario_rol ur ON ur.rol_id = r.id
            WHERE ur.usuario_id = %s
              AND ur.activo = TRUE
              AND r.activo = TRUE
            ORDER BY r.nombre;
            """,
            (usuario_id,),
        )
        roles = cursor.fetchall()
        usuario_dict["roles"] = [str(rol["nombre"]) for rol in roles]

        return usuario_dict
    finally:
        cursor.close()
        connection.close()


def incrementar_intento_fallido(usuario_id: int) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            UPDATE usuario
            SET
                intentos_fallidos = intentos_fallidos + 1,
                bloqueado_hasta = CASE
                    WHEN intentos_fallidos + 1 >= 5
                    THEN CURRENT_TIMESTAMP + INTERVAL '3 minutes'
                    ELSE bloqueado_hasta
                END
            WHERE id = %s
            RETURNING intentos_fallidos, bloqueado_hasta;
            """,
            (usuario_id,),
        )
        resultado = cursor.fetchone()
        connection.commit()

        if resultado is None:
            raise ValueError("No se pudo actualizar el intento fallido.")

        return dict(resultado)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def reiniciar_intentos_login(usuario_id: int) -> None:
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE usuario
            SET intentos_fallidos = 0,
                bloqueado_hasta = NULL
            WHERE id = %s;
            """,
            (usuario_id,),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def crear_sesion(
    usuario_id: int,
    refresh_token_hash: str | None = None,
) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            INSERT INTO sesion (
                usuario_id,
                refresh_token_hash,
                fecha_expiracion,
                activa
            )
            VALUES (
                %s,
                %s,
                CURRENT_TIMESTAMP + (%s * INTERVAL '1 minute'),
                TRUE
            )
            RETURNING id, fecha_inicio, fecha_expiracion;
            """,
            (usuario_id, refresh_token_hash, ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        sesion = cursor.fetchone()
        connection.commit()

        if sesion is None:
            raise ValueError("No se pudo crear la sesion.")

        return dict(sesion)
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def cerrar_sesion_activa(usuario_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE sesion
            SET activa = FALSE,
                fecha_cierre = CURRENT_TIMESTAMP
            WHERE id = (
                SELECT id
                FROM sesion
                WHERE usuario_id = %s
                  AND activa = TRUE
                  AND fecha_cierre IS NULL
                ORDER BY fecha_inicio DESC
                LIMIT 1
            );
            """,
            (usuario_id,),
        )
        sesion_actualizada = cursor.rowcount > 0
        connection.commit()

        return sesion_actualizada
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def cerrar_sesion_por_id(sesion_id: int, usuario_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE sesion
            SET activa = FALSE,
                fecha_cierre = CURRENT_TIMESTAMP
            WHERE id = %s
              AND usuario_id = %s
              AND activa = TRUE
              AND fecha_cierre IS NULL;
            """,
            (sesion_id, usuario_id),
        )
        actualizada = cursor.rowcount > 0
        connection.commit()
        return actualizada
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def sesion_esta_activa(sesion_id: int, usuario_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT 1
            FROM sesion
            WHERE id = %s
              AND usuario_id = %s
              AND activa = TRUE
              AND fecha_cierre IS NULL
              AND fecha_expiracion > CURRENT_TIMESTAMP
            LIMIT 1;
            """,
            (sesion_id, usuario_id),
        )
        return cursor.fetchone() is not None
    finally:
        cursor.close()
        connection.close()


def registrar_bitacora_login(
    usuario_id: int | None,
    accion: str,
    resultado: str,
    descripcion: str,
    direccion_ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Delegacion al repositorio central de bitacora."""
    registrar_bitacora(
        usuario_id=usuario_id,
        accion=accion,
        modulo="AUTENTICACION",
        resultado=resultado,
        descripcion=descripcion,
        direccion_ip=direccion_ip,
        user_agent=user_agent,
    )
