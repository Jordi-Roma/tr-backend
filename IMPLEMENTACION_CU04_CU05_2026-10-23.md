# Implementación CU04 y CU05 — StyleAR

Fecha: 23 de octubre de 2026 (America/La_Paz).

Implementación local del plan autorizado expresamente por Jordi mediante «ejecuta». Backend FastAPI y web Angular; Flutter conserva sus pantallas existentes. Se mantienen los seis módulos, CU02/CU03, el motor/cámara del probador y la confirmación QR.

## 1. Resultado funcional

**CU04 — Usuarios, roles y permisos**

- AD consulta únicamente las cuentas de su empresa, con búsqueda, estados activos/inactivos/todos y paginación real. Puede crear, editar, desactivar, reactivar y administrar asignaciones según sus permisos efectivos.
- AS dispone de `/saas/usuarios`: cuentas de plataforma sin empresa o administradores de una empresa seleccionada del catálogo real. Estas cuentas no conceden acceso AS al negocio ni permiten suplantación.
- Empresa inmutable, unicidad actual de usuario/correo y bajas lógicas. Se conservan clientes, empleados, proveedores e historial comercial.
- No se permite quitar el propio acceso administrativo ni dejar una empresa/plataforma sin administrador activo. Las escrituras administrativas y plantillas se serializan mediante un bloqueo transaccional compartido; las cuotas usan además el bloqueo de empresa.
- Crear/reactivar cuentas o conceder roles comerciales exige plan vigente y, cuando corresponde, cupo. Consultar, editar datos de cuenta y revocar accesos sigue permitido con suspensión/vencimiento.
- Las altas directas admiten CLIENTE, ADMINISTRADOR y ADMIN_SAAS según el ámbito. Personal y proveedores se crean/vinculan mediante Empleados y Proveedores. Asignar CLIENTE, CAJERO, ENCARGADO_SUCURSAL o PROVEEDOR exige la entidad/vínculo comercial correspondiente.
- Roles base protegidos. Los roles adicionales heredados se conservan, con consulta y mantenimiento AS de descripción/estado; no se ofrecen altas o asignaciones nuevas de roles sin capacidades definidas.
- Sólo las nueve capacidades de la matriz siguiente son configurables en la plantilla global AD. AD consulta plantillas comerciales; AS mantiene las asociaciones permitidas con confirmación explícita de impacto global.

**CU05 — Bitácora**

- AD consulta exclusivamente su empresa en `/bitacora`; AS consulta plataforma en `/saas/bitacora`. Empresa nula no significa todas las empresas.
- Listado/detalle reales, actor, acción, módulo, resultado, fechas y paginación. Opciones de módulos/actores obtenidas de los registros del ámbito autorizado.
- Rango validado: fechas inválidas/invertidas devuelven 422. Una fecha sin hora abarca el día de Bolivia; orden estable por fecha e ID descendentes. Lista y total se calculan con los mismos filtros en una instantánea consistente.
- Los nuevos eventos identifican actor, cuenta objetivo y empresa afectada; los cambios de plantilla identifican el rol en la descripción. El éxito se inserta en la misma transacción del cambio, una sola vez. Los rechazos relevantes se registran después del rollback como BLOQUEADO.
- El detalle conserva el mismo contexto que el listado. Un fallo de carga se muestra como error; no se sustituye por un detalle inventado.
- Eventos SaaS de empresas, planes y respaldos siguen en su fuente y pantalla `/saas/eventos`. No se agregaron exportación, borrado ni edición de auditoría.

## 2. Matriz de autorización aplicada

Todas estas capacidades requieren AD activo, asociaciones usuario–rol y rol–permiso activas, rol/permiso activo y empresa propia. Se resuelven en base de datos; no se confía en permisos enviados por el navegador/JWT. Sólo AS modifica su asociación en la plantilla ADMINISTRADOR.

