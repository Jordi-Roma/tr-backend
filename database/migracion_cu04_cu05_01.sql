-- Versión de acceso para serializar cambios administrativos con el login.
ALTER TABLE usuario ADD COLUMN IF NOT EXISTS version_acceso BIGINT NOT NULL DEFAULT 0;
-- Identificadores históricos: una restauración puede retirar una cuenta creada
-- después de la copia. El evento de AS debe conservar su objetivo original.
-- No son FKs vivas ni se resuelven como acceso a datos comerciales del objetivo.
ALTER TABLE bitacora ADD COLUMN IF NOT EXISTS objetivo_usuario_id BIGINT;
ALTER TABLE bitacora ADD COLUMN IF NOT EXISTS empresa_afectada_id BIGINT;
-- Los rechazos administrativos deben persistir como resultado explícito.
ALTER TABLE bitacora DROP CONSTRAINT IF EXISTS ck_bitacora_resultado;
ALTER TABLE bitacora ADD CONSTRAINT ck_bitacora_resultado
    CHECK (resultado IN ('EXITOSO','FALLIDO','BLOQUEADO'));
CREATE INDEX IF NOT EXISTS ix_usuario_empresa_estado_id ON usuario(empresa_id,activo,id);
CREATE INDEX IF NOT EXISTS ix_bitacora_empresa_fecha_id ON bitacora(empresa_id,fecha DESC,id DESC);
INSERT INTO permiso(nombre,modulo,accion,descripcion)
VALUES ('Reactivar usuarios','AUTENTICACION','usuarios:activar','Reactivar cuentas de la empresa.'),
       ('Asignar roles comerciales','AUTENTICACION','roles:asignar','Asignar roles a cuentas de la empresa.'),
       ('Retirar roles comerciales','AUTENTICACION','roles:retirar','Revocar roles de cuentas de la empresa.')
ON CONFLICT(modulo,accion) DO NOTHING;
-- Mantener capacidades administrativas existentes al introducir su control real.
INSERT INTO rol_permiso(rol_id,permiso_id,activo)
SELECT r.id,p.id,TRUE FROM rol r CROSS JOIN permiso p
WHERE r.nombre='ADMINISTRADOR' AND p.accion IN
 ('usuarios:ver','usuarios:crear','usuarios:editar','usuarios:desactivar','usuarios:activar','roles:ver','roles:asignar','roles:retirar','bitacora:ver')
ON CONFLICT(rol_id,permiso_id) DO UPDATE SET activo=TRUE;
