# Plan de devoluciones

## Objetivo

Permitir que un cliente solicite la devolución total o parcial de una compra, que personal autorizado la revise, que el reembolso quede registrado y que el inventario se reponga solamente cuando la prenda devuelta haya sido recibida e inspeccionada.

La implementación debe reutilizar el módulo existente `ventas_inventario` en backend y frontend. No se debe crear un séptimo módulo ni cambiar la organización actual de los seis módulos.

## Estado actual verificado

- Las ventas se guardan en `venta` y sus prendas en `venta_detalle`. La tabla admite actualmente `COMPLETADA` y `ANULADA` en la migración base; las migraciones posteriores también incluyen estados de pago y cancelación.
- Una venta presencial descuenta el inventario y registra un movimiento `VENTA_PRESENCIAL`.
- Una compra digital crea una orden en `orden_pago`; cuando Stripe confirma el pago, se registra `VENTA_DIGITAL` y la venta cambia a `COMPLETADA`.
- `orden_pago` registra el identificador del PaymentIntent de Stripe, pero no tiene campos ni estados de reembolso.
- Existe el permiso `venta_presencial:anular`, pero no se encontró una ruta o servicio que lo implemente. Anular una venta no cubre el flujo de devolución de una compra completada.
- No se encontraron tablas, endpoints ni pantallas de devoluciones en backend, web o mobile.
- `init_db.py` mantiene la lista de migraciones SQL. La rutina de inicio de `app/main.py` comprueba algunas columnas de producto; no es un ejecutor general de migraciones.

## Alcance funcional propuesto

1. Un cliente autenticado consulta sus compras y solicita la devolución de una venta completada, de todos los artículos o de cantidades parciales.
2. El cliente indica el motivo y las unidades que desea devolver; puede adjuntar una observación o evidencia si se decide habilitar carga de archivos.
3. Personal autorizado de la sucursal revisa la solicitud, la aprueba o rechaza y deja una nota auditable.
4. Al recibir e inspeccionar los artículos, el personal registra cuántas unidades fueron aceptadas para devolución.
5. El sistema calcula el importe reembolsable a partir del precio realmente cobrado, incluyendo descuentos y redondeo monetario.
6. Para pagos Stripe, el sistema solicita el reembolso al proveedor y guarda el identificador y resultado de Stripe. Para efectivo, QR u otro método sin integración de reembolso, el personal registra el reembolso manual y su referencia.
7. El inventario aumenta únicamente por las unidades físicamente recibidas y aceptadas. Cada entrada queda vinculada a la devolución y a la venta original.
8. Cliente y personal consultan el estado, los artículos, las cantidades y el importe reembolsado. Los registros no se borran físicamente.

## Estados y transiciones

Estados sugeridos para la solicitud:

| Estado | Significado |
| --- | --- |
| `SOLICITADA` | El cliente envió la solicitud. |
| `EN_REVISION` | La tienda está evaluando la solicitud o el producto recibido. |
| `RECHAZADA` | La tienda rechazó la solicitud y registró el motivo. |
| `APROBADA` | La devolución fue autorizada; falta recibir o verificar el producto. |
| `REEMBOLSO_PENDIENTE` | Se inició el reembolso y falta confirmación del proveedor o registro manual. |
| `REEMBOLSADA` | El reembolso quedó confirmado o registrado. |
| `CANCELADA` | El cliente canceló antes de que la devolución fuera procesada. |

No permitir transiciones arbitrarias ni reembolsar dos veces. Repetir una petición por timeout debe devolver el resultado ya registrado o continuar la misma operación, no iniciar un segundo reembolso.

## Modelo de datos propuesto

Crear las tablas en una migración SQL incremental. Los nombres pueden ajustarse a las convenciones finales del repositorio.

### `devolucion`

- Identificador y código legible.
- `venta_id`, cliente solicitante, sucursal, usuario que revisó y usuario que recibió el producto.
- Estado, motivo, notas de revisión y fechas de solicitud, decisión, recepción y cierre.
- Importe solicitado, importe aprobado y moneda.
- Método de reembolso; referencia al pago original y al reembolso del proveedor cuando corresponda.
- Referencia de reembolso manual para pagos en efectivo, QR u otros métodos no integrados.
- Indicador activo o mecanismo equivalente de baja lógica, sin borrado histórico.

### `devolucion_detalle`