| Operación | Permiso editable | API comercial (prefijo `/api/v1`) |
| --- | --- | --- |
| Consultar cuentas/detalle | `usuarios:ver` | GET `/usuarios`, `/usuarios/paginados`, `/usuarios/{id}` |
| Crear cuenta | `usuarios:crear` | POST `/usuarios` |
| Editar datos de cuenta | `usuarios:editar` | PUT `/usuarios/{id}` |
| Desactivar cuenta | `usuarios:desactivar` | PATCH `/usuarios/{id}/desactivar` |
| Reactivar cuenta | `usuarios:activar` | PATCH `/usuarios/{id}/activar` |
| Consultar roles/permisos | `roles:ver` | GET `/acceso/catalogos`, `/roles`, `/permisos`, `/roles/{id}/permisos` |
| Asignar/reactivar rol | `roles:asignar` | POST `/usuarios/{id}/roles/{rol}`; PATCH `…/activar` |
| Retirar rol | `roles:retirar` | PATCH `/usuarios/{id}/roles/{rol}/desactivar` |
| Consultar bitácora/opciones/detalle | `bitacora:ver` | GET `/bitacora`, `/bitacora/opciones`, `/bitacora/{id}` |

La web requiere `usuarios:ver` para abrir Usuarios y `roles:ver` para cargar sus selectores de roles. Activar una capacidad no omite empresa, vínculos, cupo, vigencia ni continuidad administrativa.

AS usa las rutas explícitas `/saas/usuarios` y `/saas/bitacora` y las operaciones de plantillas reservadas a ADMIN_SAAS. Su autorización de plataforma es fija y no se delega mediante casillas comerciales. Las rutas comerciales de AD continúan rechazando AS.

### Inventario del catálogo protegido

Los siguientes códigos preexistentes se conservan. Sus asociaciones no se pueden cambiar desde el editor de esta entrega; la interfaz los identifica como protegidos. Esto no declara completada una conversión de todos los módulos a permisos configurables.

| Módulo del catálogo | Códigos protegidos |
| --- | --- |
| AUTENTICACION | `bitacora:exportar`; `perfil:ver`, `perfil:editar`; `roles:crear`, `roles:editar`, `roles:desactivar`, `roles:permisos:editar` |
| ADMINISTRACION | `ciudades:{ver,crear,editar,desactivar}`; `empleados:{ver,crear,editar,desactivar}`; `proveedores:{ver,crear,editar,desactivar}`; `sucursales:{ver,crear,editar,desactivar}`; `colecciones:gestionar`, `colores:gestionar`, `marcas:gestionar`, `tallas:gestionar`, `temporadas:gestionar` |
| CATALOGO | `catalogo:ver`, `detalle_prenda:ver`, `disponibilidad:ver`; `productos:{ver,crear,editar,desactivar}`, `productos:precios:gestionar`, `productos:promociones:gestionar`; `variantes:{ver,crear,editar,desactivar}`; `vestidor:usar`, `vestidor:gestionar_assets` |
| INTELIGENCIA | `chatbot:consultar`, `chatbot:gestionar`; `dashboard:ver`; `recomendaciones:usar`, `recomendaciones:gestionar`; `reportes:{ver,generar,exportar,voz}` |
| PROVEEDOR | `proveedor_panel:{ver,productos,stock,entregas}` |
| RESERVAS | `carrito:ver`, `carrito:gestionar`; `favoritos:ver`, `favoritos:gestionar`; `reservas:{ver,crear,confirmar,cancelar,entregar}` |
| VENTAS_INVENTARIO | `delivery:{solicitar,ver_propios,ver_sucursal,ver_todos,gestionar_estado,cancelar}`; `devoluciones:{solicitar,ver_propios,ver_sucursal,ver_todos,revisar,recibir,reembolsar}`; `inventario:ver`, `inventario:minimos:editar`, `inventario:movimientos:{ver,crear}`, `inventario:transferencias:{ver,crear}`; `pagos:{crear,ver,ver_propios,ver_sucursal,ver_todos}`; `venta_presencial:{ver,crear,anular}` |

