# CU11–CU15 — Implementación integrada

## Alcance y plataformas

| CU | Backend | Web | Flutter |
|---|---|---|---|
| CU11 — Catálogo y disponibilidad | Sí | Sí | Sí |
| CU12 — Carrito | Sí | Sí | Sí |
| CU13 — Reservas | Sí | Sí | Sí |
| CU14 — Inventario y movimientos | Sí | Sí | No se agregan pantallas |
| CU15 — Ventas presenciales | Sí | Sí | No se agregan pantallas |

Se reutilizan los seis módulos del proyecto. No se implementan CU16–CU20 ni
sincronización offline/PWA (CU21). Se conserva el recorrido de confirmación QR
y el probador. Los cambios de color en botones QR son de contraste accesible.

## Reglas acordadas

- Las reservas nuevas son gratuitas, sin anticipo obligatorio, y duran siete
  días desde su creación. La cita se elige entre hoy y los próximos siete días.
- Continúa el máximo de dos unidades de una misma variante por reserva.
- Las reservas anteriores conservan estado, anticipo, pagos, referencias y su
  vencimiento original. No se convierten masivamente a la nueva política.
- El carrito no aparta unidades. Reservar o vender vuelve a validar precio,
  estado de la prenda y existencias dentro de una transacción.
- El precio se conserva al reservar. Al finalizar se descuentan las unidades
  elegidas y se liberan las no compradas.
- El cajero de la sucursal puede consultar, preparar, atender y finalizar una
  reserva mediante la venta correspondiente. La cancelación administrativa
  corresponde a administrador/encargado; el cliente puede cancelar la propia.
- Los descuentos manuales de ventas presenciales corresponden a administrador
  o encargado. No pueden ser negativos ni superar el importe de su línea.
- Los documentos son notas de venta comerciales PDF, no facturas fiscales.
  La empresa vendedora y su sucursal son emisoras; StyleAR es la plataforma.
- El plazo de cambio de prendas compradas pertenece a CU19 y no se fija aquí.

## Integridad, concurrencia y continuidad

La escritura del carrito se serializa por cliente. Las existencias se bloquean
por empresa, sucursal y variante; las transferencias toman sus bloqueos en un
orden estable y sus dos movimientos se confirman juntos. Las salidas respetan
el stock reservado. Una operación fallida revierte cabecera, detalles y stock.

Las solicitudes nuevas de reserva, venta, movimiento y transferencia admiten
`clave_operacion` UUID. La misma clave, usuario y empresa devuelven el recurso
original si el contenido coincide; otro contenido se rechaza. Los clientes web
y móvil agregan estas claves en las operaciones correspondientes y las
conservan ante respuestas inciertas. Las claves son opcionales en la API para
mantener compatibilidad con clientes anteriores; su protección requiere
reenviar la misma clave. Esto no sustituye CU21 ni permite ventas offline.

No se puede marcar una reserva `COMPLETADA` desde el selector de estado:
finalizar requiere registrar la venta y sus movimientos. Repetir el cierre
presencial con los mismos datos no crea otra venta; datos distintos se rechazan.

Las reservas vencidas se liberan en una transacción, una sola vez, con
trazabilidad. La API lo comprueba al consultar disponibilidad o iniciar
operaciones y tiene además una tarea periódica de 60 segundos mientras está
activa. Con la API apagada, la liberación se realiza al volver a atender esas
operaciones o en el siguiente ciclo de la tarea. El instante de vencimiento
guardado siempre es creación + siete días.

Las fechas comerciales de precios, promociones, citas y suscripción usan
`America/La_Paz`, independientemente de la zona predeterminada de Railway.
Con suscripción vencida continúan consultas, documentos y resolución de
reservas existentes según la política previa; se bloquean operaciones nuevas.

## Catálogo y carrito

Se corrigió el detalle por sucursal y se alinearon filtro/orden de precios con
el precio efectivo de las promociones. No se ofrece stock de sucursales
inactivas. Una prenda retirada del catálogo permanece identificable en un
carrito existente, muestra su indisponibilidad y puede retirarse.

Flutter incorpora filtros por talla, color, temporada, colección, rango de
precio y orden, junto con paginación; una respuesta tardía no sustituye una
búsqueda posterior. Se conservan las funciones anteriores de catálogo.

## Notas de venta

La venta presencial y la emisión inicial se confirman en la misma transacción.
La numeración es consecutiva por empresa, compartida entre sus sucursales.
Se guarda una instantánea de emisor, sucursal, vendedor, cliente, líneas,
precios, descuentos, pago y condiciones. Una nota emitida no se reescribe al
editar después el catálogo, el nombre o las condiciones de la empresa.

Para ventas históricas sin nota se permite emitirla al solicitarla por primera
vez. En ese caso los nombres y datos descriptivos disponibles se capturan en
esa primera emisión; no se inventa una instantánea histórica inexistente.

