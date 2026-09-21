-- Migración: Asociación de Talla con tipo_prenda (SUPERIOR, INFERIOR, VESTIDO)
-- StyleAR - CU24

-- 1. Agregar columna tipo_prenda a talla si no existe
ALTER TABLE talla 
ADD COLUMN IF NOT EXISTS tipo_prenda VARCHAR(20) DEFAULT 'SUPERIOR';

-- 2. Asegurar que las tallas actuales sean SUPERIOR
UPDATE talla 
SET tipo_prenda = 'SUPERIOR' 
WHERE tipo_prenda IS NULL;

-- 3. Modificar restricción única para permitir el mismo nombre en distinto tipo de prenda (ej. 'S' en SUPERIOR y 'S' en INFERIOR)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'talla_nombre_key'
    ) THEN
        ALTER TABLE talla DROP CONSTRAINT talla_nombre_key;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_talla_nombre_tipo_prenda'
    ) THEN
        ALTER TABLE talla ADD CONSTRAINT uq_talla_nombre_tipo_prenda UNIQUE (nombre, tipo_prenda);
    END IF;
END $$;

-- 4. Insertar tallas estándar para prendas inferiores (Pantalones, Jeans, Shorts)
INSERT INTO talla (nombre, descripcion, tipo_prenda, ancho_cm, largo_cm, activo)
VALUES 
    ('S', 'Talla S para prenda inferior (Cintura ~38cm, Largo ~100cm)', 'INFERIOR', 38.0, 100.0, true),
    ('M', 'Talla M para prenda inferior (Cintura ~40cm, Largo ~102cm)', 'INFERIOR', 40.0, 102.0, true),
    ('L', 'Talla L para prenda inferior (Cintura ~43cm, Largo ~104cm)', 'INFERIOR', 43.0, 104.0, true),
    ('XL', 'Talla XL para prenda inferior (Cintura ~46cm, Largo ~106cm)', 'INFERIOR', 46.0, 106.0, true),
    ('28', 'Talla numérica 28 inferior', 'INFERIOR', 36.0, 98.0, true),
    ('30', 'Talla numérica 30 inferior', 'INFERIOR', 38.0, 100.0, true),
    ('32', 'Talla numérica 32 inferior', 'INFERIOR', 41.0, 102.0, true),
    ('34', 'Talla numérica 34 inferior', 'INFERIOR', 44.0, 104.0, true),
    ('36', 'Talla numérica 36 inferior', 'INFERIOR', 47.0, 106.0, true)
ON CONFLICT (nombre, tipo_prenda) DO UPDATE 
SET ancho_cm = EXCLUDED.ancho_cm,
    largo_cm = EXCLUDED.largo_cm,
    descripcion = EXCLUDED.descripcion,
    activo = true;

-- 5. Insertar tallas estándar para Vestidos / Cuerpo Completo
INSERT INTO talla (nombre, descripcion, tipo_prenda, ancho_cm, largo_cm, activo)
VALUES 
    ('S', 'Talla S para vestido / cuerpo completo', 'VESTIDO', 44.0, 118.0, true),
    ('M', 'Talla M para vestido / cuerpo completo', 'VESTIDO', 48.0, 122.0, true),
    ('L', 'Talla L para vestido / cuerpo completo', 'VESTIDO', 52.0, 126.0, true)
ON CONFLICT (nombre, tipo_prenda) DO UPDATE 
SET ancho_cm = EXCLUDED.ancho_cm,
    largo_cm = EXCLUDED.largo_cm,
    descripcion = EXCLUDED.descripcion,
    activo = true;