La notación `prefijo:{a,b}` enumera códigos independientes. No se crean claves ficticias, roles por empresa ni permisos directos por usuario.

## 3. Sesiones, contexto y auditoría

`usuario.version_acceso` se compara al validar el token y, bajo bloqueo de usuario, al finalizar un ingreso o emitir recuperación. Los tokens anteriores sin este campo equivalen a versión cero, conservando compatibilidad hasta un cambio sensible.

Cambiar usuario/correo, desactivar/reactivar o modificar roles/capacidades invalida sesiones y códigos de recuperación afectados. Una repetición sin cambios no vuelve a revocar ni duplica el éxito. Los cambios de nombre/apellido y descripción de rol no anuncian una revocación que no ocurrió.

En Angular se consultan capacidades del servidor, se filtran menús/guardias/botones y se limpian al cerrar sesión. Las respuestas del ámbito anterior se cancelan y el listado se vacía al seleccionar otra empresa. Un 401 de una sesión anterior no cierra un ingreso nuevo; la redirección conserva la página solicitada.

Los eventos comerciales heredados sin empresa pero con actor comercial no se muestran como eventos de plataforma. No se reasignó el histórico de forma masiva. Se valida la IP proporcionada por ASGI; la aplicación no interpreta manualmente X-Forwarded-For. La confianza en proxies del servidor/despliegue debe corresponder a la infraestructura real, no a encabezados arbitrarios del cliente.

`objetivo_usuario_id` y `empresa_afectada_id` son identificadores históricos, no claves foráneas vivas. Así una restauración puede conservar la auditoría AS de cuentas que existían antes de la copia o que fueron creadas después y desaparecen al restaurarla. No habilitan consulta de información comercial del objetivo. Se verificó además que la otra empresa permanece intacta.

## 4. Contratos y migración

Se conservan las rutas y respuestas de lista/detalle de usuarios comerciales utilizadas anteriormente. El nuevo listado paginado responde `registros, total, pagina, por_pagina, total_paginas`. Filtros: `estado=ACTIVOS|INACTIVOS|TODOS`, `busqueda`, `pagina` y `por_pagina` (máximo 200).

Rutas nuevas:

- `GET /api/v1/autenticacion/capacidades` → `{permisos: string[]}`.
- `GET /api/v1/acceso/catalogos` → roles/permisos con estado, asociaciones y marcas de protección/configuración.
- `/api/v1/saas/usuarios` y detalle/edición/estado/roles equivalentes. `empresa_id` opcional en query: ausente = plataforma; presente = administradores de esa empresa. El servidor valida la empresa y las cuentas.
- `GET /api/v1/bitacora/opciones` y `/api/v1/saas/bitacora/opciones`.

Crear claves de permisos/roles libres o modificar asociaciones protegidas devuelve 409. Editar permisos AD exige `confirmar_global=true`. Cambiar estado de un rol adicional exige la misma confirmación; los PATCH heredados aceptan ese parámetro en query. Los roles base rechazan cambios de nombre/estado por todos los caminos.

Nueva migración: `database/migracion_cu04_cu05_01.sql`, versión `2026_10_23_cu04_cu05_01` registrada en `init_db.py`.

- Añade versión de acceso e identificadores históricos de auditoría.
- Añade índices de listado por empresa/estado y de bitácora por empresa/fecha/ID.
- Admite EXITOSO, FALLIDO y BLOQUEADO sin cambiar registros históricos.
- Incorpora tres claves faltantes y mantiene inicialmente las nueve capacidades legítimas de AD.
- El ledger evita aplicar la migración de nuevo y reponer permisos retirados posteriormente.
- El arranque de la API exige esta versión; no sirve tráfico sobre el esquema anterior.

