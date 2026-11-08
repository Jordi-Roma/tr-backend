ALTER TABLE plan ADD COLUMN IF NOT EXISTS stripe_price_id VARCHAR(255)
    CHECK (stripe_price_id ~ '^price_[A-Za-z0-9]+$');

CREATE TABLE IF NOT EXISTS suscripcion_stripe (
    id UUID PRIMARY KEY,
    empresa_id BIGINT NOT NULL REFERENCES empresa(id),
    suscripcion_id BIGINT NOT NULL REFERENCES suscripcion(id),
    stripe_price_id VARCHAR(255) NOT NULL,
    importe NUMERIC(12,2) NOT NULL,
    moneda CHAR(3) NOT NULL,
    estado VARCHAR(12) NOT NULL DEFAULT 'PENDIENTE'
        CHECK (estado IN ('PENDIENTE', 'ACTIVA', 'CERRADA')),
    checkout_id TEXT UNIQUE,
    checkout_url TEXT,
    checkout_expira TIMESTAMPTZ,
    stripe_suscripcion_id TEXT UNIQUE,
    stripe_cliente_id TEXT,
    pagado_hasta TIMESTAMPTZ,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_suscripcion_stripe_abierta
    ON suscripcion_stripe(empresa_id) WHERE estado IN ('PENDIENTE', 'ACTIVA');
