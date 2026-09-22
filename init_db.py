"""
Script para inicializar o migrar la base de datos (local o en la nube).
Ejecuta los scripts SQL en el orden correcto usando la variable DATABASE_URL.
Uso: python init_db.py
"""
import os
import sys

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app.database.connection import get_connection

SQL_FILES = [
    "database/script_inicial.sql",
    "database/migracion_cu10_cu11.sql",
    "database/migracion_ciclo2_bloque1_catalogo_disponibilidad.sql",
    "database/migracion_ciclo2_bloque2_carrito_reservas.sql",
    "database/migracion_ciclo2_bloque3_inventario_ventas.sql",
    "database/migracion_reservas_cita_anticipo.sql",
    "database/migracion_cu22_recomendaciones.sql",
    "database/migracion_pasarela_pago_stripe.sql",
    "database/migracion_reservas_pagos_cliente.sql",
    "database/migracion_venta_digital_movimiento.sql",
    "database/migracion_roles_permisos_base.sql",
    "database/migracion_historial_pagos.sql",
    "database/migracion_delivery.sql",
    "database/migracion_password_reset.sql",
    "database/migracion_cu24_admin_ar_medidas.sql",
    "database/migracion_cu24_talla_tipo_prenda.sql",
    "database/migracion_cu24_vestidor.sql",
    "database/migracion_reportes_programados.sql",
    "database/migracion_panel_proveedor.sql",
]


def ejecutar_scripts():
    print("Iniciando configuracion de base de datos...")
    conn = get_connection()
    try:
        cur = conn.cursor()
        for rel_path in SQL_FILES:
            full_path = os.path.join(os.path.dirname(__file__), rel_path)
            if not os.path.exists(full_path):
                print(f"Advertencia: no se encontro {rel_path}, saltando...")
                continue
            print(f"Ejecutando {rel_path}...")
            with open(full_path, "r", encoding="utf-8") as f:
                sql = f.read()
            try:
                cur.execute(sql)
                conn.commit()
                print(f"OK: {rel_path}")
            except Exception as ex:
                conn.rollback()
                print(f"Nota en {rel_path}: {ex}")

        try:
            cur.execute("ALTER TABLE categoria ADD COLUMN IF NOT EXISTS categoria_padre_id BIGINT NULL;")
            conn.commit()
            print("OK: Columna categoria_padre_id verificada.")
        except Exception:
            conn.rollback()

        print("Base de datos configurada correctamente.")
    finally:
        conn.close()


if __name__ == "__main__":
    ejecutar_scripts()