Las bases existentes conservan IDs, contraseñas y relaciones. No se editan migraciones publicadas ni se crean empresas/cuentas de prueba mediante la migración.

## 5. Verificación local

| Comprobación | Resultado |
| --- | --- |
| Suite completa backend (regresiones y CU04/CU05) | 112 aprobadas |
| Comprobación final de arranque, contexto AS, permisos, roles heredados y token CU02 | 5 aprobadas; añade el caso de arranque y revalida cuatro casos |
| Pruebas unitarias Angular | 16 aprobadas |
| Recorridos Edge con API/PostgreSQL reales | 31 aprobados |
| Compilación Angular de producción | Aprobada; advertencias preexistentes CommonJS de Leaflet/qrcode |
| Pruebas Flutter existentes, sin cambios de código móvil | 20 aprobadas |
| Migración nueva, repetida y desde esquema legado | Aprobadas en PostgreSQL 16 temporal |
| Sintaxis Python y comprobación de espacios/conflictos Git | Aprobadas |

En total se verificaron 113 casos backend distintos (68 previos y 45 de CU04/CU05). La comprobación final de arranque rechazó correctamente una base sin la nueva versión, aunque conservaba la versión multitenant, y volvió a aceptar el ledger completo.

La suite nueva está en `tests/test_cu04_cu05_integration.py`. Cubre aislamiento por IDs, AS/AD, datos adicionales rechazados, duplicados/rollback, estados, último administrador concurrente, vínculos, las nueve capacidades efectivas, roles protegidos/heredados, revocación e idempotencia, ingresos/recuperación en curso, tokens CU02, fechas, orden, contexto/detalle, rechazos persistidos y restauración con auditoría AS.

Las pruebas web usan Angular + FastAPI + PostgreSQL reales, datos sintéticos y bloqueo de dominios externos. Casos nuevos en `tr-frontend/e2e/acceso.spec.ts`: altas/edición/estados, asignaciones/vínculos, plantillas, permisos globales y denegación real, bitácora/detalle/error, enlaces SaaS y respuestas atrasadas. Incluyen AXE sin reglas excluidas, foco, teclado y pantalla de 390 px. Se revisaron capturas de las pantallas.

PostgreSQL y la API usados fueron temporales; bases separadas para backend y navegador. No se utilizó SMTP ni una base real. Los códigos capturados y los archivos de fixture permanecen fuera de Git y se eliminan al terminar.

## 6. Publicación posterior y límites

**No se hizo commit, push, migración real ni despliegue.** La base local de trabajo era backend `940e70e`, frontend `325442f` y móvil `b3fe085`. Se preservaron las imágenes locales modificadas del probador y los documentos de devoluciones que ya estaban sin seguimiento.

Antes de publicar: disponer de un respaldo operativo verificado, ejecutar `python init_db.py` en el entorno autorizado, comprobar el ledger y arrancar el backend actualizado; después publicar Angular. Dockerfile/render.yaml sólo arrancan Uvicorn: no se supone que ejecuten automáticamente el migrador ni que Railway tenga configurado un pre-deploy.

Las copias selectivas comprueban las versiones de esquema: generar una copia posterior a la migración para restaurar en ese esquema. No mezclar una restauración con versiones distintas.

Flutter no necesita nuevas pantallas para estos casos. Sus pruebas locales no sustituyen una comprobación contra el backend desplegado en un teléfono real. Tampoco se comprobaron SMTP, infraestructura/proxies de Railway, proveedores externos de pago/IA ni carga de producción. El bloqueo administrativo global prioriza consistencia; no se declara una prueba de rendimiento bajo carga.

Referencias: [plan autorizado](../PLAN_CU04_CU05_STYLEAR.md), [resumen web](../tr-frontend/IMPLEMENTACION_CU04_CU05_WEB_2026-10-23.md), [antecedente CU02/CU03](IMPLEMENTACION_CU02_CU03_2026-10-23.md).
