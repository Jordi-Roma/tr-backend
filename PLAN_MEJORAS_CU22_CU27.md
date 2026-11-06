# Plan de mejoras — CU22 y CU27

## Objetivo y alcance

Mejorar los casos existentes de StyleAR:
- CU22: Gestionar reportes y dashboards.
- CU27: Gestionar notificaciones del cliente.

CU22 y CU23 se consideran existentes. Este trabajo amplía CU22 y completa la experiencia de CU27; no debe reconstruir sus funciones ya disponibles ni modificar CU23.

Este archivo es una especificación pendiente de ejecución. Crearlo no autoriza despliegues ni acredita que las mejoras estén implementadas.

Mantener el orden solicitado: primero backend; después integración web y mobile. La notificación emergente del APK requiere Flutter/Android y validación en un teléfono, por lo que CU27 no puede darse por terminado de punta a punta únicamente con cambios del servidor.

## Estructura obligatoria

- Respetar los módulos y capas actuales. No crear módulos nuevos, proveedores externos alternativos ni sistemas paralelos de reportes o notificaciones.
- Ampliar routers, servicios, repositorios y schemas existentes. Los archivos auxiliares necesarios deben ubicarse dentro de esos módulos.
- CU22 permanece en Inteligencia. CU27 reutiliza la implementación de notificaciones en Ventas e Inventario y las llamadas de los módulos que generan los eventos.
- Reutilizar Firebase, la bandeja, la cola push y el transporte de correo existentes.
- Conservar las políticas de CU26, autenticación, permisos de usuario y aislamiento por empresa y sucursal.
- No modificar archivos ajenos al alcance ni subir credenciales al repositorio.
- Agregar migraciones versionadas nuevas en database y registrarlas en init_db.py. No editar las migraciones ya desplegadas.
- Leer el código actual antes de implementar; las rutas indicadas son puntos de partida reales, no métodos nuevos que deban inventarse con esos nombres.

| Área | Ubicación existente |
| --- | --- |
| API de reportes | tr-backend/app/modules/inteligencia/router/reporte_router.py |
| Servicio de reportes | tr-backend/app/modules/inteligencia/services/reporte_service.py |
| Consultas de reportes | tr-backend/app/modules/inteligencia/repositories/reporte_repository.py |
| Schemas de reportes | tr-backend/app/modules/inteligencia/schemas/reportes/reporte_request.py |
| Calendario de reportes | tr-backend/app/modules/inteligencia/services/programacion_reporte.py |
| Límites y funciones del plan | tr-backend/app/core/plan_empresa.py |
| Bandeja y dispositivos | tr-backend/app/modules/ventas_inventario/services/notificaciones_service.py |
| Rutas de notificaciones | tr-backend/app/modules/ventas_inventario/router/pagos_empresa_router.py |
| Ejecutor FCM | tr-backend/app/modules/ventas_inventario/services/push_worker.py |
| Reportes web | tr-frontend/src/app/modules/inteligencia/ |
| Servicio Firebase móvil | tr-mobile/lib/services/firebase_push_service.dart |
| Bandeja móvil | tr-mobile/lib/screens/notificaciones/notificaciones_screen.dart |
| Servicio de notificaciones móvil | tr-mobile/lib/services/notificaciones_service.dart |
| Reportes móviles | tr-mobile/lib/screens/reportes/reportes_admin_screen.dart |
| Configuración Android | tr-mobile/android/app/src/main/AndroidManifest.xml |
| Dependencias Flutter | tr-mobile/pubspec.yaml |

Consultar AGENTS.md de cada repositorio antes de modificarlo. Las rutas de frontend/mobile se incluyen para la fase posterior; no adelantar cambios de interfaces mientras se trabaje exclusivamente en backend.

## CU22 — Estado que se debe aprovechar

El backend ya tiene reportes por tipo y filtros, exportación PDF/Excel, interpretación de consultas, programación recurrente, envío por correo e historial de ejecuciones. CU26 ya agregó las capacidades del plan.

No presentar estas funciones como trabajo nuevo ni duplicar su ejecutor. Las mejoras son las siguientes.

### 1. Dashboard resumido

