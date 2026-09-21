CREATE TABLE IF NOT EXISTS reporte_programado (
    id BIGSERIAL PRIMARY KEY,
    titulo VARCHAR(150) NOT NULL,
    tipo VARCHAR(50) NOT NULL,
    frecuencia VARCHAR(20) NOT NULL,
    hora VARCHAR(10) NOT NULL DEFAULT '08:00',
    dia VARCHAR(20) NULL,
    formato VARCHAR(10) NOT NULL DEFAULT 'PDF',
    destinatario_email VARCHAR(200) NOT NULL,
    sucursal_id BIGINT NULL REFERENCES sucursal(id) ON DELETE SET NULL,
    solo_bajo_stock BOOLEAN NOT NULL DEFAULT FALSE,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_por BIGINT NULL,
    ultima_ejecucion TIMESTAMP WITH TIME ZONE NULL,
    proxima_ejecucion TIMESTAMP WITH TIME ZONE NULL,
    creado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Datos iniciales de ejemplo para programación de reportes
INSERT INTO reporte_programado (titulo, tipo, frecuencia, hora, dia, formato, destinatario_email, sucursal_id, solo_bajo_stock, activo)
SELECT 'Resumen Diario de Ventas', 'VENTAS', 'DIARIA', '20:00', NULL, 'PDF', 'admin@stylear.com', NULL, FALSE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM reporte_programado WHERE titulo = 'Resumen Diario de Ventas');

INSERT INTO reporte_programado (titulo, tipo, frecuencia, hora, dia, formato, destinatario_email, sucursal_id, solo_bajo_stock, activo)
SELECT 'Alerta Semanal de Bajo Stock', 'INVENTARIO', 'SEMANAL', '08:00', 'LUNES', 'EXCEL', 'inventario@stylear.com', NULL, TRUE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM reporte_programado WHERE titulo = 'Alerta Semanal de Bajo Stock');
