BEGIN;

CREATE TABLE IF NOT EXISTS rol_permiso (
    rol_id BIGINT NOT NULL,
    permiso_id BIGINT NOT NULL,
    fecha_asignacion TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (rol_id, permiso_id),
    CONSTRAINT fk_rol_permiso_rol
        FOREIGN KEY (rol_id) REFERENCES rol (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_rol_permiso_permiso
        FOREIGN KEY (permiso_id) REFERENCES permiso (id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

ALTER TABLE rol_permiso
    ADD COLUMN IF NOT EXISTS fecha_asignacion TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE rol_permiso
    ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT TRUE;

INSERT INTO permiso (nombre, modulo, accion, descripcion, activo)
VALUES
    ('Ver perfil', 'AUTENTICACION', 'perfil:ver', 'Permite consultar el perfil propio.', TRUE),
    ('Editar perfil', 'AUTENTICACION', 'perfil:editar', 'Permite actualizar el perfil propio.', TRUE),
    ('Ver usuarios', 'AUTENTICACION', 'usuarios:ver', 'Permite consultar usuarios del sistema.', TRUE),
    ('Crear usuarios', 'AUTENTICACION', 'usuarios:crear', 'Permite registrar usuarios desde administracion.', TRUE),
    ('Editar usuarios', 'AUTENTICACION', 'usuarios:editar', 'Permite modificar usuarios existentes.', TRUE),
    ('Desactivar usuarios', 'AUTENTICACION', 'usuarios:desactivar', 'Permite desactivar usuarios.', TRUE),
    ('Ver roles', 'AUTENTICACION', 'roles:ver', 'Permite consultar roles del sistema.', TRUE),
    ('Crear roles', 'AUTENTICACION', 'roles:crear', 'Permite crear roles del sistema.', TRUE),
    ('Editar roles', 'AUTENTICACION', 'roles:editar', 'Permite modificar roles.', TRUE),
    ('Desactivar roles', 'AUTENTICACION', 'roles:desactivar', 'Permite desactivar roles.', TRUE),
    ('Editar permisos de roles', 'AUTENTICACION', 'roles:permisos:editar', 'Permite asignar permisos a roles.', TRUE),
    ('Ver bitacora', 'AUTENTICACION', 'bitacora:ver', 'Permite consultar la bitacora del sistema.', TRUE),
    ('Exportar bitacora', 'AUTENTICACION', 'bitacora:exportar', 'Permite exportar registros de bitacora.', TRUE),

    ('Ver ciudades', 'ADMINISTRACION', 'ciudades:ver', 'Permite consultar ciudades.', TRUE),
    ('Crear ciudades', 'ADMINISTRACION', 'ciudades:crear', 'Permite crear ciudades.', TRUE),
    ('Editar ciudades', 'ADMINISTRACION', 'ciudades:editar', 'Permite modificar ciudades.', TRUE),
    ('Desactivar ciudades', 'ADMINISTRACION', 'ciudades:desactivar', 'Permite desactivar ciudades.', TRUE),
    ('Ver sucursales', 'ADMINISTRACION', 'sucursales:ver', 'Permite consultar sucursales.', TRUE),
    ('Crear sucursales', 'ADMINISTRACION', 'sucursales:crear', 'Permite crear sucursales.', TRUE),
    ('Editar sucursales', 'ADMINISTRACION', 'sucursales:editar', 'Permite modificar sucursales.', TRUE),
    ('Desactivar sucursales', 'ADMINISTRACION', 'sucursales:desactivar', 'Permite desactivar sucursales.', TRUE),
    ('Ver empleados', 'ADMINISTRACION', 'empleados:ver', 'Permite consultar empleados.', TRUE),
    ('Crear empleados', 'ADMINISTRACION', 'empleados:crear', 'Permite crear empleados.', TRUE),
    ('Editar empleados', 'ADMINISTRACION', 'empleados:editar', 'Permite modificar empleados.', TRUE),
    ('Desactivar empleados', 'ADMINISTRACION', 'empleados:desactivar', 'Permite desactivar empleados.', TRUE),
    ('Ver proveedores', 'ADMINISTRACION', 'proveedores:ver', 'Permite consultar proveedores.', TRUE),
    ('Crear proveedores', 'ADMINISTRACION', 'proveedores:crear', 'Permite crear proveedores.', TRUE),
    ('Editar proveedores', 'ADMINISTRACION', 'proveedores:editar', 'Permite modificar proveedores.', TRUE),
    ('Desactivar proveedores', 'ADMINISTRACION', 'proveedores:desactivar', 'Permite desactivar proveedores.', TRUE),
    ('Gestionar tallas', 'ADMINISTRACION', 'tallas:gestionar', 'Permite administrar tallas.', TRUE),
    ('Gestionar colores', 'ADMINISTRACION', 'colores:gestionar', 'Permite administrar colores.', TRUE),
    ('Gestionar marcas', 'ADMINISTRACION', 'marcas:gestionar', 'Permite administrar marcas.', TRUE),
    ('Gestionar temporadas', 'ADMINISTRACION', 'temporadas:gestionar', 'Permite administrar temporadas.', TRUE),
    ('Gestionar colecciones', 'ADMINISTRACION', 'colecciones:gestionar', 'Permite administrar colecciones.', TRUE),

    ('Ver catalogo', 'CATALOGO', 'catalogo:ver', 'Permite consultar el catalogo publico o interno.', TRUE),
    ('Ver productos', 'CATALOGO', 'productos:ver', 'Permite consultar productos.', TRUE),
    ('Crear productos', 'CATALOGO', 'productos:crear', 'Permite crear productos.', TRUE),
    ('Editar productos', 'CATALOGO', 'productos:editar', 'Permite modificar productos.', TRUE),
    ('Desactivar productos', 'CATALOGO', 'productos:desactivar', 'Permite desactivar productos.', TRUE),
    ('Gestionar precios', 'CATALOGO', 'productos:precios:gestionar', 'Permite administrar precios de productos.', TRUE),
    ('Gestionar promociones', 'CATALOGO', 'productos:promociones:gestionar', 'Permite administrar promociones.', TRUE),
    ('Ver variantes', 'CATALOGO', 'variantes:ver', 'Permite consultar variantes de productos.', TRUE),
    ('Crear variantes', 'CATALOGO', 'variantes:crear', 'Permite crear variantes de productos.', TRUE),
    ('Editar variantes', 'CATALOGO', 'variantes:editar', 'Permite modificar variantes.', TRUE),
    ('Desactivar variantes', 'CATALOGO', 'variantes:desactivar', 'Permite desactivar variantes.', TRUE),
    ('Ver detalle de prenda', 'CATALOGO', 'detalle_prenda:ver', 'Permite consultar el detalle de una prenda.', TRUE),
    ('Ver disponibilidad', 'CATALOGO', 'disponibilidad:ver', 'Permite consultar disponibilidad por sucursal.', TRUE),
    ('Usar vestidor virtual', 'CATALOGO', 'vestidor:usar', 'Permite usar el vestidor virtual.', TRUE),
    ('Gestionar assets de vestidor', 'CATALOGO', 'vestidor:gestionar_assets', 'Permite administrar assets del vestidor virtual.', TRUE),

    ('Ver carrito', 'RESERVAS', 'carrito:ver', 'Permite consultar carrito de compras.', TRUE),
    ('Gestionar carrito', 'RESERVAS', 'carrito:gestionar', 'Permite agregar o quitar items del carrito.', TRUE),
    ('Ver reservas', 'RESERVAS', 'reservas:ver', 'Permite consultar reservas.', TRUE),
    ('Crear reservas', 'RESERVAS', 'reservas:crear', 'Permite crear reservas.', TRUE),
    ('Confirmar reservas', 'RESERVAS', 'reservas:confirmar', 'Permite confirmar reservas.', TRUE),
    ('Cancelar reservas', 'RESERVAS', 'reservas:cancelar', 'Permite cancelar reservas.', TRUE),
    ('Entregar reservas', 'RESERVAS', 'reservas:entregar', 'Permite marcar reservas como entregadas.', TRUE),
    ('Ver favoritos', 'RESERVAS', 'favoritos:ver', 'Permite consultar prendas favoritas.', TRUE),
    ('Gestionar favoritos', 'RESERVAS', 'favoritos:gestionar', 'Permite agregar o quitar prendas favoritas.', TRUE),

    ('Ver inventario', 'VENTAS_INVENTARIO', 'inventario:ver', 'Permite consultar inventario.', TRUE),
    ('Editar minimos de inventario', 'VENTAS_INVENTARIO', 'inventario:minimos:editar', 'Permite editar stock minimo.', TRUE),
    ('Ver movimientos de inventario', 'VENTAS_INVENTARIO', 'inventario:movimientos:ver', 'Permite consultar movimientos de inventario.', TRUE),
    ('Crear movimientos de inventario', 'VENTAS_INVENTARIO', 'inventario:movimientos:crear', 'Permite registrar entradas, salidas o ajustes.', TRUE),
    ('Ver transferencias de stock', 'VENTAS_INVENTARIO', 'inventario:transferencias:ver', 'Permite consultar transferencias.', TRUE),
    ('Crear transferencias de stock', 'VENTAS_INVENTARIO', 'inventario:transferencias:crear', 'Permite transferir stock entre sucursales.', TRUE),
    ('Ver ventas presenciales', 'VENTAS_INVENTARIO', 'venta_presencial:ver', 'Permite consultar ventas presenciales.', TRUE),
    ('Registrar venta presencial', 'VENTAS_INVENTARIO', 'venta_presencial:crear', 'Permite registrar ventas presenciales.', TRUE),
    ('Anular venta presencial', 'VENTAS_INVENTARIO', 'venta_presencial:anular', 'Permite anular ventas presenciales.', TRUE),
    ('Crear pagos', 'VENTAS_INVENTARIO', 'pagos:crear', 'Permite crear ordenes o registros de pago.', TRUE),
    ('Ver pagos', 'VENTAS_INVENTARIO', 'pagos:ver', 'Permite consultar pagos.', TRUE),

    ('Ver reportes', 'INTELIGENCIA', 'reportes:ver', 'Permite consultar reportes.', TRUE),
    ('Generar reportes', 'INTELIGENCIA', 'reportes:generar', 'Permite generar reportes bajo demanda.', TRUE),
    ('Exportar reportes', 'INTELIGENCIA', 'reportes:exportar', 'Permite descargar reportes.', TRUE),
    ('Generar reportes por voz', 'INTELIGENCIA', 'reportes:voz', 'Permite solicitar reportes por comando de voz.', TRUE),
    ('Ver dashboard', 'INTELIGENCIA', 'dashboard:ver', 'Permite consultar dashboards.', TRUE),
    ('Usar recomendaciones', 'INTELIGENCIA', 'recomendaciones:usar', 'Permite recibir recomendaciones mediante IA.', TRUE),
    ('Gestionar recomendaciones', 'INTELIGENCIA', 'recomendaciones:gestionar', 'Permite administrar datos de recomendaciones.', TRUE),
    ('Consultar chatbot', 'INTELIGENCIA', 'chatbot:consultar', 'Permite usar el asistente virtual.', TRUE),
    ('Gestionar chatbot', 'INTELIGENCIA', 'chatbot:gestionar', 'Permite administrar configuracion del chatbot.', TRUE)
ON CONFLICT (modulo, accion) DO UPDATE
SET nombre = EXCLUDED.nombre,
    descripcion = EXCLUDED.descripcion,
    activo = TRUE;

WITH rol_admin AS (
    SELECT id FROM rol WHERE nombre = 'ADMINISTRADOR'
), permisos_admin AS (
    SELECT id FROM permiso WHERE activo = TRUE
)
INSERT INTO rol_permiso (rol_id, permiso_id, activo)
SELECT rol_admin.id, permisos_admin.id, TRUE
FROM rol_admin
CROSS JOIN permisos_admin
ON CONFLICT (rol_id, permiso_id) DO UPDATE
SET activo = TRUE;

WITH rol_cliente AS (
    SELECT id FROM rol WHERE nombre = 'CLIENTE'
), permisos_cliente AS (
    SELECT id
    FROM permiso
    WHERE accion = ANY (ARRAY[
        'perfil:ver',
        'perfil:editar',
        'catalogo:ver',
        'productos:ver',
        'detalle_prenda:ver',
        'disponibilidad:ver',
        'vestidor:usar',
        'carrito:ver',
        'carrito:gestionar',
        'reservas:crear',
        'reservas:cancelar',
        'favoritos:ver',
        'favoritos:gestionar',
        'recomendaciones:usar',
        'chatbot:consultar'
    ])
)
INSERT INTO rol_permiso (rol_id, permiso_id, activo)
SELECT rol_cliente.id, permisos_cliente.id, TRUE
FROM rol_cliente
CROSS JOIN permisos_cliente
ON CONFLICT (rol_id, permiso_id) DO UPDATE
SET activo = TRUE;

WITH rol_cajero AS (
    SELECT id FROM rol WHERE nombre = 'CAJERO'
), permisos_cajero AS (
    SELECT id
    FROM permiso
    WHERE accion = ANY (ARRAY[
        'perfil:ver',
        'catalogo:ver',
        'productos:ver',
        'detalle_prenda:ver',
        'disponibilidad:ver',
        'reservas:ver',
        'reservas:confirmar',
        'reservas:entregar',
        'venta_presencial:ver',
        'venta_presencial:crear',
        'pagos:crear',
        'pagos:ver',
        'inventario:ver'
    ])
)
INSERT INTO rol_permiso (rol_id, permiso_id, activo)
SELECT rol_cajero.id, permisos_cajero.id, TRUE
FROM rol_cajero
CROSS JOIN permisos_cajero
ON CONFLICT (rol_id, permiso_id) DO UPDATE
SET activo = TRUE;

WITH rol_encargado AS (
    SELECT id FROM rol WHERE nombre = 'ENCARGADO_SUCURSAL'
), permisos_encargado AS (
    SELECT id
    FROM permiso
    WHERE accion = ANY (ARRAY[
        'perfil:ver',
        'catalogo:ver',
        'productos:ver',
        'detalle_prenda:ver',
        'disponibilidad:ver',
        'reservas:ver',
        'reservas:confirmar',
        'reservas:cancelar',
        'reservas:entregar',
        'inventario:ver',
        'inventario:minimos:editar',
        'inventario:movimientos:ver',
        'inventario:movimientos:crear',
        'inventario:transferencias:ver',
        'inventario:transferencias:crear',
        'venta_presencial:ver',
        'reportes:ver',
        'dashboard:ver'
    ])
)
INSERT INTO rol_permiso (rol_id, permiso_id, activo)
SELECT rol_encargado.id, permisos_encargado.id, TRUE
FROM rol_encargado
CROSS JOIN permisos_encargado
ON CONFLICT (rol_id, permiso_id) DO UPDATE
SET activo = TRUE;

WITH rol_personal AS (
    SELECT id FROM rol WHERE nombre = 'PERSONAL_VENTAS'
), permisos_personal AS (
    SELECT id
    FROM permiso
    WHERE accion = ANY (ARRAY[
        'perfil:ver',
        'catalogo:ver',
        'productos:ver',
        'detalle_prenda:ver',
        'disponibilidad:ver',
        'reservas:ver',
        'reservas:confirmar',
        'reservas:entregar',
        'venta_presencial:ver',
        'venta_presencial:crear',
        'inventario:ver',
        'chatbot:consultar'
    ])
)
INSERT INTO rol_permiso (rol_id, permiso_id, activo)
SELECT rol_personal.id, permisos_personal.id, TRUE
FROM rol_personal
CROSS JOIN permisos_personal
ON CONFLICT (rol_id, permiso_id) DO UPDATE
SET activo = TRUE;

COMMIT;
