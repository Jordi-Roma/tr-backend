# Implementación de gestión de devoluciones

**Fecha:** 24 de septiembre de 2026  
**Proyecto:** TiendaAR  
**Alcance:** backend, frontend web, aplicación mobile y migración de base de datos.

## Resumen

Se implementó el flujo de devoluciones para que un cliente pueda solicitar la devolución total o parcial de productos de una compra, consultar su estado y cancelar una solicitud aún no revisada. El personal autorizado puede revisar la solicitud, registrar la recepción e inspección de los productos y procesar o registrar el reembolso.

La funcionalidad quedó integrada en las estructuras existentes de `ventas_inventario` del backend y frontend, y en las pantallas existentes de perfil/pagos de mobile. **No se creó un módulo nuevo.**

## Backend

La API quedó registrada bajo el prefijo `/api/v1/devoluciones` y exige usuario autenticado. Incluye operaciones para:

- Consultar ventas elegibles para devolución.
- Crear solicitudes asociadas a una venta y sus líneas de detalle.
- Consultar devoluciones propias, consultar su detalle y cancelar una solicitud propia.
- Listar y consultar devoluciones para el personal según sus permisos.
- Revisar una solicitud, aprobarla o rechazarla.
- Registrar recepción e inspección de los artículos.
- Procesar reembolsos mediante Stripe o registrar manualmente un reembolso de otro método de pago.

Los archivos principales agregados o modificados son:

- `app/modules/ventas_inventario/router/devolucion_router.py`
- `app/modules/ventas_inventario/services/devolucion_service.py`
- `app/modules/ventas_inventario/repositories/devolucion_repository.py`
- `app/modules/ventas_inventario/schemas/devolucion/`
- `app/modules/ventas_inventario/services/pago_service.py`
- `app/modules/ventas_inventario/repositories/inventario_repository.py`
- Registro del router en `app/main.py` y de la migración en `init_db.py`.

### Reglas y controles

- El plazo predeterminado para solicitar una devolución es de **30 días** y puede configurarse con `DEVOLUCION_PLAZO_DIAS`.
- Solo se permiten solicitudes sobre compras elegibles que estén completadas y pagadas.
- Se admiten devoluciones parciales por producto/cantidad; el backend controla las cantidades ya solicitadas o devueltas para evitar exceder lo comprado.
- Las operaciones de solicitud y actualización coordinan el uso de la venta y sus detalles dentro de transacciones para reducir conflictos entre solicitudes simultáneas.
- La devolución recibida puede generar el movimiento de inventario `DEVOLUCION_VENTA`; la recepción y actualización correspondiente se registran en la misma operación transaccional.
- El monto aprobado se calcula a partir de los productos aceptados y del importe pagado aplicable; el costo de delivery no se devuelve como producto.
- Las solicitudes tienen una clave de idempotencia. Los reembolsos Stripe actualizan el estado mediante los eventos del proveedor; un reembolso no se marca como completado hasta recibir la confirmación correspondiente.
- Los pagos que no se procesan por Stripe pueden documentarse mediante un reembolso manual con referencia y método.
- Se guardan responsables y fechas de solicitud, revisión, recepción, cancelación y reembolso para mantener trazabilidad.

### Estados contemplados

`SOLICITADA`, `EN_REVISION`, `APROBADA`, `RECHAZADA`, `REEMBOLSO_PENDIENTE`, `ERROR_REEMBOLSO`, `REEMBOLSADA` y `CANCELADA`.

El cliente puede cancelar su solicitud mientras siga en estado `SOLICITADA`. Una solicitud aprobada puede continuar a recepción y reembolso; los fallos de Stripe quedan identificados como `ERROR_REEMBOLSO` para su seguimiento.

### Permisos

- **CLIENTE:** solicitar devoluciones propias y consultar su historial/estado.
- **ADMINISTRADOR:** ver todas las devoluciones, revisarlas, recibir artículos y procesar reembolsos.
- **ENCARGADO_SUCURSAL:** gestionar las devoluciones de su ámbito de sucursal, incluyendo revisión, recepción y reembolso.
- **CAJERO:** consultar las devoluciones de su sucursal y registrar la recepción; no tiene permiso para procesar reembolsos.

## Base de datos y migración

Se agregó `database/migracion_devoluciones.sql`. La migración crea las tablas `devolucion` y `devolucion_detalle`, sus restricciones e índices, agrega `DEVOLUCION_VENTA` como tipo válido de movimiento de inventario y registra permisos/asignaciones de roles.

La migración se registró en `init_db.py` para ejecutarse durante la inicialización configurada en Railway. En los logs del despliegue del 24 de septiembre aparece `OK: database/migracion_devoluciones.sql`, seguido de `Base de datos configurada correctamente`; el backend luego informó que las migraciones fueron verificadas y completó el inicio.

## Frontend web

Se agregó la gestión dentro del módulo existente `ventas_inventario`:

- Modelos y servicio para consumir la API.
- Pantalla de devoluciones en el área existente de historial de pagos.
- Rutas para que el cliente consulte/solicite devoluciones y para que el personal gestione las solicitudes.
- Accesos en el menú principal de acuerdo con el rol.
- Formularios y vistas para selección de compra, artículos/cantidades, motivo, seguimiento del estado, cancelación, revisión, recepción e indicación del reembolso.

Archivos principales: `src/app/modules/ventas_inventario/models/devolucion.models.ts`, `services/devolucion.service.ts`, `pages/historial-pagos/devoluciones.page.*`, `ventas-inventario.routes.ts` y `src/app/layouts/main-layout/main-layout.ts`.

## Aplicación mobile

Se integró el flujo para clientes en la pantalla de perfil/pagos existente:

- Modelos y servicio mobile para ventas elegibles y devoluciones.
- Acceso a devoluciones desde el perfil del cliente.
- Solicitud con selección de compra, artículos/cantidades y motivo.
- Consulta de solicitudes, detalle/estado y cancelación cuando todavía está solicitada.
- Configuración del endpoint en `ApiConstants`.

Archivos principales: `lib/models/devolucion_models.dart`, `lib/services/devolucion_service.dart`, `lib/screens/pagos/devoluciones_screen.dart`, `lib/screens/perfil/perfil_screen.dart` y `lib/core/constants/api_constants.dart`.

## Verificación realizada

- **Backend:** se verificó compilación sintáctica de los archivos nuevos/modificados e importación de la aplicación.
- **Frontend:** `npm run build` terminó correctamente. Se observaron advertencias existentes de dependencias CommonJS (`leaflet` y `qrcode`), no errores que impidieran el build.
- **Mobile:** el usuario ejecutó `flutter analyze`; resultado: `No issues found!`.
- **Railway:** el deploy del backend fue exitoso y los logs confirmaron la ejecución de `migracion_devoluciones.sql` sin error.

## Commits publicados

Los tres repositorios recibieron estos commits en `main` el 24 de septiembre de 2026:

| Repositorio | Commit | Mensaje |
|---|---|---|
| Backend | `db21b71` | `Implementar gestion de devoluciones` |
| Frontend | `9c43ed3` | `Agregar gestion de devoluciones web` |
| Mobile | `7548a55` | `Agregar gestion de devoluciones mobile` |

El documento de planificación `PLAN_DEVOLUCIONES.md` permaneció fuera del commit del backend; no forma parte de la funcionalidad desplegada.

## Resultado

La gestión de devoluciones quedó implementada en backend, web y mobile; la migración fue confirmada en Railway y las verificaciones registradas arriba finalizaron correctamente. La implementación respeta los módulos existentes del proyecto.
