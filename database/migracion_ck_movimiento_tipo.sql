-- Migración para actualizar tipos permitidos en movimiento_inventario
ALTER TABLE movimiento_inventario
DROP CONSTRAINT IF EXISTS ck_movimiento_tipo;

ALTER TABLE movimiento_inventario
ADD CONSTRAINT ck_movimiento_tipo CHECK (
    tipo IN (
        'ENTRADA',
        'SALIDA',
        'AJUSTE_POSITIVO',
        'AJUSTE_NEGATIVO',
        'TRANSFERENCIA_ENTRADA',
        'TRANSFERENCIA_SALIDA',
        'VENTA_PRESENCIAL',
        'VENTA_DIGITAL'
    )
);