- Referencia a `venta_detalle.id` para preservar el precio y variante originales.
- Cantidad solicitada, cantidad aceptada y cantidad rechazada, con restricciones para que sean positivas y no excedan lo vendido.
- Importe correspondiente a las unidades aprobadas y observación del estado físico.

Los artículos se deben relacionar con la línea concreta de venta, no solo con el producto o la variante. Así se conserva la evidencia de precio y descuento original.

## Reglas de negocio e integridad

- Solo aceptar solicitudes para ventas `COMPLETADA`. Una venta pendiente, anulada, cancelada o con pago rechazado no puede generar un reembolso.
- En una compra digital, exigir una orden de pago en estado `PAGADO`. Para una venta presencial, conservar el método de pago registrado en `venta.metodo_pago` y dejar claro que el reembolso podría ser manual.
- Una venta puede tener varias devoluciones parciales, pero la suma de unidades ya aprobadas o devueltas y las solicitudes abiertas no puede exceder las cantidades vendidas.
- Al crear o decidir una solicitud, bloquear las líneas de venta involucradas en una transacción (`SELECT ... FOR UPDATE`) y validar las cantidades acumuladas para evitar que dos solicitudes simultáneas devuelvan la misma unidad.
- La cantidad que vuelve al stock nunca debe superar las unidades recibidas y aceptadas. Registrar una entrada de inventario por sucursal y variante, enlazada a `devolucion` y a `venta`.
- Añadir un tipo auditable de movimiento positivo, por ejemplo `DEVOLUCION_VENTA`, actualizando la restricción de tipos del movimiento mediante la migración.
- El importe parcial debe prorratear el subtotal neto de la línea vendida (después del descuento), con redondeo decimal a dos cifras. Rechazar importes mayores que lo originalmente cobrado menos reembolsos previos.
- No incluir automáticamente el costo del delivery en el reembolso. Su tratamiento requiere una política explícita.
- Para Stripe, usar el PaymentIntent guardado en `orden_pago`, una clave de idempotencia estable y confirmar el resultado antes de marcar `REEMBOLSADA`. No declarar un reembolso exitoso solo porque se envió la petición.
- Si Stripe falla o el resultado queda incierto, mantener un estado pendiente de conciliación, guardar el error técnico para auditoría y permitir reintentar sin duplicar el reembolso.
- En efectivo/QR sin integración, exigir que un usuario autorizado registre el monto, método, fecha y referencia/comprobante del reembolso manual.
- Guardar quién hizo cada acción y cuándo. No modificar ni eliminar los movimientos de venta originales.

## Roles y permisos

Añadir permisos específicos en el área `VENTAS_INVENTARIO`, por ejemplo:

- `devoluciones:solicitar` y `devoluciones:ver_propias` para clientes.
- `devoluciones:ver_sucursal`, `devoluciones:revisar` y `devoluciones:registrar_reembolso` para personal autorizado de sucursal.
- `devoluciones:ver_todos` y `devoluciones:gestionar` para administración.

El backend debe validar permisos y sucursal en cada operación. Ocultar botones en la interfaz no reemplaza la autorización del servidor. La asignación exacta de permisos a administrador, encargado y cajero se debe confirmar antes de implementar; recomendación inicial: administrador y encargado aprueban/rechazan, personal autorizado registra recepción, y el cajero solo consulta o registra un reembolso manual si se le concede expresamente.

## API propuesta dentro de `ventas_inventario`

Prefijo: `/api/v1/devoluciones`.

- `POST /ventas/{venta_id}`: crear solicitud del cliente autenticado.
- `GET /mis-devoluciones`: listar solicitudes propias.
- `GET /mis-devoluciones/{devolucion_id}`: consultar detalle propio.
- `GET /`: listar solicitudes para administración o sucursal con filtros por estado, fechas, venta, cliente y sucursal.
- `GET /{devolucion_id}`: obtener detalle autorizado.
- `PATCH /{devolucion_id}/revision`: aprobar o rechazar y guardar motivo.
- `PATCH /{devolucion_id}/recepcion`: registrar cantidades recibidas y aceptadas; generar entradas de inventario en la misma transacción.
- `POST /{devolucion_id}/reembolso`: iniciar reembolso Stripe o registrar reembolso manual, según el método original.

Las rutas deben usar los esquemas existentes de permisos y sucursal. No agregar un router bajo un nuevo módulo; registrar el router de devoluciones en el router existente de `ventas_inventario`/`app/main.py` siguiendo el patrón actual.

## Cambios previstos por repositorio

