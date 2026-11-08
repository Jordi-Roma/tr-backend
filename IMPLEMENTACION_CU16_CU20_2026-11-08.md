# Especificación e implementación de CU16 a CU20 — StyleAR

**Fecha de consolidación:** 08/11/2026.  
**Autor:** Angeles Rosales Colque.  
**Plataformas:** backend FastAPI/PostgreSQL, web Angular y aplicación Flutter.

Este documento cubre el tramo que faltaba entre los informes de CU11–CU15 y CU22–CU27. Consolida las reglas acordadas, los flujos implementados y las verificaciones registradas. La bitácora histórica continúa en `SEGUIMIENTO_IMPLEMENTACION.md`.

Las reglas de negocio se validan en el backend. Una pantalla oculta o un control deshabilitado no sustituyen la autorización, la pertenencia de empresa ni la comprobación de stock y precios.

## 1. Casos de uso incluidos

| Código | Nombre | Aplicaciones |
| --- | --- | --- |
| CU16 | Gestionar ventas digitales y pasarela de pago | Web y móvil. |
| CU17 | Gestionar compras unitarias y por mayor | Compra en web y móvil; configuración mayorista en administración web. |
| CU18 | Gestionar entregas a domicilio | Web y móvil. |
| CU19 | Gestionar cambios de prendas | Web y móvil. |
| CU20 | Gestionar devoluciones y reembolsos | Web y móvil. |

CU21, operación sin conexión, no se implementó en estos bloques. Su ausencia debe tratarse como un pendiente del segundo parcial, sin confundir la idempotencia de pagos con una sincronización comercial offline.

## 2. CU16 — Gestionar ventas digitales y pasarela de pago

### Objetivo y actores

Permitir que el cliente pague una compra de su empresa, consulte su resultado y conserve la trazabilidad entre orden, pago, venta e inventario. Intervienen el cliente, el administrador de empresa que configura los medios y el proveedor de pagos.

### Precondiciones

- Sesión válida y empresa autorizada para iniciar operaciones.
- Carrito con cantidades, precios vigentes y composición válida.
- Medio habilitado y configuración del servidor correspondiente a esa empresa.
- Resumen actualizado y aceptado por el cliente.

### Flujo principal

1. El cliente revisa el carrito y selecciona el medio de pago.
2. El backend valida el contenido, el total y la disponibilidad, y crea o recupera el intento mediante su clave de operación.
3. Se presenta el Checkout Stripe o el flujo de simulación permitido por el servidor.
4. El proveedor confirma el resultado al backend. Abrir la URL de retorno no confirma por sí solo la compra.
5. El servidor verifica empresa, referencia, sesión del proveedor, moneda e importe.
6. La confirmación completa la venta y sus movimientos de inventario dentro de una transacción.
7. El cliente consulta el resultado y puede recuperar intentos pendientes desde el carrito o el historial.

### Reglas y alternativas

- Las credenciales son propias de cada empresa y permanecen en el servidor. Las compras nuevas no utilizan automáticamente la clave global de otro comercio.
- Los reintentos conservan la clave del intento. Una confirmación repetida no crea otra venta ni vuelve a descontar stock.
- La orden conserva su instantánea de precio. Si el total cambia antes de crearla, el cliente debe revisar el nuevo resumen.
- La compra consume las líneas originales; conserva las unidades agregadas al carrito después de iniciar el pago.
- Si se recibe un pago y la compra no puede completarse, se registra un reembolso pendiente. No se presenta como venta completada ni como dinero ya devuelto.
- Se conserva la compatibilidad de anticipos de reservas anteriores, separada de los nuevos webhooks por empresa.

### Estado del proveedor

Stripe **TEST** fue verificado con Checkout, webhook firmado, confirmación automática, idempotencia y reintegro. El proyecto admite claves de prueba; esta validación no habilita Stripe LIVE ni cobros comerciales reales.

El QR BCP continúa como simulación explícita. Sin documentación, URL de sandbox y credenciales del banco no existe confirmación bancaria real. El código simulado no debe utilizarse para transferir dinero.

## 3. CU17 — Gestionar compras unitarias y por mayor

### Objetivo y actores

Permitir al cliente combinar unidades normales con paquetes mayoristas, sujetos a configuración por producto, variedad y stock. El administrador configura los descuentos porcentuales de cada producto en la web.

