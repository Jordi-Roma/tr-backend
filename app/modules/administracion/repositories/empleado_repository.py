from app.core.plan_empresa import exigir_cupo_usuarios
from psycopg2.extras import RealDictCursor
from fastapi import HTTPException
from psycopg2.errors import UniqueViolation
from .control_comercial import preparar_escritura, validar_cuenta_comercial
from app.modules.autenticacion.repositories.perfil_repository import invalidar_accesos

from app.database.connection import get_connection
from app.core.plan_empresa import bloquear_empresa_y_obtener_limite

ROLES_LABORALES = ("CAJERO", "ENCARGADO_SUCURSAL", "PERSONAL_VENTAS")


def obtener_empleado_activo_por_usuario_id(
    usuario_id: int,
    empresa_id: int,
) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT e.id, e.usuario_id, e.sucursal_id, e.codigo_empleado, e.cargo, e.activo
            FROM empleado e JOIN sucursal s ON s.id=e.sucursal_id AND s.empresa_id=e.empresa_id
            WHERE e.usuario_id = %s AND e.empresa_id = %s
                AND e.activo = TRUE AND s.activo = TRUE
            LIMIT 1;
            """,
            (usuario_id, empresa_id),
        )
        empleado = cursor.fetchone()

        if empleado is None:
            return None

        return dict(empleado)
    finally:
        cursor.close()
        connection.close()


def listar_empleados(empresa_id: int, sucursal_id: int | None = None, incluir_inactivos: bool = False) -> list[dict[str, object]]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        parametros: tuple[object, ...] = (empresa_id, incluir_inactivos)
        filtro_sucursal = ""

        if sucursal_id is not None:
            filtro_sucursal = "AND e.sucursal_id = %s"
            parametros = (empresa_id, incluir_inactivos, sucursal_id)

        cursor.execute(
            f"""
            SELECT
                e.id AS empleado_id,
                u.id AS usuario_id,
                u.nombre,
                u.apellido,
                u.username,
                u.correo,
                s.id AS sucursal_id,
                s.nombre AS sucursal_nombre,
                e.codigo_empleado,
                e.cargo,
                e.fecha_ingreso,
                e.activo,
                e.rol_laboral,
                COALESCE(
                    array_agg(r.nombre) FILTER (WHERE r.nombre IS NOT NULL),
                    ARRAY[]::VARCHAR[]
                ) AS roles
            FROM empleado e
            INNER JOIN usuario u ON u.id = e.usuario_id AND u.empresa_id = e.empresa_id
            INNER JOIN sucursal s ON s.id = e.sucursal_id AND s.empresa_id = e.empresa_id
            LEFT JOIN usuario_rol ur
                ON ur.usuario_id = u.id
                AND ur.activo = TRUE
            LEFT JOIN rol r
                ON r.id = ur.rol_id
                AND r.activo = TRUE
            WHERE e.empresa_id = %s AND (%s OR (e.activo AND u.activo AND s.activo))
                {filtro_sucursal}
            GROUP BY
                e.id,
                u.id,
                u.nombre,
                u.apellido,
                u.username,
                u.correo,
                s.id,
                s.nombre,
                e.codigo_empleado,
                e.cargo,
                e.fecha_ingreso,
                e.activo
            ORDER BY e.id ASC;
            """,
            parametros,
        )
        return [dict(empleado) for empleado in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def obtener_empleado_por_id(empleado_id: int, empresa_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT
                e.id AS empleado_id,
                u.id AS usuario_id,
                u.nombre,
                u.apellido,
                u.username,
                u.correo,
                s.id AS sucursal_id,
                s.nombre AS sucursal_nombre,
                e.codigo_empleado,
                e.cargo,
                e.fecha_ingreso,
                e.activo,
                e.rol_laboral,
                COALESCE(
                    array_agg(r.nombre) FILTER (WHERE r.nombre IS NOT NULL),
                    ARRAY[]::VARCHAR[]
                ) AS roles
            FROM empleado e
            INNER JOIN usuario u ON u.id = e.usuario_id AND u.empresa_id = e.empresa_id
            INNER JOIN sucursal s ON s.id = e.sucursal_id AND s.empresa_id = e.empresa_id
            LEFT JOIN usuario_rol ur
                ON ur.usuario_id = u.id
                AND ur.activo = TRUE
            LEFT JOIN rol r
                ON r.id = ur.rol_id
                AND r.activo = TRUE
            WHERE e.id = %s AND e.empresa_id = %s
            GROUP BY
                e.id,
                u.id,
                u.nombre,
                u.apellido,
                u.username,
                u.correo,
                s.id,
                s.nombre,
                e.codigo_empleado,
                e.cargo,
                e.fecha_ingreso,
                e.activo
            LIMIT 1;
            """,
            (empleado_id, empresa_id),
        )
        empleado = cursor.fetchone()

        if empleado is None:
            return None

        return dict(empleado)
    finally:
        cursor.close()
        connection.close()


