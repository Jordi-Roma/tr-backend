# CU02 y CU03 — implementación web y Flutter

Fecha: 23 de octubre de 2026. Alcance autorizado: backend, web Angular y app Flutter de `TiendaAR`. Cambios locales; sin commit, push ni despliegue.

## CU02: sesión y recuperación de acceso

- El acceso comercial conserva la empresa elegida. La identidad del usuario, la sesión registrada en el servidor y el contexto de empresa deben coincidir. La administración SaaS mantiene su acceso separado en web.
- Se conservan el inicio/cierre de sesión, el registro de clientes y el bloqueo temporal por intentos fallidos existentes. Flutter incorpora selección de empresa por nombre antes del acceso, envío del contexto en las peticiones y restauración de sesiones compatibles. No crea una empresa predeterminada.
- Flutter descarta sesiones antiguas sin empresa, controla vencimiento, limpia el estado de carrito/favoritos/reservas/catálogo al cambiar de cuenta o empresa y descarta respuestas de solicitudes anteriores. Un 403 de permisos conserva la sesión; un 401 de la API autenticada obliga a ingresar nuevamente. No envía credenciales a otros servidores.
- La recuperación usa un código de seis dígitos enviado **al correo registrado de esa cuenta**. Ya no se dirige al buzón global `PASSWORD_RESET_EMAIL`. El servidor busca la cuenta exclusivamente dentro de la empresa indicada; sin empresa sólo admite cuentas activas ADMIN_SAAS.
- La solicitud mantiene una respuesta genérica para cuentas inexistentes, inactivas, de otra empresa o dentro del tiempo de reenvío. Hay un mínimo de 60 segundos entre solicitudes y cinco intentos incorrectos por código. El vencimiento usa `PASSWORD_RESET_TOKEN_MINUTES` (15 minutos por defecto).
- Los códigos se guardan como hash, son de un solo uso y su consumo se serializa: dos confirmaciones simultáneas no pueden aplicar el mismo código. Recuperar la contraseña invalida las sesiones y códigos anteriores.
- Antes de emitir un código se verifica nuevamente, bajo bloqueo, que el usuario y correo siguen siendo los consultados. Una solicitud en curso no emite códigos para una identidad que ya cambió.
- La apertura de sesión se serializa con los cambios de cuenta. Un ingreso que verificó datos anteriores a un cambio de contraseña, usuario, correo o desactivación no puede abrir una sesión después de ese cambio.

## CU03: cuenta y perfil del cliente

- Edición de nombre, apellido, teléfono, nombre de usuario y correo. El cliente no puede cambiar su empresa, rol, identificador de cuenta ni otro cliente mediante el formulario o agregando campos a la petición.
- Cambiar usuario o correo exige la contraseña actual. Al completarse se cierran todas las sesiones y se pide ingresar con los datos actualizados. Editar únicamente datos personales conserva la sesión y actualiza el nombre mostrado en la interfaz.
- Cambio de contraseña con contraseña actual, confirmación y política existente de contraseña segura. Cierra todas las sesiones y descarta códigos pendientes.
- Alta, consulta, edición y desactivación de direcciones propias, con ciudad disponible y selección de dirección principal. La comprobación de propiedad ocurre antes de modificar la dirección principal. Las modificaciones simultáneas de direcciones se serializan por cliente.
- Autodesactivación exclusiva de cuentas con rol CLIENTE, mediante contraseña actual y confirmación explícita. Desactiva el acceso del usuario, cierra sesiones e invalida recuperación. **Conserva el registro de cliente, compras, reservas, pagos y direcciones**; no ejecuta borrados del historial. La reactivación corresponde a la administración de la empresa por el mecanismo existente.
- Web incluye mensajes accesibles, contraste corregido, formularios identificados y diálogo con foco inicial, ciclo de Tab, Escape y restitución de foco. Flutter incorpora edición de perfil, recuperación, direcciones y autodesactivación con carga, error y confirmación. Una carga fallida del perfil permite reintentar y no permite guardar campos vacíos.

## Migración y publicación

Se añade `database/migracion_cu02_cu03_01.sql`, registrada como `2026_10_23_cu02_cu03_01` en `init_db.py`. Agrega el contador `intentos` de recuperación, sin recrear tablas ni modificar el historial comercial. El migrador versionado debe ejecutarse antes de iniciar el backend actualizado; no hace falta repetir el plan multitenant.

La publicación debe incluir las versiones compatibles de backend y web. Flutter necesita generar y distribuir una nueva versión para que sus usuarios reciban estas pantallas y el contexto de empresa. Las sesiones móviles antiguas pedirán un nuevo ingreso.

El envío real requiere la configuración SMTP existente: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` y `SMTP_FROM`. No se modificaron secretos ni destinos de infraestructura. La dirección de destino se obtiene de la cuenta, nunca de un campo libre del formulario de recuperación.

## Validación y límites

Las pruebas de integración usan PostgreSQL 16 local y bases nuevas desechables `stylear_test_*`, con empresas y cuentas ficticias. La base del navegador es independiente de la suite backend para evitar interferencias con las pruebas de restauración y referencias globales. No se conectaron a Railway ni a la base del proyecto.

La recuperación se probó con captura de correo exclusiva de las pruebas; no se enviaron mensajes reales. La fixture del navegador no agrega endpoints de prueba a la aplicación. Sus archivos temporales de cuentas/códigos están excluidos de Git. Ninguno de esos datos se incorpora al arranque de producción.

Resultados locales confirmados:

| Verificación | Resultado |
| --- | --- |
| Backend: 50 regresiones y 18 casos de cuenta con PostgreSQL independiente | 68 pruebas aprobadas |
| Angular: pruebas unitarias | 14 pruebas aprobadas |
| Angular: compilación de producción | Aprobada; advertencias existentes de Leaflet y QRCode |
| Flutter: análisis estático | Sin incidencias |
| Flutter: sesión y pantallas | 20 pruebas aprobadas |
| Flutter: compilación Web | Aprobada |
| Navegador: suite completa en Edge | 23 pruebas aprobadas, con AXE y comprobaciones de foco/teclado |

Los 18 casos nuevos de backend cubren identidad, contraseña actual, duplicados y rollback, empresa/roles inmutables, aislamiento entre clientes y empresas, principal concurrente, conservación de reservas y direcciones, revocación de sesiones/códigos, recuperación genérica, correo de destino, vencimiento, intentos, uso único, consumo concurrente y recuperación SaaS separada. También incluyen ingreso o solicitud de recuperación simultáneos con modificación de credenciales o baja. Las otras 50 pruebas cubren las regresiones multitenant, sesiones, reportes, devoluciones y probador anteriores. La suite completa aprobó con 66 casos; después se añadieron dos comprobaciones de emisión concurrente y se reejecutaron los 18 casos de cuenta con éxito.

El análisis y las pruebas de Flutter verifican lógica y pantallas. No equivalen a una prueba en un teléfono físico ni a validar el envío real del proveedor SMTP en el despliegue.

## Trabajo preservado

Se conserva el motor Decart, el resultado por URL, la cámara y el flujo del probador aportado por la compañera. En Flutter sólo se integra el contexto de empresa/sesión en sus solicitudes y se controla el cierre de la pantalla durante la carga. No se cambió la confirmación QR. Los archivos de imágenes y documentos que ya estaban modificados o sin seguimiento en el backend no se descartaron ni se incluyeron en un commit.