### Compra unitaria

El cliente puede elegir cantidades de la misma talla/color o combinar variantes, sujeto al stock disponible. Acumular unidades no convierte una línea en compra mayorista automáticamente. El límite de una reserva gratuita no se aplica como límite de compra directa.

### Paquetes y reglas

| Modalidad | Cantidad fija | Variedad requerida |
| --- | --- | --- |
| Cuarta | 3 prendas | Mínimo 2 tallas y 2 colores distintos. |
| Media docena | 6 prendas | Mínimo 3 tallas y 3 colores distintos. |
| Docena | 12 prendas | Al menos una de cada talla definida en las variantes activas del producto. Sin requisito adicional de colores. |

- Un producto con una sola talla no admite paquetes mayoristas.
- La falta de stock no reduce las reglas de variedad. Las tallas activas sin existencias siguen siendo necesarias para la docena; con más de doce tallas no cabe una docena válida.
- Cada modalidad tiene su porcentaje independiente por producto, editable y habilitable. No se asignaron descuentos arbitrarios a los productos locales.
- Sin porcentaje configurado, precio vigente, variedad o stock suficiente, la opción permanece inhabilitada y explica el motivo.
- El descuento se calcula sobre el precio unitario vigente de cada variante, con redondeo monetario a dos decimales. No se acumula con la promoción unitaria.

### Flujo implementado

1. El cliente abre el producto, selecciona la sucursal y el apartado mayorista.
2. Distribuye las cantidades por variante para un paquete fijo.
3. La API comprueba producto, empresa, composición, precio y existencias.
4. El paquete se agrega con identificación propia. Pueden agregarse otros paquetes y unidades normales.
5. El carrito suma el stock requerido de todos los conceptos y distingue unidades y paquetes.
6. CU16 vuelve a validar el resumen antes de generar el pago y conserva las condiciones aceptadas en la venta.

Un paquete se retira completo; para cambiar su composición se arma nuevamente. Los paquetes son de compra directa y no se incorporan a la reserva gratuita. El historial y la nota conservan el tipo de compra, porcentaje y precio neto.

## 4. CU18 — Gestionar entregas a domicilio

### Objetivo y actores

Cotizar, pagar y gestionar la entrega de una compra. El cliente consulta sus entregas; el administrador gestiona las de su empresa; el encargado gestiona las de su sucursal activa. El cajero conserva consulta de su sucursal.

### Flujo principal

1. El cliente selecciona una dirección propia o confirma otra ubicación y la sucursal de origen.
2. El servidor obtiene una ruta de OpenRouteService y guarda distancia, duración, geometría y costo.
3. El cliente acepta el resumen e inicia el pago dentro de los 15 minutos de vigencia de la cotización.
4. La compra incluye el costo de envío. Al confirmarse el pago y la venta, se crea la entrega en la misma transacción.
5. El personal autorizado actualiza el estado y gestiona incidencias.
6. La entrega se completa mediante confirmación explícita de recepción física, sin incidencia abierta.

### Reglas

- Cambiar dirección, referencia, coordenadas o sucursal invalida la cotización. También se comprueba si cambió el origen.
- Se usa el costo guardado por el servidor; no el enviado como autoridad por el cliente.
- La orden creada conserva la cotización aceptada. Un reintento no duplica ORS, compra ni entrega.
- Tarifa conservada: hasta 3 km, Bs 8; hasta 6 km, Bs 12; hasta 10 km, Bs 18. `DELIVERY_MAX_KM`, si está configurado, puede restringir la cobertura.
- Una falla de ORS no se sustituye silenciosamente por una distancia inventada. Se comunica que no puede cotizarse.
- No se ofrece efectivo contra entrega. Una compra pendiente o incumplida no genera un despacho.
- Seguimiento: `PENDIENTE → EN_PREPARACION → EN_CAMINO → ENTREGADO`, con control de versión.
- Cancelar antes del reparto exige motivo y coordinación. La cancelación no acredita un reembolso; ese proceso corresponde a CU20.
- Web y móvil muestran la geometría de la ruta. No se implementó seguimiento GPS en vivo de un repartidor.

La conexión real a ORS fue verificada. Esto no acredita por sí solo que todas las coordenadas físicas de las sucursales estén correctamente cargadas.

## 5. CU19 — Gestionar cambios de prendas

### Objetivo