def obtener_usuario_por_id(usuario_id: int, empresa_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, apellido, username, correo, activo
            FROM usuario
            WHERE id = %s AND empresa_id = %s
            LIMIT 1;
            """,
            (usuario_id, empresa_id),
        )
        usuario = cursor.fetchone()

        if usuario is None:
            return None

        return dict(usuario)
    finally:
        cursor.close()
        connection.close()


def obtener_usuario_por_username(username: str) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, username
            FROM usuario
            WHERE lower(username) = lower(%s)
            LIMIT 1;
            """,
            (username,),
        )
        usuario = cursor.fetchone()

        if usuario is None:
            return None

        return dict(usuario)
    finally:
        cursor.close()
        connection.close()


def obtener_usuario_por_correo(correo: str) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, correo
            FROM usuario
            WHERE lower(correo) = lower(%s)
            LIMIT 1;
            """,
            (correo,),
        )
        usuario = cursor.fetchone()

        if usuario is None:
            return None

        return dict(usuario)
    finally:
        cursor.close()
        connection.close()


def obtener_sucursal_por_id(sucursal_id: int, empresa_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, direccion, telefono, activo
            FROM sucursal
            WHERE id = %s AND empresa_id = %s
            LIMIT 1;
            """,
            (sucursal_id, empresa_id),
        )
        sucursal = cursor.fetchone()

        if sucursal is None:
            return None

        return dict(sucursal)
    finally:
        cursor.close()
        connection.close()


def obtener_rol_por_nombre(nombre: str) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nombre, activo
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


def usuario_tiene_empleado_activo(usuario_id: int, empresa_id: int) -> bool:
    return obtener_empleado_activo_por_usuario_id(usuario_id, empresa_id) is not None