### Backend — módulo existente `app/modules/ventas_inventario`

- Añadir router, servicio, repositorio y esquemas de devoluciones dentro de las carpetas ya existentes `router`, `services`, `repositories` y `schemas`.
- Reutilizar `_aplicar_movimiento` para actualizar inventario dentro de la transacción, extendiendo el tipo de movimiento permitido mediante migración.
- Añadir la migración `database/migracion_devoluciones.sql` y registrarla en `SQL_FILES` de `init_db.py`.
- No crear un módulo raíz `devoluciones` ni cambiar el límite de seis módulos.
- Mantener el webhook de pago separado: escuchar/conciliar eventos de reembolso Stripe en el servicio de pagos o el servicio de devoluciones según el diseño final.

### Frontend — módulo existente `src/app/modules/ventas_inventario`

- Añadir el acceso del cliente a solicitar devolución desde el detalle de la compra/pago elegible y a consultar sus solicitudes.
- Añadir vistas de lista y detalle para personal autorizado, con filtros, historial, decisión, recepción e información de reembolso.
- Registrar rutas y enlaces en las rutas y el layout existentes de `ventas_inventario`, respetando `roleGuard` y los permisos del servidor.
- Mostrar estados y montos con etiquetas claras, errores recuperables y prevención visual de acciones incompatibles con el estado.

### Mobile — estructura existente

- Añadir modelos y servicio cliente de devoluciones usando `ApiClient` y `ApiConstants` existentes.
- Permitir que el cliente solicite y siga una devolución desde el historial/detalle de compra o pago.
- Si se requiere gestión operativa en mobile, añadirla a las pantallas existentes de perfil/ventas según los roles acordados; no crear un módulo paralelo.
- Mostrar estado, cantidades, monto y resultado del reembolso, sin afirmar éxito hasta que backend confirme.

## Migración y despliegue

1. Crear `database/migracion_devoluciones.sql` con tablas, claves foráneas, índices y restricciones nuevas; debe ser segura al ejecutarse sobre las tablas existentes.
2. Incluirla en `SQL_FILES` de `init_db.py` respetando el orden de dependencias.
3. Confirmar cómo Railway ejecuta `init_db.py` en el despliegue. La rutina actual de inicio de `app/main.py` no itera `SQL_FILES`, así que no se debe asumir que añadir el SQL a la lista basta para aplicarlo automáticamente.
4. Aplicar primero en una base de pruebas, comprobar que no altera ventas, pagos ni inventario existentes y luego desplegar.
5. No precargar devoluciones ni actualizar ventas antiguas automáticamente.

## Decisiones de negocio pendientes

Se deben fijar antes de cerrar las reglas y la interfaz:

1. Plazo máximo desde la compra para solicitar devolución.
2. Motivos permitidos y condiciones de aceptación (sin uso, etiquetas, empaque, defectos, etc.).
3. Si se admite devolución de productos en oferta o de reservas convertidas a venta.
4. Tratamiento del costo de delivery y de cargos de pago.
5. Quién puede aprobar cada tipo de reembolso y si habrá límites por monto.
6. Si el inventario se repone siempre tras la aceptación o si hay artículos que se inspeccionan/descartan.
7. Qué comprobante se exige para reembolsos manuales en efectivo o QR.
8. Si se contemplan cambios de talla/producto como una operación aparte. Recomendación: empezar con devolución y reembolso, y tratar cambios como flujo separado para no mezclar movimientos de stock y dinero.

## Criterios de aceptación

- El cliente solo ve y solicita devoluciones de sus propias ventas elegibles.
- El personal solo gestiona las sucursales que tiene autorizadas; administración puede consultar el alcance definido.
- No es posible aprobar más unidades de las vendidas ni procesar solicitudes concurrentes que superen el saldo retornable.
- Toda devolución aceptada deja trazabilidad de solicitud, decisión, recepción, inventario y reembolso.
- El stock aumenta solo por las unidades recibidas y aceptadas, una sola vez.
- Los importes parciales son reproducibles desde los importes originales y nunca superan el saldo cobrable/reembolsable.
- Un reembolso Stripe fallido o pendiente no se muestra como exitoso y se puede conciliar de forma segura.
- Las pantallas web y mobile muestran los mismos estados persistidos por backend.
- La migración se aplica de forma controlada en Railway y local; no cambia ni borra datos históricos.
- Todos los cambios se mantienen dentro de los seis módulos existentes de backend y frontend.