Agregar una respuesta de resumen para alimentar tarjetas y gráficos con un mismo conjunto de filtros y alcance:
- Ventas presenciales y digitales, identificadas por separado y consolidadas sin duplicarlas.
- Importes vendidos y dinero efectivamente cobrado, con definiciones distintas.
- Reembolsos confirmados y saldo neto del período bajo una regla documentada.
- Reservas pendientes y vencidas.
- Productos más vendidos.
- Existencias bajas por sucursal.

Reutilizar las consultas y reglas comerciales reales. No estimar márgenes ni ganancias si no existen costos fiables. No identificar órdenes pendientes o reservas con dinero ya cobrado. Las tarjetas, gráficos y detalle deben usar las mismas definiciones.

Conservar la consulta básica de reportes y dashboard en todos los planes. No agregar nuevos diferenciadores comerciales fuera de lo acordado en CU26.

### 2. Comparación de períodos

Permitir comparar un rango con el período anterior de igual duración. Devolver para cada indicador:
- Valor actual y anterior.
- Diferencia absoluta.
- Variación porcentual cuando tenga sentido.
- Fechas y alcance de ambos períodos.

Si el anterior es cero, devolver una variación porcentual no calculable con una explicación; no devolver infinito ni inventar un porcentaje. No tratar la ausencia de registros como fallo del servicio.

### 3. Acceso del encargado de sucursal

Actualmente las rutas de reportes requieren administrador. Ampliar la consulta según los actores de CU22:
- Administrador: datos de su empresa y filtros de sus sucursales.
- Encargado: únicamente la sucursal que tiene asignada y autorizada.
- Otros roles: conservar sus restricciones; no conceder acceso general a reportes.
- SaaS: no obtiene acceso comercial global mediante estas rutas.

Aplicar el alcance en dashboard, catálogo de filtros, generación, detalle, comparación y exportación. Si el encargado omite sucursal, usar la suya; si solicita otra, rechazar. No confiar en la sucursal enviada por el cliente.

Los tipos de reporte que no puedan limitarse correctamente a una sucursal, especialmente datos generales de usuarios, deben quedar reservados al administrador. Reutilizar los controles de asignación existentes.

La gestión de programaciones se mantiene a cargo del administrador. Los permisos de PDF, Excel, interpretación y voz continúan sujetos al plan además del rol.

### 4. Métricas comerciales coherentes

Revisar las consultas existentes antes de consolidar indicadores:
- Definir cómo se reconocen ventas completadas, anuladas, pagos y reembolsos.
- Distinguir fecha de venta, fecha de pago y fecha de reembolso.
- Evitar descontar dos veces un reembolso o contar una venta por cada uno de sus pagos.
- Mantener importes decimales y moneda explícita.
- Conservar filtros por sucursal, fechas, tipo de venta y estado cuando sean aplicables.
- Señalar que el inventario es una fotografía actual si no existe un historial que permita reconstruir su estado pasado.

La política de neto debe explicar si usa flujos de cobro del período o ventas del período ajustadas; no mezclar ambos criterios bajo una misma etiqueta.

### 5. Editar programaciones existentes

Agregar edición de título, tipo, filtros, sucursal, período relativo, frecuencia, día, hora, zona horaria, formato y destinatario.

Reutilizar la validación y el calendario actuales:
- Verificar empresa, rol, plan y formato.
- Comprobar cupo al activar una programación que estaba pausada.
- Recalcular la próxima ejecución.
- Conservar su historial.
- Evitar que una modificación y un envío simultáneos produzcan configuraciones mezcladas.
- No reactivar automáticamente una programación pausada voluntariamente.
- Conservar el control de ocurrencias ya intentadas; no reenviar una entrega incierta de manera automática.

Si se baja el plan, mantener el comportamiento de CU26 para pausar excesos o formatos retirados.

### 6. Reportes con más resultados

Actualmente se rechazan los reportes que alcanzan 5.000 filas. Preparar consulta paginada del detalle:
- Orden estable y paginación validada.
- Totales y gráficos calculados sobre todo el resultado filtrado, no sobre la página visible.
- Total de registros explícito.
- Límites de rango y ejecución razonables para proteger el servicio.
- Exportación con procesamiento controlado o un límite explícito y explicado; nunca truncar archivos silenciosamente.