Solicitar, inspeccionar y realizar el reemplazo de prendas compradas, calculando las diferencias económicas y registrando los movimientos de inventario y el comprobante correspondiente.

### Actores

Cliente; encargado de sucursal y cajero autorizados; administrador de empresa; proveedor de pago cuando existe diferencia económica.

### Precondiciones

- Compra pagada y cantidades elegibles pertenecientes al cliente y empresa actuales.
- Política de cambios habilitada, con plazo y condiciones configurados por la empresa.
- Personal autorizado para la sucursal de la operación.
- Stock y precio válidos del reemplazo antes de aceptarlo.

### Flujo principal

1. El cliente abre **Mis cambios** en web o **Cambios de prendas** en móvil y selecciona línea de compra, cantidad y motivo.
2. El servidor valida propiedad, pago, plazo y cantidades no comprometidas en otras solicitudes.
3. La tienda confirma la recepción física e inspecciona la prenda, indicando aceptación, rechazo y condición de las unidades no vendibles.
4. Se calcula el crédito según lo efectivamente pagado por las prendas originales, después de descuentos y sin el envío.
5. El cliente consulta reemplazos de la misma sucursal, pudiendo elegir otra talla, color o modelo.
6. Se cotiza el reemplazo a precio unitario y promoción vigentes. La cotización dura 15 minutos.
7. El cliente acepta expresamente la composición y la diferencia; el servidor revalida precio, stock y versión y reserva el reemplazo.
8. Se liquida la diferencia según el caso. La reserva todavía no representa salida definitiva de inventario.
9. El personal confirma la entrega física. En una transacción se libera la reserva, registra la salida del reemplazo y repone únicamente las prendas originales vendibles.
10. Se emite el comprobante vinculado a la compra original y se registra el aviso al cliente.

### Alternativas económicas y excepciones

| Situación | Tratamiento |
| --- | --- |
| Reemplazo del mismo valor | Queda listo para entrega sin cobro adicional. |
| Reemplazo de mayor valor | Orden específica de diferencia; la entrega espera su pago validado. |
| Reemplazo de menor valor | Reintegro únicamente del excedente por el medio original; la entrega espera confirmación del reintegro. |
| Sin reemplazo disponible o deseado | Con aceptación del cliente se continúa por CU20, aprovechando la solicitud y sin duplicar cantidades. |
| Prenda original no vendible | Se registra condición y recepción; no aumenta automáticamente el stock vendible. |
| Desistimiento antes de liquidar | Se libera la reserva cuando es seguro. Un resultado de pago incierto exige conciliación. |
| Pago tardío de intento cerrado | Se trata como operación incumplida con reintegro pendiente. |

### Reglas y postcondiciones

- Cada solicitud corresponde a una línea y cantidad; otras líneas requieren sus solicitudes.
- CU19 y CU20 comparten el cálculo de unidades comprometidas para impedir que una misma unidad se tramite dos veces.
- Un reemplazo no se cotiza como un nuevo paquete mayorista.
- La inspección por sí sola no repone existencias.
- Si la compra fue electrónica, su reintegro no se registra como efectivo. Para efectivo se exige referencia de entrega en caja.
- Completar o reintentar la entrega no duplica movimientos ni comprobantes.
- El estado económico se conserva separado de inspección y entrega. Un callback repetido no degrada un cambio ya completado.
- La solicitud conserva su clave ante respuestas inciertas, y el servidor valida roles, empresa, sucursal y versión en cada escritura.

Al completarse, quedan registrados el reemplazo entregado, la liquidación económica, los movimientos y el comprobante. Si falta liquidación o entrega, la operación mantiene su estado pendiente correspondiente.

## 6. CU20 — Gestionar devoluciones y reembolsos

### Objetivo

Gestionar devoluciones voluntarias, reintegros de compras pagadas incumplidas y saldos derivados de cambios, sin exceder lo comprado o pagado ni duplicar inventario o dinero.

### Actores

Cliente; administrador de empresa; encargado de sucursal y cajero autorizados; proveedor de pago.

### Precondiciones

- Venta o pago original identificable y perteneciente a la empresa y cliente autorizados.
- Cantidades e importe todavía elegibles.
- Para devolución voluntaria: política habilitada, plazo y condiciones válidos.
- Para la revisión: personal autorizado de la sucursal correspondiente.

### Flujo de devolución voluntaria

