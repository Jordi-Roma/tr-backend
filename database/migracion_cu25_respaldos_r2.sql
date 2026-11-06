-- CU25: objetos privados en Cloudflare R2 y calendario de copias por empresa.
ALTER TABLE respaldo
    ADD COLUMN IF NOT EXISTS origen VARCHAR(20) NOT NULL DEFAULT 'MANUAL',
    ADD COLUMN IF NOT EXISTS object_key TEXT;

UPDATE respaldo
SET origen = 'MANUAL'
WHERE origen IS NULL;

ALTER TABLE respaldo DROP CONSTRAINT IF EXISTS ck_respaldo_origen;
ALTER TABLE respaldo ADD CONSTRAINT ck_respaldo_origen
    CHECK (origen IN ('MANUAL', 'AUTOMATICO', 'PRE_RESTAURACION'));

CREATE UNIQUE INDEX IF NOT EXISTS uq_respaldo_object_key
    ON respaldo(object_key) WHERE object_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_respaldo_empresa_fecha
    ON respaldo(empresa_id, fecha DESC) WHERE estado = 'DISPONIBLE';

CREATE TABLE IF NOT EXISTS respaldo_programacion (
    empresa_id BIGINT PRIMARY KEY REFERENCES empresa(id) ON DELETE CASCADE,
    activa BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_inicio DATE NOT NULL DEFAULT CURRENT_DATE,
    hora_local TIME NOT NULL DEFAULT '02:00',
    zona_horaria VARCHAR(80) NOT NULL DEFAULT 'America/La_Paz',
    ultimo_respaldo TIMESTAMPTZ,
    actualizada_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_respaldo_zona_horaria CHECK (length(zona_horaria) BETWEEN 1 AND 80)
);
