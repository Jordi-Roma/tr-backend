# CU26 — Gestionar planes y suscripciones

## Objetivo y alcance autorizado

Ampliar el backend existente de StyleAR para que el administrador SaaS configure los planes Básico, Intermedio y Premium, asigne suscripciones y consulte qué empresas utilizan cada plan. Las condiciones del plan deben aplicarse en el servidor y poder consultarse después desde web y mobile.

Este documento es la especificación para implementar CU26. Su creación no implica que lo aquí descrito esté implementado.

Trabajar primero en backend. La pantalla SaaS y la integración de web y Flutter corresponden a una etapa posterior. Preparar las API necesarias para esa pantalla, sin construir interfaces en esta etapa.

## Restricción obligatoria: respetar los módulos existentes

- No crear módulos nuevos ni una estructura paralela de planes, suscripciones o respaldos.
- Reutilizar la gestión SaaS de CU01 y el servicio de respaldos de CU25.
- Mantener las responsabilidades de router, servicio, repositorio y schemas según la estructura actual. Si hace falta un archivo auxiliar, ubicarlo dentro de la estructura existente y evitar duplicar lógica.
- No mover reportes a Administración ni respaldos a Inteligencia. Cada operación permanece en su módulo y consulta la política compartida del plan.
- Conservar los cambios locales ajenos a CU26. No subir commits, desplegar ni modificar servicios externos como parte de la implementación local.

Puntos existentes que deben revisarse y ampliarse:

| Responsabilidad | Ubicación existente |
| --- | --- |
| API SaaS de planes, empresas y suscripciones | `app/modules/administracion/router/empresa_saas_router.py` |
| Persistencia SaaS y auditoría de plataforma | `app/modules/administracion/repositories/empresa_saas_repository.py` |
| Vigencia, funciones y límites del plan | `app/core/plan_empresa.py` |
| Continuidad de operaciones pendientes | `app/core/permisos_empresa.py` |
| Identidad y alcance de empresa | `app/core/contexto_empresa.py` |
| Autenticación y rol SaaS | `app/modules/autenticacion/dependencies/` |
| Reportes | `app/modules/inteligencia/router/reporte_router.py` y sus servicios, repositorios y schemas actuales |
| Respaldos CU25 | `app/modules/administracion/router/respaldo_router.py` y `app/modules/administracion/services/respaldo_service.py` |
| Cupos de personal y sucursales | Repositorios existentes de usuarios, empleados y sucursales |
| Migraciones versionadas | `database/` y `init_db.py` |

Estas son rutas reales del backend revisado. Antes de implementar, leer sus versiones actuales; no asumir firmas ni inventar métodos existentes.

## Capacidades que SÍ se diferencian por plan

1. Cantidad de usuarios activos.
2. Cantidad de empleados activos.
3. Cantidad de sucursales activas.
4. Exportación de reportes en PDF.
5. Exportación de reportes en Excel.
6. Interpretación de consultas de reportes en lenguaje natural por texto.
7. Consultas de reportes mediante voz.
8. Programación automática de reportes y cantidad de programaciones activas.
9. Respaldos manuales y cantidad permitida en siete días.
10. Respaldos automáticos y frecuencia en días.
11. Permiso para que la empresa elija el horario del respaldo automático.
12. Retención de respaldos en días.

PDF y Excel deben tener interruptores independientes. Texto y voz también deben tener capacidades identificables; validar sus dependencias.

## Capacidades excluidas de las diferencias comerciales

No establecer diferencias entre Básico, Intermedio y Premium para venta mayorista, delivery, asistente, recomendaciones ni vestidor virtual. Sus permisos por usuario y sus requisitos operativos siguen aplicándose.

No agregar como diferenciadores productos, promociones, colecciones, transferencias de inventario, ventas por internet ni pagos en línea: el usuario redujo expresamente la selección a la lista anterior.

Actualmente existen restricciones de plan para recomendaciones, asistente y vestidor. Revisar su compatibilidad para que no contradigan esta decisión. No borrar sus funcionalidades, datos ni controles de roles. No realizar una limpieza destructiva de claves antiguas sin una migración compatible. El límite de productos existente tampoco debe eliminarse silenciosamente ni incorporarse a la nueva oferta sin acordarlo.

## Configuración inicial propuesta y aceptada

| Capacidad | BASICO | INTERMEDIO | PREMIUM |
| --- | ---: | ---: | ---: |
| Usuarios activos | 10 | 30 | 100 |
| Empleados activos | 3 | 10 | 30 |
| Sucursales activas | 1 | 3 | 10 |
| Consulta normal de reportes con filtros | Sí | Sí | Sí |
| Exportar PDF | No | Sí | Sí |
| Exportar Excel | No | Sí | Sí |
| Interpretación de consultas por texto | No | No | Sí |
| Consulta por voz | No | No | Sí |
| Programar reportes | No | Sí | Sí |
| Programaciones de reportes activas | 0 | 3 | 10 |
| Respaldos manuales habilitados | Sí | Sí | Sí |
| Respaldos manuales en siete días | 1 | 2 | 5 |
| Respaldos automáticos habilitados | Sí | Sí | Sí |
| Frecuencia automática | Cada 7 días | Cada día | Cada día |
| Hora automática inicial | 02:00 Bolivia | 02:00 Bolivia | 02:00 Bolivia |
| Empresa puede elegir hora automática | No | No | Sí |
| Retención de respaldos | 7 días | 30 días | 90 días |

