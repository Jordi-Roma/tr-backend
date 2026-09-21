from psycopg2.extras import RealDictCursor

from app.database.connection import get_connection


def obtener_usuario_por_identificador(identificador: str) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, apellido, username, correo, activo
            FROM usuario
            WHERE lower(correo) = lower(%s)
               OR username = lower(%s)
            LIMIT 1;
            """,
            (identificador, identificador),
        )
        usuario = cursor.fetchone()
        return dict(usuario) if usuario is not None else None
    finally:
        cursor.close()
        connection.close()


def guardar_token_reset(usuario_id: int, token_hash: str, minutos_expiracion: int) -> None:
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE password_reset_token
            SET usado = TRUE,
                fecha_uso = CURRENT_TIMESTAMP
            WHERE usuario_id = %s
              AND usado = FALSE;
            """,
            (usuario_id,),
        )
        cursor.execute(
            """
            INSERT INTO password_reset_token (
                usuario_id,
                token_hash,
                fecha_expiracion
            )
            VALUES (
                %s,
                %s,
                CURRENT_TIMESTAMP + (%s || ' minutes')::INTERVAL
            );
            """,
            (usuario_id, token_hash, minutos_expiracion),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def consumir_token_reset(usuario_id: int, token_hash: str, password_hash: str) -> bool:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id
            FROM password_reset_token
            WHERE usuario_id = %s
              AND token_hash = %s
              AND usado = FALSE
              AND fecha_expiracion > CURRENT_TIMESTAMP
            ORDER BY fecha_creacion DESC
            LIMIT 1;
            """,
            (usuario_id, token_hash),
        )
        token = cursor.fetchone()

        if token is None:
            connection.rollback()
            return False

        cursor.execute(
            """
            UPDATE usuario
            SET password_hash = %s,
                intentos_fallidos = 0,
                bloqueado_hasta = NULL
            WHERE id = %s;
            """,
            (password_hash, usuario_id),
        )
        cursor.execute(
            """
            UPDATE password_reset_token
            SET usado = TRUE,
                fecha_uso = CURRENT_TIMESTAMP
            WHERE id = %s;
            """,
            (token["id"],),
        )
        cursor.execute(
            """
            UPDATE sesion
            SET activa = FALSE,
                fecha_cierre = CURRENT_TIMESTAMP
            WHERE usuario_id = %s
              AND activa = TRUE
              AND fecha_cierre IS NULL;
            """,
            (usuario_id,),
        )
        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()
