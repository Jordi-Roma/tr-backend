-- CU10: conservar asociaciones retiradas, imágenes y variantes históricas.
ALTER TABLE producto_coleccion ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE promocion_producto ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE promocion_sucursal ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE producto_variante ALTER COLUMN talla_id DROP NOT NULL;
ALTER TABLE producto_variante ALTER COLUMN color_id DROP NOT NULL;
-- NULL también identifica una característica no aplicable de una variante.
-- Si existen combinaciones heredadas repetidas, detener la migración sin borrar datos.
CREATE UNIQUE INDEX IF NOT EXISTS uq_cu10_variante_combinacion
    ON producto_variante(empresa_id,producto_id,talla_id,color_id) NULLS NOT DISTINCT;
