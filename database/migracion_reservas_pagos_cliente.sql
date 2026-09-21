BEGIN;

ALTER TABLE reserva
    ADD COLUMN IF NOT EXISTS anticipo_pagado BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS anticipo_orden_id BIGINT;

ALTER TABLE reserva
    DROP CONSTRAINT IF EXISTS fk_reserva_anticipo_orden;

ALTER TABLE reserva
    ADD CONSTRAINT fk_reserva_anticipo_orden
    FOREIGN KEY (anticipo_orden_id) REFERENCES orden_pago(id)
    ON UPDATE CASCADE ON DELETE SET NULL;

ALTER TABLE reserva
    DROP CONSTRAINT IF EXISTS ck_reserva_estado;

ALTER TABLE reserva
    ADD CONSTRAINT ck_reserva_estado CHECK (
        estado IN ('PENDIENTE_ANTICIPO', 'PENDIENTE', 'PREPARADA', 'EN_ATENCION', 'COMPLETADA', 'CANCELADA', 'VENCIDA')
    );

ALTER TABLE orden_pago
    ADD COLUMN IF NOT EXISTS reserva_id BIGINT,
    ADD COLUMN IF NOT EXISTS concepto VARCHAR(40) NOT NULL DEFAULT 'COMPRA';

ALTER TABLE orden_pago
    DROP CONSTRAINT IF EXISTS fk_orden_pago_reserva;

ALTER TABLE orden_pago
    ADD CONSTRAINT fk_orden_pago_reserva
    FOREIGN KEY (reserva_id) REFERENCES reserva(id)
    ON UPDATE CASCADE ON DELETE SET NULL;

ALTER TABLE orden_pago
    DROP CONSTRAINT IF EXISTS ck_orden_pago_concepto;

ALTER TABLE orden_pago
    ADD CONSTRAINT ck_orden_pago_concepto
    CHECK (concepto IN ('COMPRA', 'RESERVA_ANTICIPO', 'RESERVA_SALDO'));

CREATE INDEX IF NOT EXISTS idx_orden_pago_reserva
    ON orden_pago(reserva_id)
    WHERE reserva_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_reserva_anticipo_orden
    ON reserva(anticipo_orden_id)
    WHERE anticipo_orden_id IS NOT NULL;

UPDATE reserva
SET anticipo_pagado = TRUE
WHERE monto_reserva <= 0;

COMMIT;