Mantener compatibilidad con las rutas y respuestas ya consumidas por las aplicaciones, o versionar/documentar cualquier cambio necesario.

## CU27 — Estado que se debe aprovechar

Ya existen:
- Bandeja por usuario y empresa.
- Marcado individual como leído.
- Registro y desvinculación de instalaciones.
- Eventos de compras, pagos, entregas y devoluciones.
- Cola de salida FCM, reintentos y retirada de tokens inválidos.

El servicio Flutter escucha mensajes, pero en primer plano actualmente incrementa un contador; eso por sí solo no muestra la notificación emergente solicitada.

### 1. Bandeja organizada

Ampliar la consulta con:
- Paginación estable, sin limitar la experiencia a los últimos 100 avisos.
- Filtros de leídas/no leídas y categoría.
- Contador de avisos no leídos independiente de la página.
- Fecha, título, mensaje y operación relacionada.
- Marcado individual y marcado de todas como leídas.

Marcar como leído debe ser idempotente y afectar solo al usuario autenticado en su empresa. La consulta y el marcado de avisos deben mantenerse disponibles para consultar operaciones pendientes.

No se añade una restricción comercial de notificaciones por plan.

### 2. Eventos comerciales

Completar, reutilizando transacciones y reglas actuales:
- Compra confirmada y pago rechazado.
- Reserva confirmada, cancelada y vencida.
- Avance de una entrega.
- Avance o resolución de un cambio de prendas.
- Avance de una devolución y reembolso confirmado.

Emitir el aviso solo cuando se confirme la transición correspondiente. Una transacción revertida no debe dejar una notificación de éxito.

Utilizar claves de evento estables para que un webhook repetido o un reintento no cree avisos duplicados. Distinguir eventos diferentes de una misma operación.

Ampliar el servicio existente para eventos que no dependen de una orden de pago; no forzar reservas o cambios a simular una compra para producir avisos.

### 3. Abrir la operación correspondiente

Cada aviso debe identificar de forma estructurada:
- Categoría.
- Tipo de recurso.
- Identificador del recurso.
- Acción de navegación permitida.

Usar una lista de destinos admitidos; no ejecutar enlaces arbitrarios proporcionados por un mensaje. Al tocar el aviso, la aplicación debe consultar el recurso con la sesión actual. El identificador recibido no concede autorización.

Si el recurso ya no existe, no es accesible, la empresa no coincide o cambió la cuenta, mostrar la bandeja o un mensaje comprensible sin exponer datos.

### 4. Preferencias del cliente

Permitir elegir qué categorías generan alertas push. Los avisos transaccionales importantes siguen guardándose en la bandeja aunque el cliente silencie el push.

Guardar las preferencias por usuario y empresa. La preferencia de la app no sustituye el permiso de Android ni puede volver a habilitar un canal que el usuario bloqueó en el sistema.

No incluir campañas publicitarias, correos masivos ni un proveedor adicional en este alcance.

### 5. Envío y trazabilidad

Reutilizar push_worker.py:
- Incorporar espera progresiva entre reintentos y próximo intento persistido.
- Conservar límite de intentos y tratamiento de tokens retirados.
- Evitar que dos trabajadores procesen simultáneamente la misma salida.
- Revalidar instalación, usuario, empresa, sesión, versión de acceso y preferencias antes de enviar.
- Mantener la cola si falta configuración o falla el proveedor.
- No almacenar tokens, credenciales ni respuestas sensibles en logs.
- No registrar como entregado en el teléfono algo que solamente aceptó FCM.

Distinguir notificación persistida, salida pendiente, aceptación por Firebase, fallo/omisión y lectura. La confirmación de lectura de la bandeja no debe confundirse con la aceptación del proveedor.

Documentar cómo mantener el trabajador ejecutándose continuamente en Railway. Su comando existente es:
`python -m app.modules.ventas_inventario.services.push_worker --continuo`

Comprobar la configuración del despliegue antes de decidir si se integra con el proceso existente o con un proceso trabajador. No crear un servicio externo ni desplegar sin la autorización correspondiente.