1. El administrador configura y habilita plazo y condiciones en **Políticas de posventa**. No se fija un plazo comercial arbitrario.
2. El cliente abre **Mis devoluciones**, selecciona una compra pagada e informa motivo y cantidades.
3. El servidor valida elegibilidad y conserva la política aplicable y la clave de solicitud.
4. El personal revisa y recibe las prendas, distinguiendo cantidades aceptadas, rechazadas y no vendibles.
5. Se informa el importe resultante. La inspección deja la solicitud en espera de aceptación y todavía no aumenta existencias.
6. El cliente acepta el importe y se genera el comprobante comercial. Se reponen una sola vez las prendas vendibles y queda el reembolso pendiente.
7. Se solicita o registra el reintegro por el medio original.
8. La confirmación validada actualiza el estado económico y se notifica al cliente.

### Alternativas

- **Compra pagada incumplida:** por ejemplo, falta de stock al confirmar. Se gestiona el importe correspondiente sin aplicar el plazo de devolución voluntaria ni exigir recibir una prenda no entregada.
- **Cambio sin reemplazo:** CU19 deriva la operación con aceptación del cliente y recepción inspeccionada.
- **Reemplazo de menor valor:** se devuelve solo la diferencia, sin repetir el movimiento de inventario del cambio.
- **Cantidad o importe excedido:** se rechaza el exceso y se conservan las operaciones previas.
- **Prenda rechazada o no vendible:** se registra el dictamen; una prenda no vendible no vuelve al stock disponible.
- **Falla o respuesta incierta del proveedor:** el dinero continúa pendiente de confirmación y el reintento conserva su referencia idempotente.

### Reglas y postcondiciones

- Las unidades comprometidas en inspección o reintegro no pueden solicitarse nuevamente por CU19 o CU20.
- Se prorratea el importe efectivamente pagado después de descuentos, con ajuste de centavos en las últimas unidades. No se incluye el envío en el cálculo ordinario de prendas devueltas.
- La política se conserva al solicitar; deshabilitarla posteriormente no invalida solicitudes existentes.
- El comprobante, la reposición y la confirmación del dinero son hechos diferenciados. Un comprobante no acredita un reintegro ejecutado.
- Los pagos electrónicos se reintegran por su medio original. Un reintegro en efectivo requiere aceptación previa y referencia de caja.
- La confirmación repetida no duplica devolución, reposición ni reintegro.
- La conciliación Stripe valida empresa, pago original, moneda, importe y referencia.

La devolución queda reembolsada cuando existe la confirmación económica correspondiente. Hasta entonces, permanece identificada como pendiente, aunque la inspección y el comprobante ya estén completos.

## 7. Configuración y acceso para pruebas

- **Mayoristas:** configurar los porcentajes por producto en administración web antes de intentar paquetes.
- **Cambios y devoluciones:** como administrador, abrir Políticas de posventa y habilitar cada política con su plazo y condiciones. No se cargaron valores arbitrarios de prueba en la empresa real.
- **Stripe TEST:** configurar la clave y firma propias de la empresa únicamente en el servidor. Para la empresa 1, el receptor local se inicia desde `tr-backend` con:

```powershell
.\.venv\Scripts\python.exe scripts/escuchar_stripe.py --empresa 1
```

Después de que el receptor guarde su firma, iniciar o reiniciar la API para cargarla. Mantener receptor y API funcionando durante los ensayos. El receptor local no sustituye un webhook HTTPS desplegado.

- **ORS:** requiere la clave del servidor y ubicaciones válidas de sucursal y destino.
- **Firebase:** la conexión Android local fue verificada posteriormente y ampliada en CU27. La bandeja sigue disponible aunque el push falle o el permiso esté desactivado.
- **QR BCP:** solo simulación identificada hasta recibir la habilitación técnica del banco.

Este documento no incluye claves, contraseñas ni credenciales. Su creación no inicia servidores.

## 8. Migraciones y archivos de prueba

| Área | Migración |
| --- | --- |
| Pagos por empresa | `database/migracion_cu16_bloque1.sql` |
| Mayoristas | `database/migracion_cu17_mayorista.sql` |
| Entregas | `database/migracion_cu18_delivery.sql` |
| Políticas y devoluciones | `database/migracion_posventa_politicas.sql` |
| Cambios | `database/migracion_cu19_cambios.sql` |

