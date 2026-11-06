# CU26 — Backend de planes y suscripciones

Implementado en los módulos existentes de Administración, Inteligencia y Autenticación, con la política compartida en `app/core/plan_empresa.py`. No se agregaron módulos ni pantallas.

## Configuración comercial

Básico, Intermedio y Premium se inicializan mediante la migración versionada `2026_11_05_cu26_planes`, sin reasignar empresas y sin reemplazar claves explícitas de planes ya existentes. El nombre o código de un plan no determina las reglas en ejecución: las condiciones se leen de la configuración persistida.

Las condiciones editables son las acordadas: cupos de usuarios, empleados y sucursales; PDF, Excel, interpretación, voz y programación de reportes; copias manuales y automáticas, frecuencia, horario configurable y retención.

Reportes básicos, mayorista, delivery, asistente, recomendaciones y vestidor no son diferenciadores comerciales. Se conservan los permisos del usuario y la vigencia aplicable a cada operación. Las claves antiguas de productos se mantienen compatibles, sin incorporarlas al nuevo catálogo comercial.

Usuarios cuenta todas las cuentas activas de la empresa, incluidos clientes y personal. Un empleado con cuenta consume ambos cupos. Las reducciones no borran cuentas ni impiden el acceso básico.

Los planes incluyen descripción, condiciones, precio de referencia y moneda. El precio inicial es cero, editable; no se agregó un sistema de cobro de suscripciones.

## API SaaS

Todas las rutas SaaS requieren ADMIN_SAAS.

| Operación | Ruta |
| --- | --- |
| Listar y crear planes | `GET /api/v1/saas/planes`, `POST /api/v1/saas/planes` |
| Catálogo de opciones, unidades y dependencias | `GET /api/v1/saas/planes/catalogo` |
| Comparar configuración de planes | `GET /api/v1/saas/planes/comparacion` |
| Cantidades de empresas por plan | `GET /api/v1/saas/planes/resumen` |
| Empresas, búsqueda y paginación | `GET /api/v1/saas/planes/empresas` |
| Previsualizar cambios | `POST /api/v1/saas/planes/{id}/previsualizar` |
| Guardar cambios confirmados | `PUT /api/v1/saas/planes/{id}` |
| Historial de cambios del plan | `GET /api/v1/saas/planes/{id}/historial` |
| Asignar, cambiar o renovar una suscripción | `POST /api/v1/saas/empresas/{id}/suscripcion` |
| Historial de suscripciones de la empresa | `GET /api/v1/saas/empresas/{id}/suscripciones` |
| Política y uso de una empresa | `GET /api/v1/saas/empresas/{id}/plan` |

La lista paginada acepta `plan_id`, `estado`, `buscar`, `pagina` y `tamano` (máximo 100). Los totales cuentan una empresa una sola vez según su suscripción más reciente; distinguen asignadas, vigentes y no vigentes.

Publicar u ocultar utiliza `publico`. Desactivar utiliza `activo` e interrumpe las operaciones nuevas de las empresas suscritas: la previsualización muestra este efecto.

## Previsualización y guardado

Enviar al endpoint de previsualización los campos que se desea cambiar. Se devuelve la propuesta combinada con los valores actuales, las empresas afectadas, sus excesos de uso, las programaciones que se pausarán y un `token_previsualizacion`.

Para guardar, enviar los mismos cambios —o la propuesta completa— junto con ese token. La API vuelve a calcular el impacto dentro de la transacción. Si cambió la revisión, el uso o una programación relevante, devuelve 409 y requiere previsualizar nuevamente. La edición omitiendo campos conserva sus valores anteriores; los diccionarios de funciones y límites se combinan por clave.

La política valida claves, tipos, mínimos y dependencias. Los días de frecuencia y retención admiten de 1 a 3650. Cero en un cupo significa que no hay altas permitidas; no significa ilimitado. Los límites históricos ausentes conservan el significado anterior de sin límite. No se admite `null` para borrar un cupo mediante una edición.

El historial registra actor, fecha, antes, después e impacto. Se conserva además la auditoría de asignación de suscripciones.

## Capacidades para los clientes

`GET /api/v1/mi-empresa/capacidades` está disponible a usuarios autenticados de empresa. Devuelve identidad y revisión del plan, vigencia, capacidades incluidas y habilitadas, motivos de bloqueo, límites, uso, disponibilidad de cupos y catálogo.

Las capacidades del plan se vuelven a consultar en el servidor. Una sesión abierta no conserva permisos comerciales retirados. La consulta existente `/api/v1/mi-empresa/plan` permanece disponible para administradores.

