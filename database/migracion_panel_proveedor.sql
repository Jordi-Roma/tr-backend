-- Panel de proveedores:
-- - Vincula usuarios con proveedores comerciales.
-- - Permite trazar entradas de inventario por proveedor.
-- - Crea rol y permisos base del proveedor.

CREATE TABLE IF NOT EXISTS proveedor_usuario (
    proveedor_id BIGINT NOT NULL,
    usuario_id BIGINT NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (proveedor_id, usuario_id),
    CONSTRAINT fk_proveedor_usuario_proveedor
        FOREIGN KEY (proveedor_id) REFERENCES proveedor (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_proveedor_usuario_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuario (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_proveedor_usuario_usuario
    ON proveedor_usuario (usuario_id)
    WHERE activo = TRUE;

ALTER TABLE movimiento_inventario
    ADD COLUMN IF NOT EXISTS proveedor_id BIGINT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_movimiento_proveedor'
    ) THEN
        ALTER TABLE movimiento_inventario
            ADD CONSTRAINT fk_movimiento_proveedor
            FOREIGN KEY (proveedor_id) REFERENCES proveedor (id)
            ON UPDATE CASCADE ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_movimiento_inventario_proveedor
    ON movimiento_inventario (proveedor_id)
    WHERE proveedor_id IS NOT NULL;

INSERT INTO rol (nombre, descripcion, activo)
VALUES ('PROVEEDOR', 'Proveedor externo con acceso de consulta a sus productos, stock y entregas.', TRUE)
ON CONFLICT (nombre) DO UPDATE
SET descripcion = EXCLUDED.descripcion,
    activo = TRUE;

INSERT INTO permiso (nombre, modulo, accion, descripcion, activo)
VALUES
    ('Ver panel proveedor', 'PROVEEDOR', 'proveedor_panel:ver', 'Permite acceder al panel propio del proveedor.', TRUE),
    ('Ver productos propios proveedor', 'PROVEEDOR', 'proveedor_panel:productos', 'Permite consultar productos vinculados al proveedor.', TRUE),
    ('Ver stock propio proveedor', 'PROVEEDOR', 'proveedor_panel:stock', 'Permite consultar stock de productos vinculados al proveedor.', TRUE),
    ('Ver entregas propias proveedor', 'PROVEEDOR', 'proveedor_panel:entregas', 'Permite consultar entradas de inventario registradas para el proveedor.', TRUE)
ON CONFLICT (modulo, accion) DO UPDATE
SET nombre = EXCLUDED.nombre,
    descripcion = EXCLUDED.descripcion,
    activo = TRUE;

INSERT INTO rol_permiso (rol_id, permiso_id, activo)
SELECT r.id, p.id, TRUE
FROM rol r
JOIN permiso p ON p.modulo = 'PROVEEDOR'
WHERE r.nombre = 'PROVEEDOR'
ON CONFLICT (rol_id, permiso_id) DO UPDATE
SET activo = TRUE;
