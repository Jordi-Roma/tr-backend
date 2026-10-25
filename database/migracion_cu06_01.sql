-- CU06: ciudades comerciales por empresa. El runner controla la transacción.
ALTER TABLE ciudad ADD COLUMN empresa_id BIGINT REFERENCES empresa(id);
UPDATE ciudad SET empresa_id = (SELECT id FROM empresa WHERE codigo='stylear');
ALTER TABLE ciudad ALTER COLUMN empresa_id SET NOT NULL;
ALTER TABLE ciudad DROP CONSTRAINT IF EXISTS uq_ciudad_nombre_departamento;
CREATE UNIQUE INDEX uq_ciudad_empresa_nombre_departamento
    ON ciudad(empresa_id, lower(nombre), lower(coalesce(departamento,'')));

-- Conservar los IDs originales de StyleAR. Si otra empresa utilizaba una
-- ciudad compartida, crear su copia y trasladar sólo sus referencias.
CREATE TEMP TABLE cu06_ciudades_referenciadas ON COMMIT DROP AS
SELECT DISTINCT empresa_id, ciudad_id FROM sucursal
UNION SELECT DISTINCT empresa_id, ciudad_id FROM direccion_cliente;
INSERT INTO ciudad(nombre, departamento, activo, empresa_id)
SELECT c.nombre,c.departamento,c.activo,r.empresa_id
FROM cu06_ciudades_referenciadas r JOIN ciudad c ON c.id=r.ciudad_id
WHERE r.empresa_id<>c.empresa_id
ON CONFLICT DO NOTHING;
UPDATE sucursal s SET ciudad_id=n.id
FROM ciudad anterior, ciudad n
WHERE s.ciudad_id=anterior.id AND s.empresa_id<>anterior.empresa_id
  AND n.empresa_id=s.empresa_id AND lower(n.nombre)=lower(anterior.nombre)
  AND lower(coalesce(n.departamento,''))=lower(coalesce(anterior.departamento,''));
UPDATE direccion_cliente d SET ciudad_id=n.id
FROM ciudad anterior, ciudad n
WHERE d.ciudad_id=anterior.id AND d.empresa_id<>anterior.empresa_id
  AND n.empresa_id=d.empresa_id AND lower(n.nombre)=lower(anterior.nombre)
  AND lower(coalesce(n.departamento,''))=lower(coalesce(anterior.departamento,''));

ALTER TABLE ciudad ADD CONSTRAINT uq_ciudad_empresa_id UNIQUE(empresa_id,id);
ALTER TABLE sucursal ADD CONSTRAINT fk_sucursal_ciudad_empresa
    FOREIGN KEY(empresa_id,ciudad_id) REFERENCES ciudad(empresa_id,id)
    DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE direccion_cliente ADD CONSTRAINT fk_direccion_ciudad_empresa
    FOREIGN KEY(empresa_id,ciudad_id) REFERENCES ciudad(empresa_id,id)
    DEFERRABLE INITIALLY IMMEDIATE;
CREATE TRIGGER trg_ciudad_empresa_inmutable BEFORE UPDATE ON ciudad
    FOR EACH ROW EXECUTE FUNCTION impedir_cambio_empresa();

-- Serializar altas/reactivaciones de sucursales con la desactivación de ciudad.
-- El repositorio toma primero el lock de empresa para no invertir el orden.
CREATE FUNCTION validar_ciudad_sucursal_activa() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE habilitada BOOLEAN;
BEGIN
    IF NEW.activo THEN
        SELECT activo INTO habilitada FROM ciudad
        WHERE id=NEW.ciudad_id AND empresa_id=NEW.empresa_id FOR UPDATE;
        IF habilitada IS DISTINCT FROM TRUE THEN
            RAISE EXCEPTION 'La ciudad no pertenece a la empresa o está inactiva'
                USING ERRCODE='23514';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER trg_sucursal_ciudad_activa BEFORE INSERT OR UPDATE ON sucursal
    FOR EACH ROW EXECUTE FUNCTION validar_ciudad_sucursal_activa();
CREATE FUNCTION impedir_desactivar_ciudad_con_sucursales() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT NEW.activo AND EXISTS(
        SELECT 1 FROM sucursal WHERE ciudad_id=NEW.id AND empresa_id=NEW.empresa_id AND activo
    ) THEN
        RAISE EXCEPTION 'No se puede desactivar una ciudad con sucursales activas'
            USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER trg_ciudad_sucursales_activas BEFORE UPDATE OF activo ON ciudad
    FOR EACH ROW EXECUTE FUNCTION impedir_desactivar_ciudad_con_sucursales();