## CU27 — Requisito principal: notificación emergente en el APK

El usuario pide la notificación de Android que aparece como un recuadro en la parte superior de la pantalla: heads-up. No basta con actualizar un contador o mostrar un mensaje dentro de la bandeja.

### Comportamiento esperado

| Estado de la aplicación | Comportamiento |
| --- | --- |
| Abierta y en primer plano | Mostrar una notificación Android local al recibir el push, además de actualizar la bandeja. |
| En segundo plano | Android presenta el aviso recibido mediante FCM. |
| Proceso terminado normalmente | Gestionar la recepción según las condiciones del sistema y resolver la apertura desde el aviso. |
| Pantalla bloqueada | Respetar los permisos, configuración del canal y privacidad del dispositivo. |
| Al tocar el aviso | Abrir la operación autorizada o solicitar iniciar sesión antes de consultarla. |
| Sin permiso o con canal deshabilitado | Mantener la bandeja y permitir al usuario revisar la configuración de avisos. |
| Cierre forzado desde ajustes de Android | No prometer recepción hasta que el usuario vuelva a abrir la aplicación. |

La entrega y presentación no se pueden garantizar en todos los dispositivos o estados. El criterio es una implementación correcta y probada con permisos concedidos y canal habilitado, no una promesa de aparición absoluta.

### Backend

Preparar el mensaje FCM Android para avisos transaccionales visibles:
- Prioridad de transporte apropiada para avisos urgentes y visibles.
- Identificador del canal Android consistente con el canal creado por la aplicación.
- Título y texto adecuados, sin información sensible innecesaria en la pantalla bloqueada.
- Identificador de notificación y empresa en los datos.
- Caducidad y política de agrupación que no oculten eventos importantes por reutilizar indiscriminadamente una misma clave.

La prioridad de transporte de FCM y la importancia del canal Android son configuraciones distintas; deben coordinarse.

### Flutter y Android — fase posterior necesaria

Ampliar firebase_push_service.dart y las clases actuales de notificaciones:
1. Revisar la inicialización de Firebase, los datos públicos de compilación y el manejo de mensajes en segundo plano.
2. Comprobar el permiso POST_NOTIFICATIONS en el manifiesto combinado y solicitarlo cuando corresponda, especialmente en Android 13 o posterior.
3. Crear un canal de notificaciones con importancia alta para los avisos transaccionales que deban aparecer de forma emergente.
4. Resolver la presentación local en primer plano mediante una integración compatible con el proyecto. Actualmente no se encontró flutter_local_notifications en pubspec.yaml; revisar dependencias antes de elegir o agregar una.
5. Usar el mismo canal en el mensaje FCM, la configuración por defecto y las notificaciones locales.
6. Evitar duplicados: en segundo plano no publicar una segunda notificación local si Android ya presenta el mensaje de tipo notification.
7. Resolver aperturas mediante onMessageOpenedApp, getInitialMessage y el callback de la notificación local, según el estado de la app.
8. Deduplicar por identificador y contexto de cuenta, sin suprimir eventos comerciales distintos.
9. Conservar la renovación del token y la desvinculación segura al cerrar sesión o cambiar de usuario/empresa.
10. Respetar las decisiones del usuario sobre importancia, sonido y visibilidad del canal. No intentar elevarlas silenciosamente después de que las cambie.

No activar un servicio permanente en primer plano, alarmas de pantalla completa ni técnicas para eludir las restricciones de Android para simular una garantía de entrega.

### Pruebas del APK

Validar con una compilación de distribución y un teléfono Android físico:
- Primer plano: recuadro emergente visible.
- Segundo plano: aviso visible y apertura de la operación.
- Inicio desde la notificación con el proceso terminado normalmente.
- Pantalla bloqueada y privacidad del contenido.
- Aviso único ante un evento duplicado.
- Preferencia push silenciada: sin alerta push, aviso conservado en bandeja.
- Permiso denegado o canal deshabilitado: bandeja operativa y estado explicado.
- Renovación de token.
- Cierre de sesión y cambio de cuenta/empresa sin mostrar datos del usuario anterior.
- Reanudación después de volver a abrir la app tras un cierre forzado.

