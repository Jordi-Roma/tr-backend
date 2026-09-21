BEGIN;

-- 1. Agregar dimensiones estándar a la tabla TALLA
ALTER TABLE talla
ADD COLUMN IF NOT EXISTS ancho_cm NUMERIC(6,2) NULL,
ADD COLUMN IF NOT EXISTS largo_cm NUMERIC(6,2) NULL;

-- 2. Agregar campos de Realidad Aumentada (Vestidor Virtual) a la tabla PRODUCTO
ALTER TABLE producto
ADD COLUMN IF NOT EXISTS tipo_prenda VARCHAR(20) NOT NULL DEFAULT 'SUPERIOR',
ADD COLUMN IF NOT EXISTS tipo_corte VARCHAR(30) NOT NULL DEFAULT 'REGULAR_FIT',
ADD COLUMN IF NOT EXISTS ancho_base_cm NUMERIC(6,2) NOT NULL DEFAULT 53.0,
ADD COLUMN IF NOT EXISTS largo_base_cm NUMERIC(6,2) NOT NULL DEFAULT 72.0;

-- 3. Agregar medidas personalizables por prenda a la tabla PRODUCTO_VARIANTE
ALTER TABLE producto_variante
ADD COLUMN IF NOT EXISTS ancho_cm NUMERIC(6,2) NULL,
ADD COLUMN IF NOT EXISTS largo_cm NUMERIC(6,2) NULL;

-- 4. Precargar medidas estándar de referencia en las tallas existentes
UPDATE talla SET ancho_cm = 46.0, largo_cm = 66.0 WHERE UPPER(nombre) = 'XS' AND ancho_cm IS NULL;
UPDATE talla SET ancho_cm = 49.0, largo_cm = 69.0 WHERE UPPER(nombre) = 'S' AND ancho_cm IS NULL;
UPDATE talla SET ancho_cm = 53.0, largo_cm = 72.0 WHERE UPPER(nombre) = 'M' AND ancho_cm IS NULL;
UPDATE talla SET ancho_cm = 57.0, largo_cm = 75.0 WHERE UPPER(nombre) = 'L' AND ancho_cm IS NULL;
UPDATE talla SET ancho_cm = 61.0, largo_cm = 78.0 WHERE UPPER(nombre) = 'XL' AND ancho_cm IS NULL;
UPDATE talla SET ancho_cm = 65.0, largo_cm = 81.0 WHERE UPPER(nombre) = 'XXL' AND ancho_cm IS NULL;

COMMIT;
