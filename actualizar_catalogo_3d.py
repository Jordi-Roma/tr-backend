from app.database.connection import get_connection

conn = get_connection()
c = conn.cursor()

print("Actualizando productos 3D del catálogo...")

# 1. Actualizar nombres y detalles de productos
c.execute("""
    UPDATE producto 
    SET nombre = 'Jeans Denim Clásico 3D',
        descripcion = 'Pantalón Jean Denim clásico con ajuste 3D, textura original de mezclilla y física de tela en tiempo real.',
        tipo_prenda = 'INFERIOR',
        tipo_corte = 'SLIM_FIT',
        ancho_base_cm = 84.0,
        largo_base_cm = 104.0,
        activo = TRUE
    WHERE id = 4;
""")

c.execute("""
    UPDATE producto 
    SET nombre = 'Camisa Polo Elegante 3D',
        descripcion = 'Polo azul marino de corte regular fit con cuello reforzado y textura premium.',
        tipo_prenda = 'SUPERIOR',
        tipo_corte = 'REGULAR_FIT',
        ancho_base_cm = 54.0,
        largo_base_cm = 72.0,
        activo = TRUE
    WHERE id = 3;
""")

c.execute("""
    UPDATE producto 
    SET nombre = 'Polera Negra Casual 3D',
        descripcion = 'Polera negra de algodón peinado con ajuste anatómico y caída natural.',
        tipo_prenda = 'SUPERIOR',
        tipo_corte = 'REGULAR_FIT',
        ancho_base_cm = 52.0,
        largo_base_cm = 70.0,
        activo = TRUE
    WHERE id = 2;
""")

c.execute("""
    UPDATE producto 
    SET nombre = 'Hoodie Urbano 3D Streetwear',
        descripcion = 'Suéter hoodie gris con capucha y bolsillo canguro, modelo volumétrico 3D.',
        tipo_prenda = 'SUPERIOR',
        tipo_corte = 'OVERSIZE',
        ancho_base_cm = 58.0,
        largo_base_cm = 74.0,
        activo = TRUE
    WHERE id = 1;
""")

# 2. Actualizar imágenes principales para que apunten al servidor estático propio (sin 403)
imagenes = {
    4: "https://impromptu-uncertain-grading.ngrok-free.dev/static/images/jeans_denim_3d.jpg",
    3: "https://impromptu-uncertain-grading.ngrok-free.dev/static/images/polo_azul_3d.jpg",
    2: "https://impromptu-uncertain-grading.ngrok-free.dev/static/images/polera_negra_3d.jpg",
    1: "https://impromptu-uncertain-grading.ngrok-free.dev/static/images/hoodie_gris_3d.jpg",
}

for prod_id, url in imagenes.items():
    # Desactivar imagenes anteriores
    c.execute("UPDATE imagen_producto SET activo = FALSE WHERE producto_id = %s;", (prod_id,))
    # Insertar o actualizar la imagen principal
    c.execute("""
        INSERT INTO imagen_producto (producto_id, url, es_principal, activo)
        VALUES (%s, %s, TRUE, TRUE);
    """, (prod_id, url))

# 3. Asegurar precios vigentes
precios = {
    4: 380.00,  # Jean
    3: 220.00,  # Polo
    2: 190.00,  # Polera
    1: 320.00,  # Hoodie
}

for prod_id, precio in precios.items():
    c.execute("SELECT id FROM producto_variante WHERE producto_id = %s AND activo = TRUE LIMIT 1;", (prod_id,))
    row = c.fetchone()
    if row:
        var_id = row[0]
        c.execute("""
            UPDATE precio_producto 
            SET precio = %s, fecha_inicio = '2026-01-01', fecha_fin = '2027-12-31', activo = TRUE 
            WHERE producto_variante_id = %s;
        """, (precio, var_id))
        if c.rowcount == 0:
            c.execute("""
                INSERT INTO precio_producto (producto_variante_id, precio, fecha_inicio, fecha_fin, activo)
                VALUES (%s, %s, '2026-01-01', '2027-12-31', TRUE);
            """, (var_id, precio))

# 4. Asegurar stock en sucursales para que salgan "En stock"
c.execute("SELECT id FROM sucursal WHERE activo = TRUE;")
sucursales = [r[0] for r in c.fetchall()]
if not sucursales:
    sucursales = [1, 2]

for prod_id in [1, 2, 3, 4]:
    c.execute("SELECT id FROM producto_variante WHERE producto_id = %s AND activo = TRUE;", (prod_id,))
    variantes = [r[0] for r in c.fetchall()]
    for v_id in variantes:
        for s_id in sucursales:
            c.execute("""
                INSERT INTO inventario_sucursal (sucursal_id, producto_variante_id, stock_disponible, stock_reservado, activo)
                VALUES (%s, %s, 15, 0, TRUE)
                ON CONFLICT (sucursal_id, producto_variante_id) 
                DO UPDATE SET stock_disponible = 15, stock_reservado = 0, activo = TRUE;
            """, (s_id, v_id))

conn.commit()
conn.close()
print("¡Catálogo 3D y stock actualizados correctamente en PostgreSQL!")