Son valores iniciales editables por el administrador SaaS. No convertir los nombres de los planes en reglas permanentes: después de la inicialización, la fuente de las condiciones debe ser la configuración persistida del plan. Cambiar el nombre de un plan no debe cambiar sus capacidades.

En el backend actual, usuarios cuenta todas las cuentas activas de la empresa, incluidos clientes y personal. Un empleado con cuenta consume un cupo de usuario y otro de empleado. Conservar esa definición y devolverla como descripción del límite para la futura pantalla; no cambiar el conteo a solo personal silenciosamente.

## Funciones esenciales y dependencias

Mantener disponibles en todos los planes autenticación, recuperación de acceso, perfil, administración básica de cuentas y permisos, identificación de empresa y consulta de suscripción. Los cupos deben permitir al menos la cuenta administradora y una sucursal.

Conservar la operación básica de catálogo, inventario, ventas y comprobantes. No ofrecer un interruptor que corte una dependencia interna necesaria para registrar una venta o actualizar sus existencias.

La consulta normal de reportes se conserva en los tres planes. Se diferencian las capacidades avanzadas de la lista autorizada.

Reglas:

- Una capacidad del plan nunca sustituye el permiso del usuario: la acción requiere ambos cuando corresponda.
- Las operaciones privadas se limitan a la empresa autenticada. Solo ADMIN_SAAS puede editar planes y consultar otras empresas.
- Activar voz requiere interpretación de consultas. Habilitar un medio o sección no concede automáticamente otras capacidades.
- Programar un reporte requiere un formato permitido para su entrega; impedir configuraciones incoherentes y explicar la dependencia.
- Al vencer una suscripción o quitar una capacidad, conservar la consulta de datos y la resolución de operaciones pendientes conforme a la política actual.
- No borrar datos al reducir cupos. Bloquear nuevas altas o reactivaciones que excedan el límite; permitir reducir el uso.
- Conservar al menos una cuenta administradora operativa. No impedir el acceso básico por haber superado un cupo después de un cambio de plan.

## Administración SaaS

Ampliar las API existentes para permitir:

- Crear y editar nombre, descripción, precio de referencia, moneda y condiciones del plan. No incorporar cobros recurrentes ni otra pasarela de suscripciones dentro de este alcance.
- Publicar u ocultar un plan para nuevas contrataciones. Ocultarlo no cancela las suscripciones existentes.
- Editar individualmente cada capacidad y límite autorizado.
- Comparar planes mediante una respuesta estructurada con las mismas capacidades y unidades.
- Asignar, renovar y cambiar el plan de una empresa utilizando la estructura actual de suscripciones.
- Consultar la vigencia y el historial de suscripciones.
- Previsualizar el impacto de editar un plan antes de guardarlo: empresas afectadas, cupos que superarían y programaciones que dejarían de estar permitidas.
- Registrar el cambio confirmado y aplicarlo a las empresas que tengan asignado el plan.

Conservar la diferencia entre publicado y operativo. El comportamiento actual de `activo` influye en la vigencia; impedir que una acción presentada como ocultar desactive accidentalmente a todas las empresas suscritas.

El historial debe permitir conocer actor SaaS, fecha, valores anteriores y nuevos. La auditoría actual registra eventos, pero no debe asumirse que ya guarda ese detalle completo. Previsualización y guardado deben detectar cambios concurrentes para no confirmar un impacto desactualizado.

## Resumen de empresas por plan

Preparar las API para mostrar tarjetas y listas con:

- Número de empresas asignadas a cada plan, incluyendo cero.
- Número de empresas con suscripción vigente y no vigente, por separado.
- Listado de las empresas: identidad, estado, plan, inicio y vencimiento de suscripción.
- Filtros por plan, estado y búsqueda; paginación para las listas.
- Uso y límites de usuarios, empleados, sucursales, reportes programados y respaldos manuales.

Contar cada empresa una sola vez según su suscripción actual, siguiendo un criterio consistente con la resolución del plan existente. No contar cada fila histórica de `suscripcion` como una empresa adicional. No agrupar por el nombre visible del plan; utilizar su identidad estable.

## Reportes y programación

Una programación es una instrucción recurrente: por ejemplo, enviar cada lunes a las 08:00 un PDF con las ventas de la semana anterior.

Permitir configurar los datos que soporten los reportes existentes: tipo, filtros y sucursales autorizadas, frecuencia diaria/semanal/mensual, día aplicable, hora, zona horaria, formato y destinatario. Los períodos relativos deben recalcularse en cada ejecución.

El límite corresponde a programaciones ACTIVAS, no al número de correos enviados. Revisar el cupo tanto al crear como al reactivar, con protección frente a solicitudes concurrentes.