def crear_empleado_usuario_existente(
    usuario_id: int,
    sucursal_id: int,
    codigo_empleado: str,
    cargo: str,
    rol_id: int,
    usuario_admin_id: int,
    empresa_id: int,
) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        preparar_escritura(cursor, usuario_admin_id, empresa_id, "empleados:crear", nueva=True)
        validar_cuenta_comercial(cursor, usuario_id, empresa_id)
        limite = bloquear_empresa_y_obtener_limite(cursor, empresa_id, "empleados")
        cursor.execute("SELECT count(*) AS total FROM empleado WHERE empresa_id = %s AND activo = TRUE", (empresa_id,))
        if limite is not None and int(cursor.fetchone()["total"]) >= limite:
            raise HTTPException(status_code=403, detail="Se alcanzo el limite de empleados del plan.")
        cursor.execute(
            """
            INSERT INTO empleado (usuario_id, sucursal_id, codigo_empleado, cargo, empresa_id, rol_laboral)
            SELECT u.id, s.id, %s, %s, %s, (SELECT nombre FROM rol WHERE id=%s) FROM usuario u JOIN sucursal s ON s.empresa_id = u.empresa_id
            WHERE u.id = %s AND s.id = %s AND u.empresa_id = %s AND u.activo = TRUE AND s.activo = TRUE
            RETURNING id;
            """,
            (codigo_empleado, cargo, empresa_id, rol_id, usuario_id, sucursal_id, empresa_id),
        )
        empleado = cursor.fetchone()
        if empleado is None:
            raise HTTPException(400, "Usuario o sucursal fuera de la empresa o inactivo.")

        desactivar_roles_laborales_con_cursor(cursor, usuario_id)
        asignar_rol_con_cursor(cursor, usuario_id, rol_id)
        registrar_bitacora_con_cursor(
            cursor,
            usuario_admin_id,
            "REGISTRO_EMPLEADO",
            "Registro de empleado usando usuario existente.",
        )

        invalidar_accesos(cursor, usuario_id, empresa_id)
        connection.commit()
        return obtener_empleado_por_id(int(empleado["id"]), empresa_id)
    except UniqueViolation as error:
        connection.rollback()
        raise HTTPException(409, "El usuario, correo o código ya está registrado en su empresa. Si el empleado está inactivo, reactívelo.") from error
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def crear_usuario_empleado(
    nombre: str,
    apellido: str,
    username: str,
    correo: str,
    password_hash: str,
    sucursal_id: int,
    codigo_empleado: str,
    cargo: str,
    rol_id: int,
    usuario_admin_id: int,
    empresa_id: int,
) -> dict[str, object]:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        preparar_escritura(cursor, usuario_admin_id, empresa_id, "empleados:crear", nueva=True)
        exigir_cupo_usuarios(cursor, empresa_id)
        limite = bloquear_empresa_y_obtener_limite(cursor, empresa_id, "empleados")
        cursor.execute("SELECT count(*) AS total FROM empleado WHERE empresa_id = %s AND activo = TRUE", (empresa_id,))
        if limite is not None and int(cursor.fetchone()["total"]) >= limite:
            raise HTTPException(status_code=403, detail="Se alcanzo el limite de empleados del plan.")
        cursor.execute("SELECT 1 FROM sucursal WHERE id = %s AND empresa_id = %s AND activo = TRUE FOR SHARE", (sucursal_id, empresa_id))
        if cursor.fetchone() is None:
            raise HTTPException(400, "Sucursal fuera de la empresa o inactiva.")
        cursor.execute(
            """
            INSERT INTO usuario (
                nombre,
                apellido,
                username,
                correo,
                password_hash,
                activo,
                empresa_id
            )
            VALUES (%s, %s, %s, %s, %s, TRUE, %s)
            RETURNING id;
            """,
            (nombre, apellido, username, correo, password_hash, empresa_id),
        )
        usuario = cursor.fetchone()
        usuario_id = int(usuario["id"])

        cursor.execute(
            """
            INSERT INTO empleado (usuario_id, sucursal_id, codigo_empleado, cargo, empresa_id, rol_laboral)
            VALUES (%s, %s, %s, %s, %s, (SELECT nombre FROM rol WHERE id=%s))
            RETURNING id;
            """,
            (usuario_id, sucursal_id, codigo_empleado, cargo, empresa_id, rol_id),
        )
        empleado = cursor.fetchone()

        asignar_rol_con_cursor(cursor, usuario_id, rol_id)
        registrar_bitacora_con_cursor(
            cursor,
            usuario_admin_id,
            "REGISTRO_EMPLEADO",
            "Registro de usuario nuevo como empleado.",
        )

        connection.commit()
        return obtener_empleado_por_id(int(empleado["id"]), empresa_id)
    except UniqueViolation as error:
        connection.rollback()
        raise HTTPException(409, "El usuario, correo o código ya está registrado en su empresa. Si el empleado está inactivo, reactívelo.") from error
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def actualizar_empleado(
    empleado_id: int,
    sucursal_id: int,
    codigo_empleado: str,
    cargo: str,
    rol_id: int,
    usuario_admin_id: int,
    empresa_id: int,
) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        preparar_escritura(cursor, usuario_admin_id, empresa_id, "empleados:editar", nueva=True)
        cursor.execute("SELECT usuario_id FROM empleado WHERE id=%s AND empresa_id=%s", (empleado_id, empresa_id))
        objetivo = cursor.fetchone()
        if objetivo:
            validar_cuenta_comercial(cursor, objetivo['usuario_id'], empresa_id)
        cursor.execute(
            """
            UPDATE empleado
            SET sucursal_id = %s,
                codigo_empleado = %s,
                cargo = %s,
                rol_laboral = (SELECT nombre FROM rol WHERE id=%s)
            WHERE id = %s AND empresa_id = %s
                AND activo = TRUE
                AND EXISTS (SELECT 1 FROM sucursal s WHERE s.id = %s AND s.empresa_id = %s AND s.activo = TRUE)
            RETURNING usuario_id;
            """,
            (sucursal_id, codigo_empleado, cargo, rol_id, empleado_id, empresa_id, sucursal_id, empresa_id),
        )
        empleado = cursor.fetchone()

        if empleado is None:
            connection.rollback()
            return None

        usuario_id = int(empleado["usuario_id"])
        desactivar_roles_laborales_con_cursor(cursor, usuario_id)
        asignar_rol_con_cursor(cursor, usuario_id, rol_id)
        registrar_bitacora_con_cursor(
            cursor,
            usuario_admin_id,
            "ACTUALIZACION_EMPLEADO",
            "Actualizacion de empleado.",
        )

        invalidar_accesos(cursor, int(empleado["usuario_id"]), empresa_id)
        connection.commit()
        return obtener_empleado_por_id(empleado_id, empresa_id)
    except UniqueViolation as error:
        connection.rollback()
        raise HTTPException(409, "El usuario, correo o código ya está registrado en su empresa. Si el empleado está inactivo, reactívelo.") from error
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def desactivar_empleado(empleado_id: int, usuario_admin_id: int, empresa_id: int) -> bool:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        preparar_escritura(cursor, usuario_admin_id, empresa_id, "empleados:desactivar", nueva=False)
        cursor.execute("SELECT usuario_id FROM empleado WHERE id=%s AND empresa_id=%s", (empleado_id, empresa_id))
        objetivo = cursor.fetchone()
        if objetivo:
            validar_cuenta_comercial(cursor, objetivo['usuario_id'], empresa_id)
        cursor.execute(
            """
            UPDATE empleado
            SET activo = FALSE
            WHERE id = %s AND empresa_id = %s
                AND activo = TRUE
            RETURNING usuario_id;
            """,
            (empleado_id, empresa_id),
        )
        empleado = cursor.fetchone()

        if empleado is None:
            connection.rollback()
            return False

        desactivar_roles_laborales_con_cursor(cursor, int(empleado["usuario_id"]))
        registrar_bitacora_con_cursor(
            cursor,
            usuario_admin_id,
            "DESACTIVACION_EMPLEADO",
            "Desactivacion de empleado.",
        )

        invalidar_accesos(cursor, int(empleado["usuario_id"]), empresa_id)
        connection.commit()
        return True
    except UniqueViolation as error:
        connection.rollback()
        raise HTTPException(409, "El usuario, correo o código ya está registrado en su empresa. Si el empleado está inactivo, reactívelo.") from error
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def activar_empleado(
    empleado_id: int,
    rol_id: int,
    usuario_admin_id: int,
    empresa_id: int,
) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        preparar_escritura(cursor, usuario_admin_id, empresa_id, "empleados:editar", nueva=True)
        limite = bloquear_empresa_y_obtener_limite(cursor, empresa_id, "empleados")
        cursor.execute("SELECT count(*) AS total FROM empleado WHERE empresa_id = %s AND activo = TRUE", (empresa_id,))
        if limite is not None and int(cursor.fetchone()["total"]) >= limite:
            raise HTTPException(status_code=403, detail="Se alcanzo el limite de empleados del plan.")
        cursor.execute("SELECT usuario_id FROM empleado WHERE id=%s AND empresa_id=%s", (empleado_id, empresa_id))
        objetivo = cursor.fetchone()
        if objetivo:
            validar_cuenta_comercial(cursor, objetivo['usuario_id'], empresa_id)
        cursor.execute(
            """
            UPDATE empleado
            SET activo = TRUE, rol_laboral = (SELECT nombre FROM rol WHERE id=%s)
            WHERE id = %s AND empresa_id = %s AND activo = FALSE
              AND EXISTS (SELECT 1 FROM sucursal s WHERE s.id = empleado.sucursal_id AND s.empresa_id = %s AND s.activo = TRUE)
            RETURNING usuario_id;
            """,
            (rol_id, empleado_id, empresa_id, empresa_id),
        )
        empleado = cursor.fetchone()

        if empleado is None:
            connection.rollback()
            return None

        usuario_id = int(empleado["usuario_id"])
        desactivar_roles_laborales_con_cursor(cursor, usuario_id)
        asignar_rol_con_cursor(cursor, usuario_id, rol_id)
        registrar_bitacora_con_cursor(
            cursor,
            usuario_admin_id,
            "ACTIVACION_EMPLEADO",
            "Activacion de empleado.",
        )

        invalidar_accesos(cursor, int(empleado["usuario_id"]), empresa_id)
        connection.commit()
        return obtener_empleado_por_id(empleado_id, empresa_id)
    except UniqueViolation as error:
        connection.rollback()
        raise HTTPException(409, "El usuario, correo o código ya está registrado en su empresa. Si el empleado está inactivo, reactívelo.") from error
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def asignar_rol_con_cursor(
    cursor: RealDictCursor,
    usuario_id: int,
    rol_id: int,
) -> None:
    cursor.execute('SELECT nombre FROM rol WHERE id=%s AND activo', (rol_id,))
    rol = cursor.fetchone()
    if not rol or rol['nombre'] not in ROLES_LABORALES:
        raise HTTPException(400, 'Rol laboral no autorizado o inactivo.')
    cursor.execute(
        """
        UPDATE usuario_rol
        SET activo = TRUE
        WHERE usuario_id = %s
            AND rol_id = %s;
        """,
        (usuario_id, rol_id),
    )

    if cursor.rowcount == 0:
        cursor.execute(
            """
            INSERT INTO usuario_rol (usuario_id, rol_id, activo)
            VALUES (%s, %s, TRUE);
            """,
            (usuario_id, rol_id),
        )


def desactivar_rol_laboral_usuario(usuario_id: int, rol_id: int) -> None:
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE usuario_rol
            SET activo = FALSE
            WHERE usuario_id = %s
                AND rol_id = %s
                AND activo = TRUE;
            """,
            (usuario_id, rol_id),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def desactivar_roles_laborales_con_cursor(
    cursor: RealDictCursor,
    usuario_id: int,
) -> None:
    cursor.execute(
        """
        UPDATE usuario_rol ur
        SET activo = FALSE
        FROM rol r
        WHERE r.id = ur.rol_id
            AND ur.usuario_id = %s
            AND r.nombre = ANY(%s)
            AND ur.activo = TRUE;
        """,
        (usuario_id, list(ROLES_LABORALES)),
    )


def registrar_bitacora(
    usuario_id: int,
    accion: str,
    descripcion: str,
) -> None:
    connection = get_connection()
    cursor = connection.cursor()

    try:
        registrar_bitacora_con_cursor(cursor, usuario_id, accion, descripcion)
        connection.commit()
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
            "ADMINISTRACION_COMERCIAL",
            descripcion,
            "EXITOSO",
        ),
    )