## Reportes

Los controles de PDF, Excel e interpretación se aplican en sus API. `POST /api/v1/reportes/interpretar` acepta `origen: TEXTO | VOZ`; VOZ exige también el permiso correspondiente. El cliente todavía debe conectar ese permiso al micrófono: una API que recibe una transcripción no puede demostrar si se dictó o escribió.

Las programaciones aceptan frecuencia diaria, semanal o mensual, hora, día, zona horaria, destinatario, formato, sucursal, filtros y un período relativo. Por defecto se envía el día anterior, la semana anterior o el mes anterior, según la frecuencia. En meses cortos, el día 31 se ajusta al último día del mes.

El ejecutor revisa pendientes cada minuto. Usa bloqueos y un registro único por reporte/ocurrencia para evitar ejecuciones simultáneas y repetición automática de un intento reclamado. Verifica plan, vigencia, formato, sucursal y que el creador siga siendo administrador activo de la empresa. Los ejemplos históricos sin creador se pausan para evitar envíos no solicitados.

La ejecución manual ahora genera y envía el archivo mediante el transporte de correo existente; respeta su configuración de destinatario fijo si la hay. El resultado se consulta en:

`GET /api/v1/reportes/programados/{id}/ejecuciones`

Una pérdida de conexión después de enviar puede dejar un intento INICIADO o FALLIDO sin certeza de entrega. No se reenvía automáticamente esa ocurrencia: revisar el historial antes de usar una ejecución manual. Esto evita prometer una entrega exactamente una vez que el transporte de correo no puede garantizar.

Al bajar el cupo o retirar un formato, se conservan las programaciones y se pausan las afectadas en orden estable por ID. Una mejora del plan no reactiva envíos pausados. Las altas y reactivaciones controlan el cupo dentro de una transacción.

## Respaldos CU25

Se reutilizaron el servicio y las rutas existentes de R2. La política compartida controla manuales, automáticos, frecuencia, hora editable y retención. Cambiar de plan restablece la hora fija de Bolivia cuando corresponde; el ejecutor también ignora horarios antiguos no permitidos.

La cuota manual usa los últimos siete días e incluye copias eliminadas. Automáticos y preventivos no consumen ese cupo. La retención nueva solo afecta copias nuevas. Desactivar creación de copias conserva la consulta y restauración de las disponibles.

La restauración por empresa genera una copia preventiva también cuando la solicita SaaS. La prueba con las tablas nuevas detectó referencias de integridad implementadas con triggers: la restauración ahora incluye esas dependencias al ordenar y reponer filas. La empresa debe estar suspendida para restaurarla y las otras empresas se verifican sin cambios.

La suscripción es información de plataforma y queda fuera de la restauración comercial. Restaurar una copia anterior no recupera un plan superior ni reinicia cuotas: al terminar se vuelven a aplicar las restricciones del plan actual a las programaciones restauradas.

R2 mantiene las variables existentes y la clave estable `STYLEAR_BACKUP_KEY`. No se incluyeron credenciales en los archivos.

## Migración y entrega

La nueva migración se ejecuta mediante `init_db.py`, después de CU25. Añade metadatos y revisión del plan, historial detallado, campos de programación y registro de ejecuciones. Las migraciones anteriores permanecen intactas.

La implementación local no publica commits ni despliega. El frontend web y Flutter siguen pendientes de conectar estas API. Los cambios locales de imágenes y documentos ajenos al CU26 se conservaron.

## Verificación

Las pruebas están en `tests/test_cu26_planes.py` y `tests/test_cu26_planes_integration.py`, junto con las pruebas existentes pertinentes de Reportes, fundamento multitenant y registro público.

Las integraciones requieren DATABASE_URL y STYLEAR_TEST_DATABASE_URL idénticas, con una base `stylear_test_*` en localhost. Se utilizó una base PostgreSQL 16 desechable, correo simulado y almacenamiento R2 en memoria. No se enviaron correos ni se utilizaron buckets reales.

Se verifican política, edición parcial, previsualizaciones obsoletas, historial, cambio y renovación de planes, conteos sin duplicados, roles, aislamiento, cupos concurrentes, pausas, ejecución y no duplicación de reportes, retención, horario y restauración.

Resultado: 57 pruebas de CU26, Reportes y fundamento multitenant aprobadas; otras 18 de registro y aprobación de empresas aprobadas. Las advertencias observadas corresponden a APIs de ciclo de vida y dependencias ya usadas por el proyecto.
