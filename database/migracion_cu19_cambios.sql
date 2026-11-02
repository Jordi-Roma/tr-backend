ALTER TABLE devolucion ADD COLUMN tipo_operacion VARCHAR(12) NOT NULL DEFAULT 'DEVOLUCION' CHECK(tipo_operacion IN ('DEVOLUCION','CAMBIO'));
ALTER TABLE devolucion ADD COLUMN importe_reintegro NUMERIC(12,2) CHECK(importe_reintegro>=0 AND importe_reintegro<=monto_aprobado);
ALTER TABLE devolucion DROP CONSTRAINT ck_devolucion_estado;
ALTER TABLE devolucion ADD CONSTRAINT ck_devolucion_estado CHECK(estado IN ('SOLICITADA','EN_REVISION','APROBADA','RECHAZADA','ESPERA_ACEPTACION','REEMBOLSO_PENDIENTE','ERROR_REEMBOLSO','REEMBOLSADA','CANCELADA','CAMBIO_COMPLETADO'));
CREATE TABLE cambio_prenda (
 id BIGINT PRIMARY KEY REFERENCES devolucion(id),
 estado VARCHAR(24) NOT NULL DEFAULT 'SOLICITADO' CHECK(estado IN ('SOLICITADO','APROBADO','RECHAZADO','COTIZADO','ESPERA_PAGO','ESPERA_REINTEGRO','LISTO','COMPLETADO','CANCELADO','DEVOLUCION')),
 version INTEGER NOT NULL DEFAULT 1,
 reemplazo_id BIGINT REFERENCES producto_variante(id),
 cantidad INTEGER NOT NULL CHECK(cantidad>0),
 precio_reemplazo NUMERIC(12,2),
 credito NUMERIC(12,2),
 diferencia NUMERIC(12,2),
 cotizacion_vence TIMESTAMPTZ,
 aceptado_en TIMESTAMPTZ,
 reservado BOOLEAN NOT NULL DEFAULT FALSE,
 orden_id BIGINT REFERENCES orden_pago(id),
 comprobante JSONB,
 actualizado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE orden_pago ADD COLUMN cambio_id BIGINT REFERENCES cambio_prenda(id);
ALTER TABLE orden_pago DROP CONSTRAINT ck_orden_pago_concepto;
ALTER TABLE orden_pago ADD CONSTRAINT ck_orden_pago_concepto CHECK(concepto IN ('COMPRA','RESERVA_ANTICIPO','RESERVA_SALDO','DIFERENCIA_CAMBIO'));
CREATE INDEX idx_orden_cambio ON orden_pago(cambio_id);
