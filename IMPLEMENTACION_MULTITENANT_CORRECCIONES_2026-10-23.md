# Correcciones multitenant y preparación del frontend

Fecha: 23 de octubre de 2026. Carpeta: `TiendaAR/tr-backend`.

## Cambios de esta intervención

- Se restauraron el procesamiento de imagen y la respuesta por URL del probador a su versión anterior al cambio de formato Base64. Se conserva la selección de producto por empresa; no se rediseñaron el motor ni las pantallas. Los archivos de imágenes ya modificados antes de esta intervención se preservaron.
- La confirmación QR se mantuvo como solicitó Jordi: no se modificó su servicio ni su recorrido de confirmación.
- Se añadió empresa obligatoria a los repositorios, servicios y rutas de categorías, tallas, colores y marcas: altas, nombres, lecturas, cambios, activación/desactivación y categorías recursivas.
- Se separó la identidad de una empresa suspendida del permiso para iniciar operaciones nuevas. Login y consultas siguen disponibles; la dependencia de autorización distingue consultas/trámites pendientes de altas nuevas.
- Una suscripción vencida/suspendida, un plan inactivo o una empresa suspendida bloquean las nuevas operaciones. Ventas presenciales, nuevas reservas y compras digitales verifican también dentro de su transacción.
- Se conservaron pagos de órdenes pendientes, devoluciones y gestión de reservas existentes. La consulta de plan/uso del AD sigue disponible.
- Se completó la cuota de cuentas activas, incluyendo registro de clientes, alta administrativa, alta de empleado con usuario y reactivación. Las cuotas se cuentan tras bloquear la empresa en la misma transacción.
- Se añadió la restricción de función de reportes y se mantuvieron las de asistente, recomendaciones y vestidor. Las consultas no requieren vigencia, pero siguen sujetas a las funciones configuradas. El plan de transición conserva las funciones omitidas; permite deshabilitarlas explícitamente.
- Se añadieron edición de planes, edición de nombre de empresa y consulta de uso/estado efectivo. Los códigos de empresa son estables. Solo se aceptan claves de límites/funciones que el backend implementa.
- Se añadieron eventos de plataforma transaccionales para altas/cambios SaaS y operaciones de respaldo. El actor AS y la empresa afectada quedan separados de la bitácora comercial.
- Se añadieron respaldos cifrados globales y selectivos, previsualización, restauración, eliminación y purga por conservación configurada.

## Migraciones y despliegue

Se conserva `2026_10_23_multitenant_01`. La nueva versión `2026_10_23_multitenant_02` crea `evento_plataforma` y `respaldo`, y permite diferir las comprobaciones FK durante la restauración selectiva. Las operaciones normales conservan comprobación inmediata.

`init_db.py` registra cada versión una sola vez y el arranque de la API exige la versión 02. No desplegar el código sin completar la migración y los clientes compatibles.

**No se migró la base real ni Railway.** Las migraciones se ejecutaron en bases PostgreSQL 16 temporales, locales y vacías, con datos ficticios. También se ensayó una base con registros anteriores al multitenant y se comprobó la conservación de IDs y asignación a StyleAR, sin elevar su administrador a AS.

Antes de producción sigue siendo necesario ensayar una copia autorizada de los datos reales, verificar conteos/saldos, disponer de un respaldo restaurable, coordinar versiones web/APK y revisar el despliegue real. No se hizo push, merge ni despliegue.

## Configuración privada de respaldos

Configurar en el servidor, fuera de Git y del navegador:

| Variable | Uso |
| --- | --- |
| `STYLEAR_BACKUP_DIR` | Directorio privado y persistente para archivos cifrados, fuera de `/static` |
| `STYLEAR_BACKUP_KEY` | Clave Fernet válida, custodiada fuera del código y conservada de manera recuperable |
| `STYLEAR_BACKUP_RETENTION_DAYS` | Conservación elegida por el operador: entero entre 1 y 3650 |
| `STYLEAR_RESTORE_DATABASE_URL` | Base de ensayo vacía para restauración global, distinta de la activa |
| `STYLEAR_RESTORE_ASSETS_DIR` | Carpeta vacía de ensayo para sus archivos, distinta de los assets activos |

No se eligieron una ubicación real, clave ni plazo por Jordi. Hasta configurarlos, las operaciones que los requieren devuelven 503; esto evita escribir respaldos privados en un destino público por defecto. El cliente no debe solicitar ni recibir esos secretos.

