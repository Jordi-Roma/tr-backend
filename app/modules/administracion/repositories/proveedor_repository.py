from psycopg2.extras import RealDictCursor
from psycopg2.errors import UniqueViolation
from fastapi import HTTPException
from contextlib import contextmanager
from .control_comercial import preparar_escritura, validar_cuenta_comercial, asignar_rol, retirar_rol_proveedor_sin_vinculo
from app.modules.autenticacion.repositories.perfil_repository import _transaccion, invalidar_accesos
from app.core.plan_empresa import exigir_cupo_usuarios

from app.database.connection import get_connection


def listar_proveedores(empresa_id: int) -> list[dict[str, object]]:
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
                AND pu.empresa_id = p.empresa_id
                AND pu.activo = TRUE
            WHERE p.empresa_id = %s
            GROUP BY p.id
            ORDER BY p.nombre ASC;
            """, (empresa_id,)
        )
        return [dict(proveedor) for proveedor in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def obtener_proveedor_por_id(proveedor_id: int, empresa_id: int) -> dict[str, object] | None:
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
                AND pu.empresa_id = p.empresa_id
                AND pu.activo = TRUE
            WHERE p.id = %s AND p.empresa_id = %s
            GROUP BY p.id
            LIMIT 1;
            """,
            (proveedor_id, empresa_id),
        )
        proveedor = cursor.fetchone()

        if proveedor is None:
            return None

        return dict(proveedor)
    finally:
        cursor.close()
        connection.close()


