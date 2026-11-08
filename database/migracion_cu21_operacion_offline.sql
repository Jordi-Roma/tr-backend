ALTER TABLE operacion_comercial ALTER COLUMN recurso_id DROP NOT NULL;
ALTER TABLE operacion_comercial ADD COLUMN error TEXT;
ALTER TABLE operacion_comercial ADD CONSTRAINT ck_operacion_comercial_resultado
    CHECK ((recurso_id IS NOT NULL) <> (error IS NOT NULL));
