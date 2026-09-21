BEGIN;

CREATE TABLE IF NOT EXISTS producto_embedding (
    producto_id BIGINT PRIMARY KEY REFERENCES producto(id) ON DELETE CASCADE,
    modelo VARCHAR(100) NOT NULL,
    texto_hash CHAR(64) NOT NULL,
    embedding DOUBLE PRECISION[] NOT NULL,
    fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cliente_favorito (
    cliente_id BIGINT NOT NULL REFERENCES cliente(id) ON DELETE CASCADE,
    producto_id BIGINT NOT NULL REFERENCES producto(id) ON DELETE CASCADE,
    fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (cliente_id, producto_id)
);

CREATE TABLE IF NOT EXISTS cliente_preferencia_ia (
    cliente_id BIGINT PRIMARY KEY REFERENCES cliente(id) ON DELETE CASCADE,
    categorias BIGINT[] NOT NULL DEFAULT '{}',
    usar_historial BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cliente_favorito_producto ON cliente_favorito(producto_id);
CREATE INDEX IF NOT EXISTS idx_venta_cliente_completada
    ON venta(cliente_id, fecha_venta DESC)
    WHERE estado = 'COMPLETADA' AND activo = TRUE AND cliente_id IS NOT NULL;

COMMIT;