def obtener_proveedor_por_nit(nit: str, empresa_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT id, nit
            FROM proveedor
            WHERE nit = %s AND empresa_id = %s
            LIMIT 1;
            """,
            (nit, empresa_id),
        )
        proveedor = cursor.fetchone()

        if proveedor is None:
            return None

        return dict(proveedor)
    finally:
        cursor.close()
        connection.close()


@contextmanager
def _escritura(usuario_admin_id, empresa_id, accion, nueva=True):
    try:
        with _transaccion() as cur:
            preparar_escritura(cur, usuario_admin_id, empresa_id, accion, nueva)
            yield cur
    except UniqueViolation as error:
        raise HTTPException(409, 'El NIT, usuario, correo o vínculo ya está registrado en su empresa.') from error


def _auditar(cur, usuario_id, accion, proveedor_id):
    cur.execute("""INSERT INTO bitacora(usuario_id,accion,modulo,descripcion,resultado)
        VALUES(%s,%s,'PROVEEDORES',%s,'EXITOSO')""",
        (usuario_id, accion, f'Proveedor id={proveedor_id}'))


def _proveedor_activo(cur, proveedor_id, empresa_id):
    cur.execute('SELECT id FROM proveedor WHERE id=%s AND empresa_id=%s AND activo FOR UPDATE', (proveedor_id, empresa_id))
    if not cur.fetchone():
        raise HTTPException(404, 'Proveedor activo no encontrado en su empresa.')


def crear_proveedor(nombre, nit, telefono, correo, direccion, empresa_id, usuario_admin_id):
    with _escritura(usuario_admin_id, empresa_id, 'proveedores:crear') as cur:
        cur.execute("""INSERT INTO proveedor(nombre,nit,telefono,correo,direccion,empresa_id)
            VALUES(%s,%s,%s,%s,%s,%s) RETURNING id""", (nombre,nit,telefono,correo,direccion,empresa_id))
        pid=cur.fetchone()['id']
        _auditar(cur,usuario_admin_id,'CREAR_PROVEEDOR',pid)
    return obtener_proveedor_por_id(pid,empresa_id)


def actualizar_proveedor(proveedor_id,nombre,telefono,correo,direccion,empresa_id,usuario_admin_id):
    with _escritura(usuario_admin_id,empresa_id,'proveedores:editar') as cur:
        _proveedor_activo(cur,proveedor_id,empresa_id)
        cur.execute('UPDATE proveedor SET nombre=%s,telefono=%s,correo=%s,direccion=%s WHERE id=%s AND empresa_id=%s',
                    (nombre,telefono,correo,direccion,proveedor_id,empresa_id))
        _auditar(cur,usuario_admin_id,'EDITAR_PROVEEDOR',proveedor_id)
    return obtener_proveedor_por_id(proveedor_id,empresa_id)


def desactivar_proveedor(proveedor_id,empresa_id,usuario_admin_id):
    with _escritura(usuario_admin_id,empresa_id,'proveedores:desactivar',nueva=False) as cur:
        _proveedor_activo(cur,proveedor_id,empresa_id)
        cur.execute('UPDATE proveedor SET activo=FALSE WHERE id=%s AND empresa_id=%s',(proveedor_id,empresa_id))
        cur.execute('SELECT usuario_id FROM proveedor_usuario WHERE proveedor_id=%s AND empresa_id=%s AND activo',(proveedor_id,empresa_id))
        for row in cur.fetchall():
            retirar_rol_proveedor_sin_vinculo(cur,row['usuario_id'],empresa_id)
        _auditar(cur,usuario_admin_id,'DESACTIVAR_PROVEEDOR',proveedor_id)
    return True


def activar_proveedor(proveedor_id,empresa_id,usuario_admin_id):
    with _escritura(usuario_admin_id,empresa_id,'proveedores:editar') as cur:
        cur.execute('UPDATE proveedor SET activo=TRUE WHERE id=%s AND empresa_id=%s RETURNING id',(proveedor_id,empresa_id))
        if not cur.fetchone():
            return None
        cur.execute('''SELECT pu.usuario_id FROM proveedor_usuario pu JOIN usuario u ON u.id=pu.usuario_id AND u.empresa_id=pu.empresa_id
            WHERE pu.proveedor_id=%s AND pu.empresa_id=%s AND pu.activo AND u.activo''',(proveedor_id,empresa_id))
        for row in cur.fetchall():
            asignar_rol(cur,row['usuario_id'],'PROVEEDOR')
            invalidar_accesos(cur,row['usuario_id'],empresa_id)
        _auditar(cur,usuario_admin_id,'ACTIVAR_PROVEEDOR',proveedor_id)
    return obtener_proveedor_por_id(proveedor_id,empresa_id)


def vincular_usuario_proveedor(proveedor_id,usuario_id,empresa_id,usuario_admin_id):
    with _escritura(usuario_admin_id,empresa_id,'proveedores:editar') as cur:
        _proveedor_activo(cur,proveedor_id,empresa_id)
        validar_cuenta_comercial(cur,usuario_id,empresa_id)
        cur.execute('SELECT proveedor_id FROM proveedor_usuario WHERE usuario_id=%s AND activo AND proveedor_id<>%s',(usuario_id,proveedor_id))
        if cur.fetchone():
            raise HTTPException(409,'La cuenta ya está vinculada a otro proveedor. Retire primero ese vínculo.')
        cur.execute('''INSERT INTO proveedor_usuario(proveedor_id,usuario_id,empresa_id,activo) VALUES(%s,%s,%s,TRUE)
            ON CONFLICT(proveedor_id,usuario_id) DO UPDATE SET activo=TRUE''',(proveedor_id,usuario_id,empresa_id))
        asignar_rol(cur,usuario_id,'PROVEEDOR')
        invalidar_accesos(cur,usuario_id,empresa_id)
        _auditar(cur,usuario_admin_id,'VINCULAR_USUARIO_PROVEEDOR',proveedor_id)
    return True


def desvincular_usuario_proveedor(proveedor_id,usuario_id,empresa_id,usuario_admin_id):
    with _escritura(usuario_admin_id,empresa_id,'proveedores:editar',nueva=False) as cur:
        cur.execute('UPDATE proveedor_usuario SET activo=FALSE WHERE proveedor_id=%s AND usuario_id=%s AND empresa_id=%s AND activo RETURNING usuario_id',(proveedor_id,usuario_id,empresa_id))
        if not cur.fetchone():
            return False
        retirar_rol_proveedor_sin_vinculo(cur,usuario_id,empresa_id)
        _auditar(cur,usuario_admin_id,'DESVINCULAR_USUARIO_PROVEEDOR',proveedor_id)
    return True


def crear_cuenta_proveedor(proveedor_id,datos,password_hash,empresa_id,usuario_admin_id):
    with _escritura(usuario_admin_id,empresa_id,'proveedores:editar') as cur:
        _proveedor_activo(cur,proveedor_id,empresa_id)
        exigir_cupo_usuarios(cur,empresa_id)
        cur.execute('''INSERT INTO usuario(nombre,apellido,username,correo,password_hash,empresa_id)
            VALUES(%s,%s,%s,%s,%s,%s) RETURNING id''',(datos.nombre,datos.apellido,datos.username,datos.correo,password_hash,empresa_id))
        uid=cur.fetchone()['id']
        cur.execute('INSERT INTO proveedor_usuario(proveedor_id,usuario_id,empresa_id) VALUES(%s,%s,%s)',(proveedor_id,uid,empresa_id))
        asignar_rol(cur,uid,'PROVEEDOR')
        _auditar(cur,usuario_admin_id,'CREAR_CUENTA_PROVEEDOR',proveedor_id)
    return obtener_proveedor_por_id(proveedor_id,empresa_id)


def listar_productos_vinculables(empresa_id):
    with _transaccion() as cur:
        cur.execute('SELECT id,nombre FROM producto WHERE empresa_id=%s AND activo ORDER BY nombre,id',(empresa_id,))
        return [dict(r) for r in cur.fetchall()]


def listar_cuentas_vinculables(empresa_id):
    with _transaccion() as cur:
        cur.execute('''SELECT u.id,u.nombre,u.apellido,u.username,u.activo, (SELECT pu.proveedor_id FROM proveedor_usuario pu WHERE pu.usuario_id=u.id AND pu.activo) AS proveedor_id FROM usuario u WHERE u.empresa_id=%s
            AND NOT EXISTS(SELECT 1 FROM usuario_rol ur JOIN rol r ON r.id=ur.rol_id WHERE ur.usuario_id=u.id AND ur.activo AND r.activo AND r.nombre IN ('ADMINISTRADOR','ADMIN_SAAS'))
            ORDER BY u.nombre,u.id''',(empresa_id,))
        return [dict(r) for r in cur.fetchall()]


def vincular_producto_proveedor(proveedor_id,producto_id,empresa_id,usuario_admin_id,activo=True):
    with _escritura(usuario_admin_id,empresa_id,'proveedores:editar',nueva=activo) as cur:
        _proveedor_activo(cur,proveedor_id,empresa_id)
        cur.execute('SELECT id FROM producto WHERE id=%s AND empresa_id=%s AND activo',(producto_id,empresa_id))
        if not cur.fetchone():
            raise HTTPException(404,'Producto activo no encontrado en su empresa.')
        cur.execute('''INSERT INTO producto_proveedor(producto_id,proveedor_id,empresa_id,activo) VALUES(%s,%s,%s,%s)
            ON CONFLICT(producto_id,proveedor_id) DO UPDATE SET activo=EXCLUDED.activo''',(producto_id,proveedor_id,empresa_id,activo))
        _auditar(cur,usuario_admin_id,'VINCULAR_PRODUCTO' if activo else 'DESVINCULAR_PRODUCTO',proveedor_id)
    return listar_productos_proveedor_panel(proveedor_id,empresa_id)


def obtener_proveedor_por_usuario(usuario_id: int, empresa_id: int) -> dict[str, object] | None:
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT p.id, p.nombre, p.nit, p.telefono, p.correo, p.direccion, p.activo, p.fecha_creacion
            FROM proveedor_usuario pu
            JOIN proveedor p ON p.id = pu.proveedor_id AND p.empresa_id = pu.empresa_id
            WHERE pu.usuario_id = %s
              AND pu.empresa_id = %s
              AND pu.activo = TRUE
              AND p.activo = TRUE
            ORDER BY p.id ASC
            LIMIT 1;
            """,
            (usuario_id, empresa_id),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        cursor.close()
        connection.close()


def listar_productos_proveedor_panel(proveedor_id: int, empresa_id: int) -> list[dict[str, object]]:
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
            JOIN producto p ON p.id = pp.producto_id AND p.empresa_id = pp.empresa_id
            JOIN categoria ca ON ca.id = p.categoria_id AND ca.empresa_id = p.empresa_id
            LEFT JOIN marca m ON m.id = p.marca_id AND m.empresa_id = p.empresa_id
            LEFT JOIN producto_variante pv
                ON pv.producto_id = p.id
                AND pv.activo = TRUE AND pv.empresa_id = p.empresa_id
            WHERE pp.proveedor_id = %s
              AND pp.empresa_id = %s
              AND pp.activo = TRUE
            GROUP BY p.id, ca.nombre, m.nombre, pp.costo_referencia
            ORDER BY p.nombre ASC;
            """,
            (proveedor_id, empresa_id),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def listar_stock_proveedor_panel(proveedor_id: int, empresa_id: int) -> list[dict[str, object]]:
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
            JOIN producto p ON p.id = pp.producto_id AND p.empresa_id = pp.empresa_id
            JOIN producto_variante pv ON pv.producto_id = p.id AND pv.empresa_id = p.empresa_id
            JOIN talla t ON t.id = pv.talla_id AND t.empresa_id = p.empresa_id
            JOIN color co ON co.id = pv.color_id AND co.empresa_id = p.empresa_id
            JOIN inventario_sucursal inv
                ON inv.producto_variante_id = pv.id
                AND inv.activo = TRUE AND inv.empresa_id = p.empresa_id
            JOIN sucursal s ON s.id = inv.sucursal_id AND s.empresa_id = p.empresa_id
            JOIN ciudad ci ON ci.id = s.ciudad_id
            WHERE pp.proveedor_id = %s
              AND pp.empresa_id = %s
              AND pp.activo = TRUE
              AND p.activo = TRUE
              AND pv.activo = TRUE
            ORDER BY ci.nombre ASC, s.nombre ASC, p.nombre ASC, t.nombre ASC, co.nombre ASC;
            """,
            (proveedor_id, empresa_id),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def listar_entregas_proveedor_panel(proveedor_id: int, empresa_id: int) -> list[dict[str, object]]:
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
            JOIN producto_variante pv ON pv.id = mi.producto_variante_id AND pv.empresa_id = mi.empresa_id
            JOIN producto p ON p.id = pv.producto_id AND p.empresa_id = mi.empresa_id
            JOIN talla t ON t.id = pv.talla_id AND t.empresa_id = mi.empresa_id
            JOIN color co ON co.id = pv.color_id AND co.empresa_id = mi.empresa_id
            JOIN sucursal s ON s.id = mi.sucursal_id AND s.empresa_id = mi.empresa_id
            JOIN ciudad ci ON ci.id = s.ciudad_id
            WHERE mi.proveedor_id = %s
              AND mi.empresa_id = %s
              AND mi.tipo = 'ENTRADA'
              AND mi.activo = TRUE
            ORDER BY mi.fecha_movimiento DESC, mi.id DESC;
            """,
            (proveedor_id, empresa_id),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()
