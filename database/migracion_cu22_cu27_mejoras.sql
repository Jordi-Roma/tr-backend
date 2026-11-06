-- Ampliación de los módulos existentes, aplicada por init_db.py.
ALTER TABLE reporte_programado ADD COLUMN revision BIGINT NOT NULL DEFAULT 1;
ALTER TABLE reporte_ejecucion ADD COLUMN reporte_revision BIGINT NOT NULL DEFAULT 1;

ALTER TABLE notificacion_usuario
    ADD COLUMN categoria VARCHAR(20) NOT NULL DEFAULT 'GENERAL',
    ADD COLUMN recurso_tipo VARCHAR(25),
    ADD COLUMN recurso_id BIGINT,
    ADD COLUMN accion VARCHAR(30),
    ADD COLUMN leida_en TIMESTAMPTZ;
ALTER TABLE notificacion_usuario ADD CONSTRAINT ck_notificacion_categoria CHECK
    (categoria IN ('GENERAL','COMPRA','PAGO','RESERVA','ENTREGA','CAMBIO','DEVOLUCION','REEMBOLSO'));
ALTER TABLE notificacion_usuario ADD CONSTRAINT ck_notificacion_destino CHECK
    ((recurso_tipo IS NULL AND recurso_id IS NULL AND accion IS NULL) OR
     (recurso_tipo IS NOT NULL AND recurso_id IS NOT NULL AND accion IS NOT NULL
      AND recurso_tipo IN ('VENTA','ORDEN_PAGO','RESERVA','DELIVERY','CAMBIO','DEVOLUCION')
      AND recurso_id>0 AND accion='VER_DETALLE'));
UPDATE notificacion_usuario SET categoria='PAGO',recurso_tipo='ORDEN_PAGO',recurso_id=orden_id,accion='VER_DETALLE'
    WHERE orden_id IS NOT NULL;
UPDATE notificacion_usuario SET categoria='COMPRA' WHERE clave LIKE 'compra:%';
UPDATE notificacion_usuario SET categoria='REEMBOLSO' WHERE clave LIKE 'reembolso%' OR clave LIKE 'reembolsado:%';
UPDATE notificacion_usuario SET categoria='ENTREGA',recurso_tipo='DELIVERY',
    recurso_id=split_part(clave,':',2)::bigint,accion='VER_DETALLE' WHERE clave ~ '^delivery:[0-9]+:';
UPDATE notificacion_usuario SET categoria='DEVOLUCION',recurso_tipo='DEVOLUCION',
    recurso_id=split_part(clave,':',2)::bigint,accion='VER_DETALLE' WHERE clave ~ '^devolucion:[0-9]+:';

CREATE TABLE notificacion_preferencia (
    empresa_id BIGINT NOT NULL REFERENCES empresa(id) DEFERRABLE INITIALLY IMMEDIATE,
    usuario_id BIGINT NOT NULL REFERENCES usuario(id) DEFERRABLE INITIALLY IMMEDIATE,
    categoria VARCHAR(20) NOT NULL CHECK (categoria IN
        ('GENERAL','COMPRA','PAGO','RESERVA','ENTREGA','CAMBIO','DEVOLUCION','REEMBOLSO')),
    push_habilitado BOOLEAN NOT NULL DEFAULT TRUE,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(empresa_id,usuario_id,categoria)
);
CREATE TRIGGER trg_notificacion_preferencia_empresa BEFORE INSERT OR UPDATE ON notificacion_preferencia
    FOR EACH ROW EXECUTE FUNCTION validar_empresa_de_padre('usuario','usuario_id');
ALTER TABLE salida_push ADD COLUMN proximo_intento TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN aceptado_en TIMESTAMPTZ,
    ADD COLUMN expira_en TIMESTAMPTZ;
UPDATE salida_push s SET expira_en=n.creado_en+INTERVAL '24 hours'
    FROM notificacion_usuario n WHERE n.id=s.notificacion_id;
CREATE INDEX idx_notificacion_bandeja ON notificacion_usuario(empresa_id,usuario_id,id DESC);
CREATE INDEX idx_notificacion_no_leidas ON notificacion_usuario(empresa_id,usuario_id,id DESC) WHERE NOT leida;
CREATE INDEX idx_push_proximo ON salida_push(proximo_intento,id) WHERE estado IN ('PENDIENTE','FALLIDO');
