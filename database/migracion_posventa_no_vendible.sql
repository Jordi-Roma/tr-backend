ALTER TABLE movimiento_inventario DROP CONSTRAINT ck_movimiento_tipo;
ALTER TABLE movimiento_inventario ADD CONSTRAINT ck_movimiento_tipo CHECK (
    tipo IN ('ENTRADA', 'SALIDA', 'AJUSTE_POSITIVO', 'AJUSTE_NEGATIVO',
             'TRANSFERENCIA_ENTRADA', 'TRANSFERENCIA_SALIDA', 'VENTA_PRESENCIAL',
             'VENTA_DIGITAL', 'DEVOLUCION_VENTA', 'DEVOLUCION_NO_VENDIBLE')
    AND (tipo <> 'DEVOLUCION_NO_VENDIBLE' OR stock_anterior = stock_nuevo)
);
