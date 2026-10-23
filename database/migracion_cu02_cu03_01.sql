-- Intentos persistentes de los códigos de recuperación de un solo uso.
ALTER TABLE password_reset_token
    ADD COLUMN IF NOT EXISTS intentos INTEGER NOT NULL DEFAULT 0
    CHECK (intentos >= 0);
