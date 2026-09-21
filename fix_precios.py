from app.database.connection import get_connection

conn = get_connection()
c = conn.cursor()
c.execute("UPDATE precio_producto SET fecha_inicio = '2026-01-01', fecha_fin = '2027-12-31', activo = TRUE;")
c.execute("SELECT id FROM producto_variante WHERE producto_id = 3 LIMIT 1;")
row = c.fetchone()
if row:
    c.execute(
        "INSERT INTO precio_producto (producto_variante_id, precio, fecha_inicio, fecha_fin, activo) "
        "VALUES (%s, 220.00, '2026-01-01', '2027-12-31', TRUE);",
        (row[0],)
    )
conn.commit()
print("Precios corregidos con éxito!")
