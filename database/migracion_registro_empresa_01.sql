-- Registro público: no modifica cuentas, planes ni suscripciones existentes.
ALTER TABLE plan ADD COLUMN publico BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE plan ADD CONSTRAINT ck_plan_legado_privado
    CHECK (codigo <> 'STYLEAR_LEGADO' OR NOT publico);

ALTER TABLE empresa DROP CONSTRAINT ck_empresa_estado;
ALTER TABLE empresa ADD CONSTRAINT ck_empresa_estado
    CHECK (estado IN ('PENDIENTE', 'ACTIVA', 'SUSPENDIDA', 'CANCELADA'));
ALTER TABLE suscripcion DROP CONSTRAINT ck_suscripcion_estado;
ALTER TABLE suscripcion ADD CONSTRAINT ck_suscripcion_estado
    CHECK (estado IN ('PENDIENTE', 'ACTIVA', 'SUSPENDIDA', 'VENCIDA', 'CANCELADA'));

CREATE TABLE solicitud_registro_empresa (
    id UUID PRIMARY KEY,
    empresa_id BIGINT NOT NULL UNIQUE REFERENCES empresa(id) DEFERRABLE INITIALLY IMMEDIATE,
    correo_contacto VARCHAR(150) NOT NULL,
    responsable VARCHAR(241) NOT NULL,
    origen_hash CHAR(64) NOT NULL,
    fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    huella_alta CHAR(64) NOT NULL
);
CREATE INDEX idx_solicitud_registro_correo ON solicitud_registro_empresa(correo_contacto,fecha_creacion);
CREATE INDEX idx_solicitud_registro_origen ON solicitud_registro_empresa(origen_hash,fecha_creacion);
