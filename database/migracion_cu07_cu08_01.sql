-- Preservar el rol laboral aunque se retire temporalmente el acceso.
ALTER TABLE empleado ADD COLUMN rol_laboral VARCHAR(80);
UPDATE empleado e SET rol_laboral=(
 SELECT r.nombre FROM usuario_rol ur JOIN rol r ON r.id=ur.rol_id
 WHERE ur.usuario_id=e.usuario_id AND r.nombre IN ('CAJERO','ENCARGADO_SUCURSAL','PERSONAL_VENTAS')
 ORDER BY ur.activo DESC, ur.rol_id LIMIT 1
);
ALTER TABLE empleado ADD CONSTRAINT ck_empleado_rol_laboral
 CHECK(rol_laboral IN ('CAJERO','ENCARGADO_SUCURSAL','PERSONAL_VENTAS'));
-- El panel representa un proveedor comercial por cuenta. No elegir uno al azar.
CREATE UNIQUE INDEX uq_proveedor_usuario_activo ON proveedor_usuario(usuario_id) WHERE activo;
