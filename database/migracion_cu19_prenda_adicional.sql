ALTER TABLE cambio_prenda
    ADD COLUMN adicional_id BIGINT REFERENCES producto_variante(id),
    ADD COLUMN precio_adicional NUMERIC(12,2),
    ADD CONSTRAINT ck_cambio_prenda_adicional CHECK (
        (adicional_id IS NULL AND precio_adicional IS NULL)
        OR (adicional_id IS NOT NULL AND precio_adicional IS NOT NULL AND precio_adicional > 0)
    );