Registrar dispositivo, versión Android, permisos, estado del canal y estado de la app. Separar la evidencia de recepción visible de la mera aceptación por Firebase. No marcar como aprobados escenarios que no se hayan probado.

## Integración y compatibilidad

- Mantener el acceso y las capacidades de CU26 para reportes.
- Conservar la operación de consultas básicas y atención de pendientes cuando una suscripción vence.
- Nuevas tablas o columnas deben tener alcance de empresa y relaciones coherentes con el modelo actual.
- Revisar la compatibilidad con CU25: restaurar datos no debe reenviar avisos antiguos ni reactivar salidas push ya procesadas. Mantener invalidación de sesiones/dispositivos conforme a la restauración.
- No sobrescribir preferencias o decisiones de notificación del usuario durante una actualización.
- Conservar las rutas públicas existentes o proporcionar una transición compatible.
- No modificar las diferencias comerciales de planes ya acordadas.

## Orden de implementación

1. Backend CU22: métricas, alcance por sucursal, dashboard y comparación.
2. Backend CU22: edición de programaciones y consulta paginada.
3. Backend CU27: bandeja, categorías, lecturas y preferencias.
4. Backend CU27: eventos, navegación estructurada, cola y contrato FCM.
5. Validaciones e integración de backend con servicios externos simulados.
6. En una etapa posterior solicitada: web y Flutter, incluyendo la notificación heads-up del APK.
7. Validación real del transporte y la presentación en Android; documentar evidencias.

## Criterios de aceptación

### CU22

- El administrador consulta su empresa y el encargado solo su sucursal en todas las variantes del reporte.
- Dashboard, gráficos, comparación, detalle y exportaciones mantienen cifras coherentes.
- No se mezclan ventas, cobros pendientes y reembolsos ni se inventan datos históricos de inventario.
- Los porcentajes con base cero se manejan explícitamente.
- Se editan programaciones sin perder historial ni exceder cuotas o capacidades del plan.
- Un detalle paginado no altera los totales generales.
- Las aplicaciones existentes mantienen un contrato compatible.

### CU27

- El usuario consulta sus propios avisos con filtros, contador y paginación.
- Las lecturas individuales y masivas son idempotentes y respetan empresa y usuario.
- Cada transición comercial produce su aviso una sola vez después de confirmarse.
- Las preferencias afectan el push sin borrar los avisos importantes de la bandeja.
- La cola respeta sesiones, tokens, preferencias y reintentos espaciados.
- Tocar un aviso nunca permite acceder a operaciones de otra empresa o usuario.
- La aplicación puede presentar el aviso emergente en primer plano y segundo plano bajo condiciones admitidas por Android.
- La aceptación por Firebase no se presenta como prueba de visualización en el teléfono.
- No se declara completo el requisito del APK sin pruebas reales de la fase Flutter.

## Verificación y entrega

Agregar pruebas útiles de autorización, aislamiento, métricas, paginación, cuotas, concurrencia, reintentos, duplicados y navegación. Usar PostgreSQL local desechable para integraciones y simular FCM/correo en las pruebas automatizadas.

La prueba real de Android y las comunicaciones externas requieren su etapa explícita. No enviar avisos a clientes reales para verificar el desarrollo.

Entregar cambios, migraciones, contrato de API y resultados de pruebas con sus límites. No incluir claves privadas ni tokens en capturas, documentación o commits.

## Referencias oficiales para la fase Android

- Firebase: [Recepción de mensajes en Flutter](https://firebase.google.com/docs/cloud-messaging/flutter/receive-messages). Sustenta la separación entre primer plano, segundo plano y apertura de mensajes.
- Android: [Notificaciones y presentación heads-up](https://developer.android.com/develop/ui/compose/notifications). Explica la presentación emergente y su relación con la importancia del canal.
- Android: [Diseño de notificaciones y niveles de importancia](https://developer.android.com/design/ui/mobile/guides/home-screen/notifications). Explica el comportamiento visible y el control del usuario.

Verificar la documentación oficial y las versiones instaladas al implementar. Las referencias no sustituyen las pruebas con el APK real.
