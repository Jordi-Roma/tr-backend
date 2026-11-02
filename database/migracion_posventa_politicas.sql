CREATE TABLE politica_posventa (
 empresa_id BIGINT PRIMARY KEY REFERENCES empresa(id),
 cambios_habilitados BOOLEAN NOT NULL DEFAULT FALSE, plazo_cambios INTEGER CHECK(plazo_cambios BETWEEN 1 AND 365), condiciones_cambios VARCHAR(2000) NOT NULL DEFAULT '',
 devoluciones_habilitadas BOOLEAN NOT NULL DEFAULT FALSE, plazo_devoluciones INTEGER CHECK(plazo_devoluciones BETWEEN 1 AND 365), condiciones_devoluciones VARCHAR(2000) NOT NULL DEFAULT '',
 version INTEGER NOT NULL DEFAULT 1,
 CHECK(NOT cambios_habilitados OR (plazo_cambios IS NOT NULL AND length(trim(condiciones_cambios))>=5)),
 CHECK(NOT devoluciones_habilitadas OR (plazo_devoluciones IS NOT NULL AND length(trim(condiciones_devoluciones))>=5))
);
ALTER TABLE devolucion ADD COLUMN politica_snapshot JSONB;
ALTER TABLE devolucion ADD COLUMN aceptada_cliente_en TIMESTAMPTZ;
ALTER TABLE devolucion ADD COLUMN comprobante JSONB;
ALTER TABLE devolucion ADD COLUMN solicitud_clave UUID;
ALTER TABLE devolucion ADD COLUMN solicitud_huella CHAR(64);
CREATE UNIQUE INDEX uq_devolucion_solicitud ON devolucion(empresa_id,cliente_id,solicitud_clave) WHERE solicitud_clave IS NOT NULL;
ALTER TABLE devolucion_detalle ADD COLUMN cantidad_no_vendible INTEGER NOT NULL DEFAULT 0 CHECK(cantidad_no_vendible>=0 AND cantidad_no_vendible<=cantidad_aceptada);
ALTER TABLE devolucion DROP CONSTRAINT ck_devolucion_estado;
ALTER TABLE devolucion ADD CONSTRAINT ck_devolucion_estado CHECK(estado IN ('SOLICITADA','EN_REVISION','APROBADA','RECHAZADA','ESPERA_ACEPTACION','REEMBOLSO_PENDIENTE','ERROR_REEMBOLSO','REEMBOLSADA','CANCELADA'));

-- El cajero opera únicamente en su sucursal; el servidor vuelve a validar el alcance.
INSERT INTO rol_permiso(rol_id,permiso_id,activo)
SELECT r.id,p.id,TRUE FROM rol r CROSS JOIN permiso p
WHERE r.nombre='CAJERO' AND p.modulo='VENTAS_INVENTARIO' AND p.accion IN ('devoluciones:revisar','devoluciones:reembolsar')
ON CONFLICT(rol_id,permiso_id) DO UPDATE SET activo=TRUE;
