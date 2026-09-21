CREATE TABLE IF NOT EXISTS password_reset_token (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuario(id),
    token_hash TEXT NOT NULL,
    fecha_expiracion TIMESTAMP NOT NULL,
    usado BOOLEAN NOT NULL DEFAULT FALSE,
    fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_uso TIMESTAMP NULL
);

CREATE INDEX IF NOT EXISTS idx_password_reset_token_usuario
    ON password_reset_token(usuario_id);

CREATE INDEX IF NOT EXISTS idx_password_reset_token_hash
    ON password_reset_token(token_hash);
