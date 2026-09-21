BEGIN;

INSERT INTO permiso (nombre, modulo, accion, descripcion, activo)
VALUES
    ('Ver pagos propios', 'VENTAS_INVENTARIO', 'pagos:ver_propios', 'Permite consultar el historial de pagos propio del cliente.', TRUE),
    ('Ver todos los pagos', 'VENTAS_INVENTARIO', 'pagos:ver_todos', 'Permite consultar todos los pagos registrados en el sistema.', TRUE),
    ('Ver pagos de sucursal', 'VENTAS_INVENTARIO', 'pagos:ver_sucursal', 'Permite consultar pagos relacionados con la sucursal del encargado.', TRUE)
ON CONFLICT (modulo, accion) DO UPDATE
SET nombre = EXCLUDED.nombre,
    descripcion = EXCLUDED.descripcion,
    activo = TRUE;

INSERT INTO rol_permiso (rol_id, permiso_id, activo)
SELECT r.id, p.id, TRUE
FROM rol r
JOIN permiso p ON p.modulo = 'VENTAS_INVENTARIO'
WHERE r.nombre = 'CLIENTE'
  AND p.accion = 'pagos:ver_propios'
ON CONFLICT (rol_id, permiso_id) DO UPDATE SET activo = TRUE;

INSERT INTO rol_permiso (rol_id, permiso_id, activo)
SELECT r.id, p.id, TRUE
FROM rol r
JOIN permiso p ON p.modulo = 'VENTAS_INVENTARIO'
WHERE r.nombre = 'ADMINISTRADOR'
  AND p.accion = 'pagos:ver_todos'
ON CONFLICT (rol_id, permiso_id) DO UPDATE SET activo = TRUE;

INSERT INTO rol_permiso (rol_id, permiso_id, activo)
SELECT r.id, p.id, TRUE
FROM rol r
JOIN permiso p ON p.modulo = 'VENTAS_INVENTARIO'
WHERE r.nombre = 'ENCARGADO_SUCURSAL'
  AND p.accion = 'pagos:ver_sucursal'
ON CONFLICT (rol_id, permiso_id) DO UPDATE SET activo = TRUE;

COMMIT;