El administrador configura el logo opcional y condiciones de futuras notas.
El logo se valida como imagen, se guarda bajo un nombre nuevo y no reemplaza
el archivo de notas anteriores. Utiliza `static/empresas/`, con la misma
necesidad de almacenamiento persistente y respaldo que los demás archivos
estáticos del proyecto.

El personal autorizado descarga el PDF o lo envía al correo registrado del
cliente asociado a la venta. No se admite un destinatario arbitrario enviado
por el navegador. Una venta a consumidor final sin cliente/correo permite
descargar el PDF; enviarlo requiere asociar un cliente con correo al registrar.
Si SMTP falla, la venta y el documento siguen disponibles y se puede reintentar
el envío. No se simula un envío exitoso en producción.

Los selectores de venta/inventario son consultas comerciales separadas de los
CRUD administrativos de CU08/CU10: no conceden edición de proveedores/prendas
al cajero o al encargado.

## Migración y despliegue

Migración versionada: `2026_10_27_cu11_cu15_01`, en
`database/migracion_cu11_cu15_01.sql`, registrada en `init_db.py`.
Agrega metadatos de reserva gratuita/cierre, registro de reintentos,
configuración de comprobantes, numeración e instantáneas de notas, y la función
de precio efectivo. No borra ventas, movimientos, reservas ni anticipos.

La API comprueba esta versión al iniciar. Aplicar mediante el inicializador
habitual con respaldo previo, nunca ejecutando SQL suelto ni marcando versiones
manualmente. Esta implementación se prueba en bases desechables; no se ejecuta
el inicializador contra la base real durante el desarrollo.

Coordinar publicación del backend con web y Flutter para que los clientes
actualizados muestren las reservas nuevas como gratuitas. Se mantiene lectura
compatible de reservas anteriores con anticipo.

## Verificación

- PostgreSQL real y desechable: recorridos CU11–CU15, aislamiento, carreras de
  stock, transacciones, reintentos, estados, vencimiento, PDF y correo capturado.
- Regresión del backend incluyendo CU01–CU10 y funcionalidades existentes.
- Angular: compilación, pruebas unitarias y recorridos Playwright/AXE con API
  y PostgreSQL reales en otra base desechable.
- Flutter: análisis y pruebas de modelos, proveedores, filtros, paginación,
  reintentos y formularios; no constituye prueba en un teléfono físico.
- SMTP se captura exclusivamente en fixtures; el envío real requiere probar
  la configuración de correo del entorno de despliegue.

Las dependencias de desarrollo del backend están en `requirements-dev.txt`.
La suite exige `DATABASE_URL` y `STYLEAR_TEST_DATABASE_URL` iguales, con destino
local `stylear_test_*`; no ejecutarla contra una base de negocio.

## Resultado de la verificación local — 27/10/2026

- Backend: **223 pruebas distintas aprobadas**. La regresión completa pasó con
  221; la revisión comercial final pasó sus 20, incluyendo dos pruebas nuevas
  de configuración de notas y reingreso de una prenda retirada del catálogo.
- La migración completa se aplicó en bases PostgreSQL locales nuevas; el
  inicializador reconoce las versiones aplicadas sin repetirlas.
- Web: **16 pruebas unitarias aprobadas**, compilación de producción correcta,
  **7 recorridos CU11–CU15 y 2 de regresión aprobados** con Edge/Playwright.
  AXE no detectó infracciones en las pantallas comprobadas. La regresión incluye
  cambio de empresa y el modal/confirmación QR anteriores. Las comprobaciones
  finales se ejecutaron en tandas; el envío verifica la nota de la venta creada,
  sin seleccionar una venta histórica de la fixture.
- Flutter: **32 pruebas aprobadas**, incluidos filtros, paginación, respuesta
  tardía, reintento de reserva y navegación del cajero sin CU14/CU15 móviles.
- El PDF se inspeccionó visualmente y se probó su extracción de texto; el logo
  y las condiciones se verificaron por empresa y se conservan en notas previas.
- Se verificaron los hashes de los siete archivos locales previos del backend:
  permanecen intactos. Se conserva el stash móvil previo a esta implementación.

Estado de entrega: **cambios locales, sin commit, push ni despliegue de este
bloque**. No se aplicó la migración a la base real. Pendiente de comprobar en
el entorno publicado: envío SMTP real, persistencia de logos y uso en teléfono
físico. Los datos de prueba permanecen exclusivamente en fixtures y bases
locales desechables, fuera de la aplicación publicada.

El análisis final de los 14 archivos Flutter modificados/nuevos terminó sin
observaciones. Los avisos del build Angular corresponden a dependencias
CommonJS existentes (`leaflet` y `qrcode`); la compilación finalizó con éxito.
