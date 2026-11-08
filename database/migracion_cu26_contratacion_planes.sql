ALTER TABLE suscripcion_stripe
    ADD COLUMN IF NOT EXISTS plan_destino_id BIGINT REFERENCES plan(id),
    ADD COLUMN IF NOT EXISTS comprobante_url TEXT;