Revisar el ejecutor real de reportes programados: la existencia de CRUD y una ruta de ejecución manual no prueba que exista un proceso automático funcionando. Reutilizar o completar el mecanismo dentro de Inteligencia. Evitar ejecuciones duplicadas entre workers, registrar resultado e impedir envío si la capacidad o suscripción ya no lo permite.

Si se baja el límite, conservar las programaciones y pausar de forma determinista las que excedan el cupo, informando cuáles en la previsualización. Si se desactiva programación o un formato requerido, pausar las afectadas. Una mejora posterior no debe reactivar automáticamente envíos que la empresa pausó voluntariamente.

El backend actual de interpretación recibe texto. No puede demostrar si un texto llegó de un teclado o de una transcripción. La API debe exponer el permiso de voz para los clientes y controlar interpretación en el servidor, sin presentar un indicador enviado por el cliente como prueba segura del origen. La captura y ocultación del micrófono se conectarán en web y mobile posteriormente.

## Integración con respaldos CU25

- Reutilizar el servicio y las rutas existentes; no crear otro sistema de copias.
- Leer de la política persistida del plan los interruptores, cupos, frecuencia, retención y permiso de horario.
- Reemplazar los valores fijos derivados del código del plan por la política compartida, conservando una transición compatible para planes existentes.
- Manuales: ventana móvil de siete días. Eliminar una copia no devuelve el cupo ya consumido.
- Automáticos y preventivos de restauración no consumen cuota manual.
- Si se desactivan copias manuales o automáticas, mantener la consulta y la restauración de copias aún disponibles.
- Revisar el horario guardado después de una reducción de plan: una empresa sin permiso de horario editable debe volver al horario fijo aplicable, aunque antes fuera Premium.
- Cambiar retención se aplica a copias nuevas; las existentes conservan su vencimiento para evitar borrados anticipados inesperados.
- Mantener R2 privado, cifrado, validación de integridad, confirmación de restauración y aislamiento de empresa. No incluir credenciales en código, archivos de ejemplo ni respuestas API.

## Contrato de capacidades para web y mobile posteriores

Ampliar o complementar la consulta de plan existente con una respuesta normalizada de capacidades efectivas, límites, uso, unidades y razones de bloqueo. Debe estar disponible para los usuarios autenticados que necesiten construir sus menús, con el alcance de empresa correspondiente y sin revelar información de otras empresas.

La futura pantalla SaaS consumirá un catálogo de opciones con nombres comprensibles, descripciones, dependencia, tipo de control y si es esencial. No depender de que el frontend conozca listas de claves distintas a las del backend.

No aceptar claves desconocidas ni valores negativos. Distinguir cero de ausencia y definir expresamente si se permite ilimitado. Una omisión en una edición no debe producir cambios inesperados. Validar todas las reglas también en servidor.

## Migración y compatibilidad

- Revisar el estado real del repositorio antes de implementar y conservar las rutas que ya utilizan los clientes.
- Utilizar una nueva migración versionada y registrarla en `init_db.py`; no reescribir migraciones aplicadas.
- Reutilizar `plan`, `suscripcion`, sus campos JSON y la auditoría existente cuando sea adecuado. Agregar estructuras solo para necesidades que no cubra el modelo actual.
- Inicializar BASICO, INTERMEDIO y PREMIUM sin duplicar planes existentes ni sobrescribir configuraciones personalizadas o reasignar empresas automáticamente.
- Tratar explícitamente STYLEAR_LEGADO y las claves previas para que una actualización no bloquee de forma imprevista a empresas existentes.
- Los cambios de permisos deben tener efecto también en llamadas directas a las API, aunque una sesión ya estuviera abierta.

## Criterios de aceptación

1. ADMIN_SAAS puede editar todas las capacidades y cantidades autorizadas y previsualizar su impacto.
2. Ningún administrador de empresa puede editar planes ni consultar otra empresa.
3. Los tres planes tienen valores iniciales configurables y las capacidades excluidas no se convierten en diferenciadores comerciales.
4. PDF, Excel, interpretación, voz y programación se representan por separado y respetan las dependencias descritas.
5. Los cupos se controlan al crear y reactivar, incluso con solicitudes concurrentes; una reducción no borra datos.
6. Los reportes programados se ejecutan automáticamente cuando corresponde, respetan plan y vigencia y no duplican envíos entre workers.
7. CU25 usa las condiciones editadas, mantiene el aislamiento por empresa y no cobra cuota manual por automáticos o preventivos.
8. SaaS obtiene cantidades y empresas por plan sin duplicar empresas por suscripciones históricas.
9. Se conservan historial de cambios y suscripciones, consulta básica y continuidad de pendientes.
10. Las API entregan capacidades efectivas para la integración posterior de web y mobile.
11. Se realizan pruebas pertinentes de autorización, dependencias, concurrencia de cupos, cambios de plan, programación y aislamiento entre empresas; no usar servicios externos reales para enviar correos o modificar respaldos de producción en esas pruebas.
12. La entrega documenta cambios, migración, validaciones realizadas y límites pendientes. La interfaz web/mobile y el despliegue quedan fuera de esta etapa.