Se aplicaron con respaldos previos y se verificó la repetición del inicializador sin duplicar las migraciones. Al cierre posterior de CU22–CU27, la base local tenía las 18 versiones previstas aplicadas.

Pruebas backend de referencia, dentro de `tests/`:

- `test_cu16_bloque1_integration.py`.
- `test_cu17_mayorista_integration.py`.
- `test_cu18_delivery_integration.py`.
- `test_posventa_politicas_integration.py`.
- `test_cu19_cambios_integration.py`.
- `test_escuchar_stripe.py`.

Los clientes disponen de pruebas Flutter y recorridos web E2E equivalentes para pagos, paquetes mayoristas, entregas, posventa y cambios. Se verificaron reglas comerciales, aislamiento, reintentos, liquidación de diferencias, aceptación del cliente e inspección de prendas no vendibles. Las pruebas con simuladores no acreditan conexión bancaria real.

## 9. Evidencias externas y límites

**Stripe TEST:** el usuario completó un Checkout de Bs 50 en una base desechable. El webhook validado completó una venta y descontó una unidad. Repetir el evento no duplicó venta ni descuento. CU20 gestionó después un reintegro de Bs 50 con estado `succeeded`; la devolución quedó reembolsada y el stock regresó a su valor original. El reintento conservó la misma referencia. No se movió dinero real.

**OpenRouteService:** se verificó una consulta real y se corrigió el uso del formato GeoJSON. Los mapas muestran rutas devueltas por el proveedor; no seguimiento en vivo.

**Firebase:** se verificaron registro y recepción Android. En CU27 se probaron primer plano, segundo plano, proceso cerrado y pantalla bloqueada, distinguiendo aceptación del proveedor, visualización y lectura.

**BCP:** documentación, sandbox y credenciales pendientes del banco. No se inventaron endpoints ni se presentó el simulador como pago real.

**Despliegue y datos:** los ensayos comerciales utilizaron bases sintéticas y se retiraron al finalizar. No equivalen a una validación de producción. La última petición de cerrar el entorno dejó los servidores detenidos.

## 10. Relación con las fichas y diagramas

Las fichas académicas de CU19 y CU20 están en `output/segundoParcial_grupo02_pruebas_CU01_CU20.docx`, desde la raíz del proyecto. Este Markdown las complementa con las reglas y el estado de implementación consolidado.

Los diagramas editables están en la raíz: `CU19_Detallar_CU.drawio`, `CU19_Secuencia.drawio`, `CU20_Detallar_CU.drawio` y `CU20_Secuencia.drawio`. También existen los archivos conjuntos de CU16–CU20.

Para los bloques siguientes, consultar `INFORME_IMPLEMENTACION_CU22_CU27.md` en la raíz. El avance histórico de todos los bloques se mantiene únicamente en `SEGUIMIENTO_IMPLEMENTACION.md` del backend.


## 11. Actualización de interfaz: selección inicial y módulos agrupados (08/11/2026)

En web y móvil el cliente puede elegir producto, talla y color del reemplazo al solicitar el cambio. La interfaz consulta las variantes disponibles de la sucursal de su compra y muestra una diferencia estimada. El backend conserva esa elección en la solicitud y la incorpora a su huella de idempotencia.

Este paso no reserva existencias ni crea un pago: la solicitud continúa pendiente de inspección. Tras aprobar la recepción, el cliente revisa nuevamente disponibilidad y precio y acepta la cotización definitiva; entonces se aplican los flujos de pago/reintegro de CU19 descritos en este documento.

Devoluciones y Cambios se agrupan mediante tarjetas en Posventa; las solicitudes se abren después de elegir una tarjeta. Políticas posventa queda en la misma entrada y solo es configurable por el administrador. Pagos de prueba se accede desde Pagos. Productos reúne categorías, tallas, colores, marcas, temporadas, colecciones, variantes y promociones mediante tarjetas, y sus acciones por producto se presentan como botones.

La entrega se verificó con 30 pruebas backend de cambios/posventa, 34 web, 88 Flutter, dos recorridos Edge/AXE y las compilaciones web/APK. Los ensayos utilizaron datos sintéticos y no cambiaron la empresa real. No se requirió migración nueva para guardar la elección inicial. El detalle de archivos y validaciones está en SEGUIMIENTO_IMPLEMENTACION.md.