El contenedor incluye `postgresql-client`; `pg_dump` debe ser compatible con la versión del servidor. En las pruebas locales se usaron las herramientas PostgreSQL 16 instaladas. No se construyó la imagen Docker ni se comprobó su ejecución en Railway en esta intervención.

### Alcance de las copias y restauraciones

- Global: dump de PostgreSQL con instantánea exportada más archivos locales estáticos; paquete cifrado. La restauración implementada utiliza una base y una carpeta de ensayo vacías. No sobrescribe la base activa. El eventual reemplazo de producción exige un procedimiento de mantenimiento y aprobación independiente.
- Por empresa: registros propios y tablas hijas detectadas por sus relaciones; archivos locales referenciados; referencias globales para validación. La restauración reemplaza únicamente los registros de la empresa original suspendida, en una transacción. Rechaza cambios de esquema/referencias globales, conflictos de IDs y archivos compartidos que difieren.
- Se comparan las filas restauradas y las de otras empresas antes de confirmar. Las sesiones y códigos de recuperación restaurados se invalidan deliberadamente.
- Si un archivo local referenciado falta, el respaldo selectivo se rechaza. Los recursos alojados en servicios externos conservan sus URLs; no se descargan ni se garantizan copias de esos servicios.
- No hay descarga pública de respaldos desde la API. AS ve metadatos y acciona procesos auditados. El operador que custodia los archivos y la clave posee capacidad excepcional de descifrado y debe mantenerlos privados.
- La purga de vencidos es una operación explícita de AS. Si se desea ejecución programada, el operador debe programarla con la política acordada; no se creó una automatización en este chat.
- Las restauraciones de base no revierten eventos externos de Stripe. El global se restaura en ensayo y la empresa permanece suspendida hasta revisión antes de volver a operar.

## Verificación

Las pruebas de integración son optativas en la suite: requieren `STYLEAR_TEST_DATABASE_URL` explícita, igual a `DATABASE_URL`, host local y una base con prefijo `stylear_test_`. Sin ese destino se omiten; no toman la base real desde `.env`.

Se comprobaron migración repetida, datos heredados, catálogos de A/B, nombres y SKU repetidos, rechazo de relaciones cruzadas, rutas HTTP con sesiones reales, suspensión/vencimiento, cuotas concurrentes, última unidad reservada concurrentemente, respaldo/restauración por empresa con archivos y restauración global en un destino vacío. Resultado final: **40 pruebas aprobadas**, con tres advertencias de deprecación; incluye las pruebas de integración reales sobre PostgreSQL temporal. El clúster de pruebas se cerró y eliminó al terminar.

No se probaron cobros externos reales, el motor visual con cámara/teléfono, la UI Angular/Flutter ni todos los recorridos comerciales sobre datos de producción. Las advertencias actuales de deprecación de multipart/startup son anteriores a estas correcciones.

El siguiente paso de clientes está documentado en `../PLAN_FRONTEND_MULTITENANT_STYLEAR.md`. La web y Flutter no se modificaron en esta intervención.

## Integración posterior con GitHub: 23 de octubre de 2026

Al actualizar `main` se incorporaron los commits remotos hasta `24edfd8`. Esos cambios ya incluían Decart Lucy VTON, streaming en vivo y alternancia de cámara frontal/trasera. Se conservaron ese motor, las dependencias remotas y el contrato fotográfico por URL. La incorporación de Decart procede del historial remoto, no de una sustitución del motor solicitada por el plan multitenant.

Se resolvieron los conflictos del router de vestidor y del servicio de devoluciones combinando ambas versiones. Las rutas nuevas de streaming ahora reciben el contexto de empresa, consultan prendas de ese ámbito y vinculan las sesiones en memoria a su empresa. La vista en vivo propaga el código a sus peticiones internas. Pausar una sesión propia sigue permitido tras suspender la empresa, para cerrar el consumo existente. En devoluciones se conserva tanto el filtro por empresa como el 404 remoto cuando no se encuentra una devolución ya reembolsada.

Se añadieron nueve regresiones en `tests/test_integracion_cambios_remotos.py`: imagen por empresa, rechazo de prenda ajena, creación y cambio de sesión, rechazo de sesiones de otra empresa, pausa con suspensión, contexto obligatorio, conservación del visor/cámaras y devolución no encontrada. Resultado de `python -m pytest tests -q --maxfail=1`: **34 aprobadas, una suite omitida y tres advertencias de deprecación**. La suite omitida exige PostgreSQL temporal explícito; esta ejecución no conectó a datos reales ni a Decart/Stripe. No se volvieron a probar la cámara física ni las inferencias externas.
