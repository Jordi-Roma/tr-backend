BEGIN;

ALTER TABLE reserva
    ADD COLUMN IF NOT EXISTS fecha_cita DATE,
    ADD COLUMN IF NOT EXISTS monto_reserva NUMERIC(12, 2) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS monto_aplicado NUMERIC(12, 2) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS venta_id BIGINT;

ALTER TABLE reserva
    DROP CONSTRAINT IF EXISTS fk_reserva_venta;

ALTER TABLE reserva
    ADD CONSTRAINT fk_reserva_venta
    FOREIGN KEY (venta_id) REFERENCES venta(id)
    ON UPDATE CASCADE ON DELETE SET NULL;

ALTER TABLE reserva
    DROP CONSTRAINT IF EXISTS ck_reserva_montos_anticipo;

ALTER TABLE reserva
    ADD CONSTRAINT ck_reserva_montos_anticipo
    CHECK (monto_reserva >= 0 AND monto_aplicado >= 0);

CREATE INDEX IF NOT EXISTS idx_reserva_fecha_cita
    ON reserva (fecha_cita);

CREATE INDEX IF NOT EXISTS idx_reserva_venta
    ON reserva (venta_id)
    WHERE venta_id IS NOT NULL;

COMMIT;
