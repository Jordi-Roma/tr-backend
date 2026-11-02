# Seguimiento de implementación de StyleAR

Autor: Angeles Rosales Colque.

Este archivo reúne el arranque local, las reparaciones y el avance por bloques. Se actualizará con cada implementación.

## Desarrollo local en Windows

Desde `tr-backend`, usando el entorno instalado:

```powershell
.\.venv\Scripts\python.exe init_db.py
if ($LASTEXITCODE -eq 0) {
    .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
}
```

En otra terminal, desde `tr-frontend`:

```powershell
npm start -- --host 127.0.0.1
```

Web: http://127.0.0.1:4200/
API: http://127.0.0.1:8000/docs

La conexión se toma del `.env` del backend. Las migraciones versionadas se
registran en `schema_migrations`; volver a ejecutar el inicializador las omite.
No registrar versiones manualmente para eludir errores.

### Reparación local del 24 de octubre de 2026

La primera migración multitenant fallaba porque los SKU `pol1` y `POl1`
colisionaban con el nuevo índice que ignora mayúsculas. Se mantuvo la variante
3 con `pol1` y se cambió únicamente el SKU de la variante 7 a `POl1-7`.
No se eliminaron variantes ni sus referencias.

Se corrigieron las migraciones antiguas de tipos de movimiento para aceptar
`DEVOLUCION_VENTA`, evitando fallos al ejecutarlas sobre datos de devoluciones.
Las cuatro migraciones versionadas quedaron aplicadas.

Respaldo previo: `.private/antes_migraciones_20261024.dump`.
Registro del cambio de SKU: `.private/reparacion_sku_20261024.json`.
Estos archivos están excluidos de Git.

## Bloque 1: CU06 — Gestionar ciudades y sucursales

Autor: Angeles Rosales Colque. Fecha: 24/10/2026.

Primer bloque de implementación de las fichas CU06–CU10 del 23/10/2026.
CU06, CU07 y CU09 tienen interfaz web. CU08 y CU10 incluyen además las
consultas autorizadas del proveedor en Flutter, en los bloques posteriores.

### Comportamiento implementado

- El administrador comercial gestiona las ciudades y sucursales de su empresa.
  El administrador SaaS no gestiona ciudades comerciales.
- Las ciudades originales mantienen sus identificadores y pertenecen a StyleAR.
  Si una base heredada contiene referencias de otra empresa, la migración crea
  copias de esas ciudades para esa empresa y actualiza únicamente sus referencias.
- Los nombres de ciudad/departamento no se repiten dentro de una empresa, ignorando
  mayúsculas. Distintas empresas pueden utilizar los mismos nombres.
- Sucursales y direcciones sólo pueden referenciar ciudades de su empresa. La API
  valida la asociación y PostgreSQL añade una barrera de integridad independiente.
- Crear o editar una sucursal requiere una ciudad activa. No se desactiva una
  ciudad con sucursales activas. Una sucursal no se reactiva si su ciudad está inactiva.
- Las desactivaciones conservan los registros. Las pantallas administrativas
  muestran también inactivos para permitir reactivarlos. Los selectores mantienen
  la consulta de ciudades activas como comportamiento predeterminado.
- El alta/reactivación de sucursales controla el límite del plan dentro de una
  transacción con bloqueo de empresa. Las consultas y desactivaciones siguen
  disponibles con suscripción suspendida; las altas y reactivaciones se rechazan.
- Las operaciones administrativas exigen rol de administrador de empresa y el
  permiso correspondiente. Las cuentas comerciales conservan la consulta de
  ciudades de su empresa necesaria para sus direcciones.
- Los respaldos selectivos incluyen las ciudades como datos comerciales y ya
  no como referencias globales.
- Las pantallas CU06 tienen contraste y jerarquía de encabezados revisados con
  AXE. Los formularios modales contienen el foco, cierran con Escape y devuelven
  el foco al control de apertura. La ubicación de sucursal admite coordenadas
  mediante teclado además del mapa.

### Persistencia y arranque

Nueva migración: `2026_10_24_cu06_01`, registrada mediante `init_db.py`.
La API verifica su presencia al iniciar. No ejecutar el SQL manualmente ni
insertar la versión para eludir un error.

```powershell
cd C:\MATERIAS\SI2\Presentacion\tr-backend
.\.venv\Scripts\python.exe init_db.py
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

En otra terminal:

```powershell
cd C:\MATERIAS\SI2\Presentacion\tr-frontend
npm start
```

Respaldo local previo a CU06:
`.private/antes_cu06_20261024_230425.dump`, excluido de Git.
Se verificó que la migración local conserva IDs/nombres de ciudades y las
referencias de sucursales, y que repetir el inicializador omite la versión aplicada.

### Validación

Las pruebas PostgreSQL usan únicamente una base local desechable `stylear_test_*`
con `DATABASE_URL` y `STYLEAR_TEST_DATABASE_URL` explícitas e idénticas.
No ejecutar la suite de integración sobre la base StyleAR.

100 pruebas aprobadas en la suite de CU06, multitenant, cuentas, CU04/CU05
y fundamentos. Incluyen duplicados, asociación ajena, acceso por ID, historial,
reactivación, cupo concurrente, estado de suscripción, direcciones y restauración.

Pruebas de navegador: `tr-frontend/e2e/cu06.spec.ts`, usando la fixture PostgreSQL
real descrita en `tr-frontend/e2e/README.md`. Comprueban las dos pantallas,
aislamiento, formularios, estados y accesibilidad con AXE.
Resultado: 2 recorridos aprobados, sin incidencias AXE en las vistas comprobadas;
compilación Angular de desarrollo correcta. Las bases desechables se retiraron
al terminar las pruebas.

### Recorrido manual

1. Ingresar como administrador de StyleAR; abrir Ciudades y comprobar los datos originales.
2. Crear una ciudad y una sucursal asociada. Intentar desactivar la ciudad: se debe rechazar.
3. Desactivar la sucursal y luego la ciudad. Ambas deben permanecer visibles como inactivas.
4. Intentar reactivar primero la sucursal: se debe rechazar. Activar la ciudad y luego la sucursal.
5. Ingresar como administrador de otra empresa: no debe ver las ciudades/sucursales de StyleAR.
6. Comprobar que un nombre de ciudad puede repetirse en otra empresa, pero no en la misma.

CU07–CU08 se completan en el bloque 2 descrito más abajo; CU09–CU10 siguen pendientes. Este bloque no agrega
pantallas administrativas en móvil ni modifica la carga de existencias del CU14.

## Bloque 2: CU07–CU08 — Implementado

Empleados: solo web. Proveedores: administración web y consulta autorizada en web/móvil.

### CU07 — Empleados, solo web

- El administrador registra una cuenta y su empleado en una transacción, o
  asigna una cuenta existente mediante un selector de su empresa.
- Sólo se admiten CAJERO, ENCARGADO_SUCURSAL y PERSONAL_VENTAS como roles laborales.
  No se permite elevar cuentas a administrador desde este módulo ni modificar
  cuentas administrativas mediante vínculos de empleado.
- El encargado consulta únicamente los empleados de su sucursal activa asignada.
  No dispone de formularios de modificación y la API rechaza todas sus escrituras.
  El modelo actual mantiene una asignación de sucursal por empleado.
- El administrador puede editar asignaciones, desactivar y reactivar empleados.
  La desactivación conserva el rol laboral en la ficha; la reactivación pide
  confirmarlo, sin sustituirlo por un rol de mayor privilegio.
- Los cambios de rol, asignación o estado cierran las sesiones afectadas. Los
  datos e historial se conservan; no se elimina la cuenta por desactivar al empleado.
- Los límites de usuarios y empleados se comprueban dentro de la transacción;
  un fallo no deja una cuenta sin empleado. Los códigos se separan por empresa.
  Se mantiene la regla existente de usuario y correo únicos globalmente.

### CU08 — Proveedores, web y móvil

- El administrador registra y modifica proveedores, gestiona su estado, crea
  cuentas vinculadas o vincula cuentas comerciales existentes de su empresa.
- Crear la cuenta, asignar PROVEEDOR y guardar el vínculo es una sola operación.
  Vincular una cuenta existente asigna ese rol y exige ingresar nuevamente.
  No depende de crear primero un usuario PROVEEDOR desde Usuarios, que requería
  un vínculo todavía inexistente.
- Cada cuenta tiene como máximo un vínculo activo de proveedor. La plataforma
  nunca selecciona arbitrariamente el primero entre varios vínculos. Distintas
  cuentas pueden representar a un mismo proveedor. La migración falla si hay
  ambigüedades heredadas, en lugar de retirar autorizaciones silenciosamente.
- El administrador asocia o retira productos de su empresa desde la ficha del
  proveedor. Se conserva el vínculo histórico con estado inactivo al retirarlo.
- Los paneles web y Flutter muestran únicamente el perfil, productos, existencias
  y entregas autorizados del proveedor vinculado; no ofrecen acciones de escritura.
  El servidor obtiene el proveedor de la sesión, no de un ID enviado por el móvil.
- Desvincular la cuenta o desactivar el proveedor revoca el acceso y cierra las
  sesiones afectadas. La reactivación recupera los vínculos conservados y exige
  nuevo ingreso. Las entregas e inventarios históricos no se eliminan.
- Flutter ofrece navegación propia del proveedor hacia su panel y cuenta, sin
  cargar carrito, reservas de cliente ni gestión de catálogo. Permite actualizar
  y reintentar, retira datos ante rechazos y descarta respuestas de otra sesión/empresa.
- Inventario conserva un selector mínimo de proveedores activos para el encargado,
  sin concederle acceso a la administración CU08.

### Migración, pruebas y respaldo del bloque 2

Migración: `2026_10_24_cu07_cu08_01`. Añade el rol laboral conservado y la
unicidad del vínculo activo por cuenta de proveedor. `init_db.py` la registra;
la API exige esta versión antes de servir peticiones.

Respaldo local previo: `.private/antes_cu0708_20261024_233948.dump`.
Se verificó que se conservan ciudades, referencias de sucursales, empleados y
sus estados. El respaldo es privado y está excluido de Git.

Validaciones:

- 100 regresiones de backend de los bloques anteriores aprobadas.
- 14 pruebas PostgreSQL de CU07/CU08 aprobadas, incluyendo aislamiento, permisos,
  roles prohibidos, cuotas concurrentes, atomicidad, cierre de sesiones, cuentas
  y vínculos de proveedores, productos, stock y entregas reales.
- 4 recorridos Playwright de CU07/CU08 aprobados, con AXE sobre las pantallas
  y formularios verificados: administrador de empleados, encargado de consulta,
  administrador de proveedores y panel propio del proveedor.
- 24 pruebas Flutter aprobadas; análisis sin incidencias y compilación web correcta.
  Las pruebas móviles usan HTTP simulado; el aislamiento real del panel se valida
  con PostgreSQL/API. No sustituyen una prueba manual en teléfono físico.
- Compilación Angular de desarrollo correcta.

### Recorrido manual del bloque 2

1. Iniciar backend y frontend con los comandos del comienzo de este archivo.
2. Como administrador, abrir Empleados, crear una cuenta y seleccionar sucursal
   y rol. Editar su cargo, desactivar y reactivar confirmando el rol laboral.
3. Como encargado, abrir Empleados: sólo debe consultar registros de su sucursal.
4. Como administrador, crear un proveedor, abrir su ficha con Editar y crear
   una cuenta vinculada. Asociar un producto propio desde la misma ficha.
5. Ingresar con esa cuenta de proveedor: comprobar sus productos, existencias
   y entregas. Repetir en Flutter mediante el panel Mi proveedor.
6. Retirar el vínculo o desactivar el proveedor desde el administrador. La sesión
   anterior debe dejar de tener acceso. Reactivar y volver a ingresar para consultar.

Móvil, desde `tr-mobile`, con un emulador Android iniciado:

```powershell
flutter run --dart-define=API_URL=http://10.0.2.2:8000
```

En teléfono físico conectado a la misma red, sustituir `10.0.2.2` por la IPv4
local de la PC. El backend debe escuchar en `0.0.0.0` como se indica al comienzo.
El móvil usa Railway por defecto si se omite `API_URL`.

### Pendientes

CU09 se desarrolla en el bloque 3 de este mismo archivo. El siguiente bloque
es CU10 (productos, variantes y promociones, con el alcance móvil acordado).
Las consultas de productos del proveedor ya están conectadas por CU08; la
administración completa de CU10 se revisará en su bloque. CU14 no se modifica
para cargar stock al crear productos.

Este es el único archivo de seguimiento nuevo: reemplaza ARRANQUE_LOCAL.md e
IMPLEMENTACION_CU06_2026-10-24.md. Los informes que ya existían en el repositorio
sobre otros bloques se conservan como antecedentes.


## Bloque 3: CU09 — Gestionar clasificaciones del catálogo

Autor: Angeles Rosales Colque. Fecha: 24/10/2026.

Alcance: categorías, tallas, colores, marcas, temporadas y colecciones, sólo web.
El administrador comercial consulta, crea, edita, desactiva y reactiva sus
clasificaciones. El móvil no incorpora administración de CU09.

### Comportamiento implementado

- Las seis escrituras verifican la empresa y el administrador dentro de la
  transacción, respetan la vigencia del plan y registran la auditoría en el mismo
  commit. Un fallo revierte tanto el registro como su auditoría.
- Las operaciones de clasificación comparten los bloqueos administrativos de
  CU04/CU07/CU08. Los duplicados concurrentes devuelven conflicto, conservando una
  sola clasificación. Se ignoran mayúsculas y espacios exteriores en el nombre.
  Los inactivos también reservan su identidad para conservar el historial.
- La identidad de talla incluye el tipo de prenda; la de temporada incluye el
  año; la de colección incluye su temporada. Distintas empresas pueden utilizar
  los mismos nombres sin compartir sus registros.
- Categorías: padre activo de la misma empresa; no se admiten ciclos ni elegir
  descendientes como padre. No se desactiva una categoría con hijos o productos
  activos. Para desactivar una jerarquía se comienza por los hijos.
- No se desactivan tallas o colores con variantes activas, marcas con productos
  activos, temporadas con colecciones activas ni colecciones con productos
  activos asociados. Las relaciones históricas no se eliminan.
- Categorías y colecciones sólo se reactivan con su padre/temporada activo.
  Un intento inválido conserva los datos y su estado anterior.
- La API limita los textos a la capacidad de las columnas. Las tallas admiten
  SUPERIOR, INFERIOR o VESTIDO y medidas opcionales entre 0,01 y 9999,99 cm;
  se rechazan valores no finitos. Se conserva la validación hexadecimal de
  colores y el intervalo 2000–2200 para los años.
- Los formularios web validan nombres y longitudes, muestran errores de API
  dentro del diálogo y conservan lo escrito ante un rechazo. Se confirma cada
  cambio de estado. La consulta fallida ofrece Reintentar consulta.
- Se corrigió el formulario de marcas que permanecía abierto y vacío después
  de guardar. Las seis pantallas usan encabezados, mensajes y contraste
  revisados, con los modales accesibles compartidos.

### Base de datos y validación

Este bloque no necesita cambios de esquema ni una nueva migración. Se verificó
la base local en modo de lectura: las seis versiones existentes están aplicadas,
no hay ciclos ni duplicados en las clasificaciones y la API inicia con health 200.
También se verificó la inicialización de una base desechable y su segunda
ejecución, que omite correctamente las migraciones ya aplicadas.

Las pruebas de API y navegador usan bases PostgreSQL locales desechables;
no insertan datos de prueba en StyleAR.

- 22 casos de CU09 aprobados en PostgreSQL/API: CRUD de las seis clasificaciones,
  aislamiento, permisos, historial, validación, duplicados concurrentes, ciclos
  concurrentes, dependencias y reversión de datos/auditoría antes del commit.
- 16 pruebas de regresión multitenant aprobadas.
- Compilación Angular de desarrollo correcta.
- 8 recorridos Playwright de CU09 aprobados: verifican el CRUD de las seis pantallas,
  el rechazo de duplicados y la recuperación tras un fallo de comunicación,
  además de AXE en listados y formularios.

### Recorrido manual del bloque 3

1. Iniciar backend y frontend con los comandos del comienzo de este archivo.
2. Como administrador, abrir cada clasificación; crear, buscar, editar,
   desactivar y reactivar un registro sin asociaciones activas.
3. Crear una categoría hija y comprobar que el padre no puede desactivarse ni
   elegirse a sí mismo o a su hija como padre.
4. Crear temporada y colección. Intentar desactivar primero la temporada:
   debe explicar el conflicto. Desactivar la colección y después la temporada;
   la colección no podrá reactivarse hasta reactivar su temporada.
5. Probar un nombre duplicado: el diálogo conserva los datos y explica el
   conflicto. Revisar los filtros Todos/Inactivos para recuperar registros.
6. Con otra empresa, verificar que sólo aparecen sus propias clasificaciones.

CU10 se implementa en el bloque 4 de este archivo. CU14 no se utiliza
para cargar stock al crear productos.

Los servicios temporales de prueba se detuvieron y sus dos bases desechables
se eliminaron al cerrar el bloque. No se dejan backend ni frontend ejecutándose.


## Bloque 4: CU10 — Gestionar productos, variantes y promociones

Autor: Angeles Rosales Colque. Fecha: 25/10/2026.

Alcance confirmado con la ficha del 23/10/2026: administrador de empresa en web;
proveedor con consulta de sus productos y existencias en web y Flutter. No se
incorpora carga de stock al crear productos o variantes; corresponde a CU14.

### Comportamiento implementado

- El alta de producto permite agregar varias variantes y precios iniciales en
  el mismo formulario. Se confirma mediante un único POST /api/v1/productos;
  cualquier error revierte producto, variantes, imágenes, precios y vínculos.
  También se admite guardar el producto y completar sus variantes después.
- Desde cada producto se abren sus variantes/precios o una promoción con ese
  producto preseleccionado. Se conservan los formularios separados para la
  administración posterior.
- Todas las escrituras de CU10 verifican empresa, administrador, versión de
  acceso y vigencia del plan dentro de la transacción. El cupo de productos se
  cuenta después del bloqueo de empresa, tanto al crear como al reactivar.
  La auditoría se guarda con el identificador afectado en el mismo commit.
- Categorías, marcas, colecciones, temporadas y proveedores deben ser propios
  y activos. Las tallas deben corresponder al tipo de prenda. Cambiar el tipo
  del producto se rechaza si contradice las tallas de sus variantes existentes.
- No se repite un SKU dentro de la empresa, ignorando mayúsculas y espacios
  exteriores, ni una combinación talla/color dentro del producto. Las
  características no aplicables también cuentan como una combinación. Los
  inactivos conservan su identidad para no duplicar registros históricos.
- Los textos, tipos de prenda/corte, medidas e importes se validan antes del
  guardado. Las medidas deben estar entre 0,01 y 9999,99 cm; los precios son
  positivos, finitos y admiten hasta dos decimales.
- Se conserva el administrador de imágenes por URL o archivo del equipo. Se
  valida formato, tamaño de archivo de hasta 5 MB, URLs y una sola principal.
  Retirar una imagen la desactiva; reincorporar su URL conserva su identificador.
  La URL opcional del modelo 3D también se conserva al editar desde web.
- Cambiar proveedores o colecciones retira sus vínculos mediante estado lógico,
  conservando las relaciones anteriores. Las consultas administrativas, de
  proveedores, catálogo y recomendaciones utilizan únicamente vínculos activos.
- No se desactiva un producto o variante con existencias reservadas. La creación
  de reservas comparte bloqueos de producto/variante antes de comprometer stock,
  para evitar aceptar una variante desactivada durante la operación.
- Desactivar un producto desactiva sus variantes sin borrar inventario ni precios.
  Reactivar el producto no reactiva automáticamente todas sus variantes: éstas
  se habilitan individualmente, validando nuevamente producto, talla y color.
- Los precios programados conservan el precio anterior hasta su fecha de inicio.
  Un precio temporal mantiene también el tramo posterior cuando corresponde.
  El historial distingue vigente, programado, finalizado y reemplazado.
- Las promociones validan fechas, porcentaje y productos/sucursales de la empresa.
  Un descuento fijo se rechaza si supera un precio asociado en el período; bajar
  un precio también comprueba los descuentos fijos que le aplicarían.
- La web permite seleccionar sucursales y conserva ese alcance al editar.
  Sin sucursales seleccionadas, aplica a toda la empresa. Los vínculos retirados
  de productos/sucursales quedan históricos y no siguen aplicándose al catálogo
  ni al precio utilizado por el carrito. Una promoción vencida requiere ajustar
  su vigencia antes de reactivarse.
- El proveedor no puede escribir productos, variantes, precios ni promociones.
  En Flutter puede desplegar un producto autorizado y consultar material, género
  y existencias por SKU/sucursal con los datos recibidos por su sesión. No se
  agregan controles de creación, edición ni carga de stock.

### Migración y conservación de datos

Nueva migración versionada: 2026_10_25_cu10_01, ejecutada mediante init_db.py.
Añade estados lógicos a producto_coleccion, promocion_producto y
promocion_sucursal; admite características no aplicables y protege las
combinaciones únicas de variantes incluyendo valores nulos. La API comprueba
esta versión al arrancar.

Se verificaron las combinaciones heredadas antes de migrar. Respaldo local:
`.private/antes_cu10_20261025_001244.dump`, excluido de Git.
La migración se aplicó en la base local y una segunda ejecución omitió las siete
versiones ya aplicadas. Se compararon los productos, variantes, precios,
vínculos, promociones y existencias antes/después sin cambios en sus datos.

### Validación del bloque

- 22 casos PostgreSQL/API de CU10: registro conjunto y reversión, referencias,
  permisos, aislamiento, SKU/combinaciones concurrentes, cuotas concurrentes,
  historial, dependencias de reservas, precios futuros/temporales y promociones.
- 52 regresiones aprobadas de CU07/CU08, CU09 y multitenant; las 16 multitenant
  se volvieron a ejecutar tras reforzar la validación de reservas.
- 3 recorridos Playwright aprobados con AXE en las pantallas y formularios
  revisados: producto con imagen/variante/precio, variantes e historial de
  precios, y promociones con sucursales y validación de descuentos.
- Angular: compilación de desarrollo correcta.
- Flutter: 25 pruebas aprobadas, análisis sin incidencias y compilación web
  correcta. El panel móvil se
  prueba con HTTP simulado; el aislamiento y rechazo de escrituras del proveedor
  también se prueban sobre PostgreSQL/API. No sustituye una prueba en teléfono.

### Recorrido manual del bloque 4

1. Iniciar backend y frontend con los comandos del comienzo del archivo.
2. Como administrador, abrir Productos, completar sus asociaciones e imágenes
   y agregar variantes iniciales con precios. Confirmar el registro.
3. Abrir Variantes y precios desde su fila y comprobar el filtro del producto.
   Editar la variante o agregar otra combinación. Intentar repetir una para
   comprobar que se conserva el formulario y se explica el conflicto.
4. Programar un precio futuro o temporal y revisar el historial. El precio
   actual sigue aplicándose hasta el inicio del nuevo intervalo.
5. Crear una promoción, seleccionar sus productos y sucursales, guardar y
   volver a editar. Comprobar que el alcance se conserva. Intentar un descuento
   inválido o fechas invertidas para revisar el rechazo.
6. Con un proveedor vinculado, consultar sus productos y stock desde web y
   Flutter. En móvil desplegar la ficha de un producto; no debe haber controles
   de escritura. Otra empresa no debe acceder a estos recursos.

Estado: CU06–CU10 implementados en los cuatro bloques registrados. No se
realizaron commits, push ni despliegue remoto. Las pruebas usan bases locales
desechables, independientes de StyleAR.

Al cerrar CU10 se detuvo el servidor temporal y se eliminaron sus dos bases
desechables. No quedan backend ni frontend ejecutándose. La base local StyleAR
conserva sus datos y la migración CU10 aplicada.

## CU16–CU20 · Bloque 1: pagos de prueba por empresa y bases de reintegros y avisos

Fecha: 30/10/2026. Autor: Angeles Rosales Colque.

### Alcance y diferencias con los pagos anteriores

- Cada empresa configura sus medios de prueba desde **Pagos de prueba**. Sólo
  el administrador comercial puede guardar esa configuración. Las credenciales
  se resuelven en el servidor por ID de empresa; no se envían al navegador ni al
  móvil. Las compras nuevas no usan la clave Stripe global de otro comercio.
- Stripe admite únicamente claves `sk_test_`. Sin clave de esa empresa se usa un
  simulador local identificado como tal. El QR es una **simulación de StyleAR**,
  sin cuenta bancaria ni dinero real; el código comienza con
  `STYLEAR-PRUEBA-NO-PAGAR`. La conexión oficial BCP queda pendiente de contrato,
  documentación y credenciales. Su endpoint no confirma pagos: responde 503.
- Abrir una URL de retorno no confirma la compra. Web y Flutter consultan el
  estado del servidor. Las acciones de simulación sólo aparecen cuando el
  servidor las autoriza; no pueden aprobar una sesión Stripe conectada.
- La clave de operación se conserva para reintentar una solicitud cuya respuesta
  se perdió. La API evita crear otra venta o sesión de pago para el mismo intento,
  comprueba el total mostrado y conserva el precio de la orden. Un intento
  pendiente se puede recuperar desde el carrito o el historial.
- Los eventos firmados verifican empresa, sesión, importe, moneda y referencia.
  Repetir una confirmación no vuelve a descontar stock ni duplica la compra.
  La compra y sus movimientos se confirman en una transacción; si falla una
  variante, se revierten también las anteriores. El carrito conserva las unidades
  agregadas después del checkout.
- Si llega dinero y la compra ya no puede completarse, por ejemplo por falta de
  stock o por llegar después de cancelar el intento, se registra un **reembolso
  pendiente**. No se presenta como compra exitosa ni se afirma que ya se devolvió
  dinero. La confirmación del reintegro es otra operación, con referencia propia.
  Stripe test usa una misma clave de reintegro en los reintentos; el simulador
  permite al administrador probar la confirmación sin mover fondos.
- Se conserva la consulta del historial y la compatibilidad de los anticipos de
  reservas anteriores. Su webhook global queda limitado a las operaciones
  heredadas de prueba; las compras nuevas requieren el webhook de su empresa.
- Se corrigió además una omisión del carrito: variantes con talla o color
  opcionales ya no desaparecen del cálculo del total.

Este bloque prepara CU16 y la base técnica de avisos y reintegros. **No completa
CU17–CU20** ni cambia todavía precios por mayor, promociones, políticas,
rutas, cambios de talla o devoluciones comerciales completas.

### Notificaciones y Flutter

- Bandeja propia en web y Flutter, con lectura y consulta de la orden. No depende
  de que llegue un push y sólo muestra la cuenta y empresa autenticadas.
- Registro privado de instalaciones vinculado a la sesión. Cambiar de cuenta,
  retirar el dispositivo, cerrar la sesión o revocar el acceso impide reutilizar
  su registro para enviar información de la cuenta anterior.
- Cola de salida transaccional y trabajador FCM HTTP v1 con reintentos limitados.
  Sin credenciales conserva los pendientes. Registra aceptación del proveedor,
  que **no equivale a entrega en el teléfono**. El aviso del sistema es genérico;
  los detalles se consultan dentro de la aplicación autenticada.
- Flutter incluye Firebase Core/Messaging y activación voluntaria de avisos.
  Inicia sin Firebase configurado y explica esa situación sin bloquear la bandeja.
  El push de este bloque se prepara para Android/iOS; Flutter web usa la bandeja.
- Se retiró el contador local de 15 minutos del QR: no correspondía a un
  vencimiento confirmado por el servidor. El modal web reutiliza el componente
  accesible del proyecto, con foco, Escape y desplazamiento en pantallas pequeñas.

### Configuración local y externa pendiente

La base local tiene `STYLEAR_PAGOS_PRUEBA=1` en el `.env` ignorado por Git. Cada
empresa mantiene sus medios deshabilitados hasta que su administrador los
habilite en **Pagos de prueba**. Para probar el recorrido local no se necesita
una cuenta bancaria ni credenciales Firebase.

Variables opcionales del servidor, sustituyendo `<id>` por el ID real de empresa:

```text
STYLEAR_PAGOS_<id>_STRIPE_SECRET_KEY=sk_test_...
STYLEAR_PAGOS_<id>_STRIPE_WEBHOOK_SECRET=whsec_...
STYLEAR_PAGOS_<id>_EVENTOS_PRUEBA_SECRET=<secreto aleatorio de al menos 32 caracteres>
STYLEAR_FIREBASE_PROJECT_ID=<proyecto>
STYLEAR_FIREBASE_CREDENTIALS=<ruta privada al JSON de cuenta de servicio>
```

El webhook Stripe de compras nuevas es
`POST /api/v1/pagos-empresa/stripe/webhook/<id>`. El endpoint
`POST /api/v1/pagos-empresa/eventos-prueba/<id>` es exclusivamente un contrato
interno de simulación, con HMAC SHA256 sobre `timestamp.cuerpo`, cabeceras
`X-Stylear-Timestamp` y `X-Stylear-Signature`, y antigüedad máxima de cinco minutos.
**No representa una API bancaria BCP.**

Nunca guardar secretos, JSON de servicio o tokens de dispositivos en Git. Para
FCM real se debe aportar el proyecto y una cuenta de servicio autorizada para
Firebase Messaging. Ejecutar el trabajador desde el backend:

```powershell
.\.venv\Scripts\python.exe -m app.modules.ventas_inventario.services.push_worker
```

El trabajador se ejecuta bajo demanda en este bloque; no se instaló un servicio
ni un proceso periódico. En Flutter habilitar Firebase sólo después de configurar
el proyecto y sus aplicaciones nativas, usando estas definiciones:

```text
FIREBASE_ENABLED=true
FIREBASE_API_KEY=...
FIREBASE_APP_ID=...
FIREBASE_MESSAGING_SENDER_ID=...
FIREBASE_PROJECT_ID=...
FIREBASE_IOS_BUNDLE_ID=...
```

Se pasan con `--dart-define=NOMBRE=valor` a Flutter. Android/iOS deben corresponder
al proyecto registrado; iOS requiere además la configuración APNs y capacidades
push correspondientes. No se aportaron credenciales externas ni se verificó
entrega real en teléfono. Las pruebas de transporte usan proveedores simulados.

### Migración y preservación de datos

- Nueva versión `2026_10_30_cu16_bloque1`, archivo
  `database/migracion_cu16_bloque1.sql`: configuración por empresa, claves de
  operación, eventos, reintegros, bandeja, dispositivos y cola push.
- Aplicada en StyleAR local con respaldo previo
  `.private/antes_cu16_bloque1_20261030_141204.dump`.
- También se aplicaron tres migraciones anteriores pendientes en esta base:
  `cu09_unicode_01`, `cu11_cu15_01` y `registro_empresa_01`.
- Se compararon pagos, ventas, existencias y movimientos antes y después:
  conservados. El inicializador se ejecutó dos veces para comprobar repetición
  segura. Se verificó el arranque de la API con la base local actualizada.
- No se cambiaron contraseñas administrativas ni se habilitaron cobros reales.

### Validaciones del bloque

- PostgreSQL/API: **53 pruebas aprobadas**, incluyendo 17 de este bloque,
  regresiones CU11–CU15 y aislamiento multitenant. Incluyen firma inválida,
  eventos repetidos, empresas distintas, importe incorrecto, concurrencia,
  stock insuficiente, reintegros, sesiones y envío FCM simulado.
- Flutter: **36 pruebas aprobadas**, análisis sin incidencias y compilación web
  correcta. Las cuatro pruebas nuevas cubren reintentos con la misma clave,
  separación por empresa, retorno Stripe sin aprobación automática y bandeja
  con lectura, error/reintento y Firebase pendiente.
- Angular: compilación de producción correcta. Conserva avisos existentes de
  dependencias CommonJS (`leaflet`, `qrcode`). La descarga de Google Fonts falló
  temporalmente durante una compilación y pasó al reintentar.
- Edge/Playwright y AXE: recorrido de configuración, QR simulado, estados de
  pago, bandeja, lectura y separación entre empresas; contrastes corregidos.
  Los datos de las pruebas viven exclusivamente en bases locales desechables.

### Recorrido manual para probar

1. Iniciar backend y frontend con los comandos del principio del documento.
   En Flutter ejecutar `flutter pub get` tras incorporar las dependencias y luego
   `flutter run -d chrome` para web, o seleccionar el dispositivo Android/iOS.
2. Ingresar como administrador comercial y abrir **Pagos de prueba**. Habilitar
   Stripe test y/o QR simulado y guardar. No introducir credenciales en esa pantalla.
3. Como cliente de esa misma empresa, agregar prendas con stock y abrir carrito.
   Iniciar QR de prueba y consultar el estado. Simular aprobación; revisar la
   compra y la nueva notificación. Reconsultar no debe duplicar el descuento.
4. Para probar un reintegro, crear un checkout y agotar su stock mediante otra
   operación antes de confirmar. Al recibir la confirmación se mostrará
   **Reembolso pendiente**. El administrador podrá simular su confirmación y el
   cliente verá **Reembolsado**. Estas pruebas no mueven dinero real.
5. En Flutter abrir Perfil → Notificaciones. La bandeja funciona sin Firebase;
   activar avisos explica qué falta mientras no exista configuración externa.

### Reglas reservadas para el siguiente bloque

Compra unitaria con cantidades libres, y compra por mayor en paquetes fijos por
modelo: cuarta de 3, media docena de 6 y docena de 12. Cuarta exige al menos dos
tallas y dos colores; media exige tres de cada uno; docena exige todas las tallas
definidas para ese producto. Un producto con una sola talla no habilita mayorista.
Sin variedad o existencias suficientes se mantiene sólo la compra unitaria,
sin excepciones por escasez. Se podrán combinar paquetes y unidades normales
como conceptos separados. Los precios/descuentos deberán configurarse por empresa.
No se implementaron aún esas reglas en este bloque.

Resultado final de navegador: **2 pruebas Edge/Playwright aprobadas**, con AXE
sin infracciones en configuración, QR, pago pendiente/aprobado, notificaciones
y reintegros pendientes/confirmados. Al cerrar se detuvieron las instancias de
prueba y se eliminaron las tres bases CU16 desechables y sus archivos temporales
de conexión. No quedan backend ni frontend levantados por esta implementación.
No se realizaron commits, push ni despliegue remoto.

## CU16–CU20 · Bloque 2: compra unitaria y paquetes mayoristas

Fecha: 30/10/2026. Autor: Angeles Rosales Colque.

### Aclaración incorporada del usuario

Los descuentos son **porcentajes independientes por producto**, editables para
cuarta, media docena y docena. No se fijaron porcentajes arbitrarios ni se copiaron
los de un modelo a otro. Un paquete sin porcentaje configurado permanece
inhabilitado. La configuración inicial no cambia los precios unitarios existentes.

### Comportamiento terminado en este bloque

- Administración web: Productos → **Descuentos mayoristas**. El administrador de
  la empresa puede configurar cada porcentaje (mayor que 0 y menor que 100,
  hasta dos decimales), habilitar el paquete o deshabilitarlo. Un control de versión
  impide sobrescribir cambios de otro administrador sin actualizar la pantalla.
- Compra unitaria: cantidades libres, de la misma talla/color o de combinaciones
  distintas, siempre sujetas al stock. La cantidad por sí sola nunca convierte
  esa línea en mayorista. El límite de dos unidades de la reserva gratuita ya
  no deshabilita los botones de pago de una compra directa.
- Compra por mayor en web y Flutter: apartado propio en el detalle del producto,
  con elección de sucursal y cantidades por variante para **un paquete fijo**.
  Se pueden agregar varios paquetes y después unidades normales.
- Cuarta: exactamente **3 prendas**, al menos **2 tallas y 2 colores distintos**.
  Media docena: exactamente **6 prendas**, al menos **3 tallas y 3 colores**.
  Docena: exactamente **12 prendas**, al menos una de **cada talla definida en
  las variantes activas del producto**. No agrega una regla de colores para docena.
- Un modelo con una sola talla no admite paquetes mayoristas. Las tallas definidas
  sin existencias siguen siendo necesarias para la docena; no se rebaja la regla
  por falta de stock. Si tiene más de doce tallas, no cabe una docena válida.
- Sin porcentaje, variedad, precio vigente o stock suficiente se explica el motivo
  y se inhabilita la opción. La API vuelve a validar la composición; alterar el
  cliente o seleccionar prendas de otra empresa/modelo no evita estas reglas.
- El porcentaje se calcula sobre el **precio unitario vigente de cada variante**,
  con redondeo monetario a dos decimales. No se acumula con la promoción unitaria.
  Ejemplo: precio vigente Bs 50, cuarta 10% → Bs 45 por prenda en ese paquete.
  Dos unidades normales siguen con su propio precio/promoción, como otra línea.
- El stock requerido suma unidades y paquetes. No se modifica la cantidad de una
  línea del paquete desde el carrito: se retira el paquete completo y se arma
  otro. Las unidades normales mantienen sus controles de cantidad.
- Los paquetes tienen identificación propia e idempotencia para reintentos.
  La venta guarda el tipo de compra, grupo de origen, porcentaje y precio neto.
  El historial y la nota de venta conservan la diferencia entre unidad y paquete.
- Antes de generar el pago se recalculan el precio y la disponibilidad. Si cambia
  el total mostrado, el cliente debe revisar el nuevo resumen. Una orden ya creada
  conserva su instantánea aunque después se edite el porcentaje del producto.
- La confirmación de pago descuenta sólo las líneas originales del carrito;
  conserva unidades o paquetes agregados después. No repite venta ni movimientos
  al recibir otra vez la misma confirmación. Sigue usando los pagos de prueba
  seguros del bloque 1 y su tratamiento de falta de stock/reintegro pendiente.
- Los paquetes de este bloque son para **compra directa**, sin incorporarlos a la
  reserva gratuita. La reserva existente mantiene su límite de dos por variante.

### Migración y datos locales

Versión `2026_10_30_cu17_mayorista`, archivo
`database/migracion_cu17_mayorista.sql`. Agrega configuración por modelo,
agrupación de paquetes en carrito y metadatos comerciales en el detalle de venta.
Las líneas anteriores conservan el concepto `UNIDAD` y su precio histórico.

Aplicada a StyleAR local después de crear el respaldo:
`.private/antes_cu17_mayorista_20261030_151441.dump`.
Se ejecutó el inicializador dos veces y se compararon pagos, ventas, existencias
y movimientos antes/después: conservados. La API inicia con el esquema actualizado.
No se asignaron porcentajes de prueba a productos de la base real local.

### Validaciones

- **69 pruebas de integración aprobadas** en base nueva desechable: las primeras
  16 de mayorista y las 53 de pagos, reservas CU11–CU15 y multitenant.
- Después se aprobaron **4 comprobaciones focalizadas**: tres casos nuevos
  (colores/tallas insuficientes, porcentajes por producto sin acumular promociones,
  cambio de total y rechazo de reserva mayorista) y la repetición del pago mixto
  con sus metadatos de historial. En total, **72 casos distintos verificados**,
  con 19 pruebas propias de este bloque.
- Flutter: **39 pruebas aprobadas**, incluidas tres nuevas de modelos de carrito,
  reintento del paquete con la misma clave, redondeo monetario y selector de
  composición. Pruebas HTTP simuladas; no sustituyen verificación en teléfono.
- Angular: compilación de producción correcta.
- Edge/Playwright: recorrido de administrador configurando el porcentaje por
  producto; cliente armando una cuarta, combinándola con dos unidades, pagando y
  consultando el comprobante con conceptos separados. AXE sin infracciones en
  las pantallas verificadas. Se corrigió el contraste del encabezado del detalle.
- Todos los datos de estas pruebas pertenecen a bases desechables. No se usaron
  credenciales de banco ni se movió dinero real.

### Recorrido manual

1. Iniciar backend, web y/o Flutter con los comandos registrados en este documento.
2. Como administrador: Productos → Descuentos mayoristas. Configurar y guardar
   los porcentajes deseados para ese producto, habilitando cada opción.
3. Como cliente: abrir el producto. En web usar **Comprar por mayor**, debajo de
   la compra unitaria; en Flutter tocar **Comprar por mayor · paquetes**.
4. Elegir sucursal, paquete y distribución. Completar exactamente la cantidad
   del paquete y cumplir tallas/colores. Agregarlo y, si se desea, añadir unidades
   desde el recorrido unitario habitual.
5. En carrito comprobar que unidades y paquete tienen conceptos/precios distintos.
   Eliminar una fila mayorista retira todo ese paquete; no altera las unidades.
6. Pagar con el medio de prueba habilitado por el administrador y revisar el
   detalle del pago. No usar el QR simulado para transferencias bancarias.

### Pendientes obligatorios del cierre final (acuerdo del usuario)

Las conexiones externas se posponen **hasta el cierre**, no se eliminan del alcance.
No se declarará terminado el conjunto CU16–CU20 mientras falte resolver y verificar:

- [ ] BCP: obtener el acceso y documentación oficial, implementar el contrato
  real de cobro QR y conciliación por empresa, validar firmas y verificar un
  cobro/reintegro autorizado. El endpoint 503 actual y el QR simulado no cuentan
  como integración bancaria terminada.
- [ ] Stripe: aportar claves de prueba por empresa y configurar/verificar sus
  webhooks con Stripe, incluyendo confirmación, importe/moneda, repetición de
  eventos y reintegro. Los mocks actuales no sustituyen esa verificación externa.
- [ ] Firebase: configurar proyecto y aplicaciones Android/iOS, credenciales del
  servidor y APNs para iOS; verificar recepción en dispositivos y cierre/cambio
  de sesión. La bandeja funciona ahora, pero no se afirma entrega push real.
- [ ] Completar y probar los demás bloques de las fichas CU16–CU20, incluidos
  políticas, entrega/rutas y los flujos completos de cambios y devoluciones,
  según corresponda a cada ficha.
- [ ] Ejecutar el recorrido integrado final y actualizar aquí la evidencia y
  cualquier requisito externo que necesite datos o acceso del usuario.

Este registro distingue funcionalidad local terminada, conexiones verificadas y
pendientes concretos. Las credenciales externas siguen fuera del repositorio.

Cierre del bloque 2: análisis Flutter sin incidencias y compilación web Flutter
correcta. Se detuvieron los servidores temporales y se eliminaron las tres bases
CU17 desechables y sus archivos de conexión; no quedaron procesos del proyecto
levantados por estas pruebas. Se conserva el respaldo local. Sin commits, push
ni despliegue remoto.

## CU16–CU20 · Bloque 3: CU18 — entregas a domicilio

Fecha: 31/10/2026. Autor: Angeles Rosales Colque.

### Funcionalidad implementada

- Cotización autenticada vinculada con cliente, empresa, sucursal y destino.
  Se puede seleccionar una dirección guardada o escribir otra y confirmar su
  ubicación. Elegir una dirección de otra cuenta es rechazado por la API.
- La cotización guarda distancia, minutos, costo, trazado ORS y ubicación de
  origen. Tiene **15 minutos de vigencia para iniciar el pago**. Web y Flutter
  solicitan aceptar el resumen antes de continuar.
- Cambiar sucursal, dirección, referencia o coordenadas invalida la cotización.
  También se comprueba si cambió la ubicación de la sucursal antes del checkout.
  El costo enviado por el cliente no es una fuente de autoridad: se usa la
  cotización guardada. El precio aceptado queda fijo en la orden ya creada;
  reintentar esa misma orden no recalcula ORS ni duplica compras.
- Se conserva la tarifa previa: hasta 3 km Bs 8; hasta 6 km Bs 12; hasta 10 km
  Bs 18. Fuera de sus tramos no se ofrece un envío gratuito. El límite adicional
  `DELIVERY_MAX_KM`, si existe, puede restringir esa cobertura.
- Se corrigió el formato de respuesta ORS. El POST usa el endpoint `/geojson`,
  correspondiente a `features` y geometría `LineString`; se verifican sus datos.
  Se retiró el cálculo Haversine usado silenciosamente como reemplazo ante
  fallos. Sin clave, sin ruta o con respuesta inválida se comunica el problema;
  no se inventan distancia, tiempo ni costo.
- La entrega operativa se crea **en la misma transacción que confirma la compra
  pagada y descuenta stock**. Una compra pendiente/rechazada o un pago que exige
  reintegro por falta de stock no genera un despacho. Repetir el callback no
  crea otra entrega, aviso ni movimiento.
- El envío se paga junto con la compra mediante Stripe o QR; no se ofrece efectivo
  contra entrega. El antiguo endpoint `delivery/solicitar` sólo reconoce una
  entrega ya existente con el mismo destino: no agrega cargos a ventas pagadas,
  no cambia el total ni crea una entrega sin pago.
- Seguimiento con control de versión y transiciones:
  `PENDIENTE → EN_PREPARACION → EN_CAMINO → ENTREGADO`.
  La cancelación se permite antes de salir a reparto y exige motivo. No se
  habilitan retrocesos ni sobrescritura de cambios concurrentes.
- El administrador puede gestionar las entregas de su empresa; el encargado
  sólo las de su sucursal activa. El cajero mantiene consulta de su sucursal,
  sin controles de gestión de CU18. El cliente consulta exclusivamente las suyas.
- Finalizar exige una **confirmación explícita de entrega física** y no admite
  una incidencia abierta. Se registra quién confirmó y la fecha efectiva.
- Las incidencias y sus resoluciones conservan motivo, fecha, actor y versión.
  Sus reintentos reconocibles no duplican el historial. Una cancelación abre una
  incidencia de coordinación; **cancelar la entrega no confirma un reembolso**.
  Si corresponde devolver dinero se continúa con CU20, todavía pendiente del
  bloque de devoluciones. Este bloque no inventa una devolución de fondos.
- Registro de notificación y cola push transaccional por cada cambio relevante;
  el envío FCM real conserva las dependencias externas del bloque 1. El cliente
  puede consultar el historial aunque no reciba push.
- Web muestra el trazado aceptado y el destino; Flutter dibuja la geometría de
  la ruta. Se retiraron las líneas rectas presentadas como rutas. Los registros
  anteriores sin geometría lo indican expresamente. No se presenta seguimiento
  GPS en tiempo real de un repartidor.
- Las pantallas retiran los datos anteriores al fallar una actualización o cambiar
  de sesión. Se descartaron cotizaciones en vuelo si el destino ya cambió y se
  corrigió una escritura de señales durante el renderizado del carrito Angular.
  Los marcadores del mapa tienen nombres accesibles.

Referencia técnica del formato ORS, consultada para esta reparación:
[Requests and Return Types — documentación oficial de OpenRouteService](https://giscience.github.io/openrouteservice/api-reference/endpoints/directions/requests-and-return-types).

### Migración local y preservación

Versión `2026_10_31_cu18_delivery`, archivo
`database/migracion_cu18_delivery.sql`. Agrega cotizaciones aceptadas, referencia
con la orden de pago y la entrega, historial de seguimiento, versión, incidencia
abierta y registro de recepción física.

Aplicada con respaldo previo:
`.private/antes_cu18_delivery_20261031_203810.dump`.
Se ejecutó el inicializador dos veces. Se conservaron pagos, ventas, existencias,
movimientos y datos de las entregas existentes. Las entregas anteriores pendientes
sin pago verificable se identifican como `PENDIENTE_PAGO` y no se despachan; no se
inventan pagos para habilitarlas. La API inicia correctamente con la base migrada.
No se alteraron contraseñas ni se habilitaron cobros reales.

### Validaciones del bloque

- **88 pruebas PostgreSQL/API aprobadas**, incluidas 16 de CU18 y regresiones
  de mayorista, pagos, reservas CU11–CU15 y aislamiento entre empresas.
- Cubren cotización vencida/ajena, cambios del destino y origen, importe falso,
  falta de stock, pago repetido, concurrencia de estados, permisos por sucursal,
  confirmación física, incidencias y continuidad de despachos pagados aunque
  se suspenda el plan comercial. Las respuestas ORS inválidas o ausentes no
  producen cotizaciones ficticias.
- Flutter: **44 pruebas aprobadas**. Las cinco nuevas comprueban ID de cotización,
  geometría, versión de incidencias, confirmación física, errores recuperables
  y retiro de datos del historial al cambiar de sesión. Análisis sin incidencias.
- Angular: compilación de producción correcta, con los avisos existentes de
  CommonJS para `leaflet` y `qrcode`.
- Edge/Playwright + AXE: recorrido completo con dirección guardada, aceptación
  del envío, pago QR simulado, consulta del cliente, gestión por encargado,
  incidencia/resolución y confirmación física. Otra empresa no ve la dirección.
  El recorrido aprobado pasó los controles de accesibilidad verificados.
- El navegador usó una base desechable y un proveedor ORS simulado exclusivamente
  en la fixture. Esto **no equivale a una consulta real a ORS ni a entrega física**.

### Recorrido manual

1. Iniciar los proyectos con los comandos del inicio de este documento.
2. Configurar la ubicación real de la sucursal y, para cotizar con ORS real,
   aportar `OPENROUTE_API_KEY` en el `.env` privado del backend.
3. Como cliente, agregar prendas y elegir **Delivery** en el carrito. Seleccionar
   una dirección guardada o escribir otra, revisar la ubicación y cotizar.
4. Revisar distancia, estimación y costo; aceptar la cotización. Pagar compra y
   envío con el medio habilitado. Mientras el pago siga pendiente no aparece
   una entrega operativa en Mis deliveries.
5. Con el pago confirmado, abrir **Mis deliveries**. Como encargado de la
   sucursal, abrir **Delivery**, avanzar los estados y registrar incidencias
   cuando corresponda. Resolverlas antes de finalizar.
6. Para finalizar, elegir `ENTREGADO` y marcar la confirmación de entrega física.
   El cliente ve el estado y el historial, y tiene el aviso en su bandeja.

### Estado de la conexión ORS y cierre pendiente

Se comprobó que la base de desarrollo **no tiene `OPENROUTE_API_KEY` configurada**.
Por ese motivo no se ejecutó una consulta real al proveedor. La cotización local
responderá que falta configurar el servicio; el retiro en sucursal sigue disponible.
No se activó ningún simulador en la aplicación normal ni se guardó una clave
sintética en el `.env` local.

Se añade al cierre obligatorio ya acordado:

- [ ] ORS: aportar la clave autorizada, verificar las coordenadas reales de cada
  sucursal y ejecutar una cotización real, incluyendo fallo de proveedor y
  destino sin cobertura. Las pruebas de la fixture no cierran esta verificación.

Siguen pendientes BCP, Stripe, Firebase y los flujos completos CU19–CU20 del
registro anterior. La siguiente implementación debe abordar las políticas por
empresa y los cambios/devoluciones; este bloque cierra el funcionamiento de
entregas probado con proveedores simulados, sin declarar cerrado el conjunto.

Cierre del bloque 3: Flutter compila para web y su análisis quedó sin incidencias.
Se detuvieron las instancias temporales y se eliminaron las tres bases CU18
utilizadas para las pruebas y sus archivos de conexión. No quedaron servidores
levantados por esta implementación. Se conserva el respaldo de StyleAR local.
No se hicieron commits, push ni despliegues remotos.

## Bloque 4 — Políticas y devoluciones con aceptación (31/10/2026)

Se implementó la política por empresa y el flujo de devolución CU20 en web y
mobile. La política de cambios CU19 queda preparada; el reemplazo de prendas,
reserva de la nueva variante y liquidación de diferencias corresponden al
siguiente bloque y **todavía no están implementados**.

### Comportamiento implementado

- El administrador configura plazos y condiciones en **Políticas de posventa**.
  Las políticas comienzan deshabilitadas y no se activan sin plazo y condiciones.
  Cada empresa mantiene sus valores y versión; una edición concurrente exige
  actualizar antes de guardar. No se impuso un plazo comercial arbitrario.
- El cliente consulta su política y solicita cantidades elegibles de compras
  completadas y pagadas. Se conserva una copia de la política aplicable al
  solicitar; deshabilitarla después no bloquea solicitudes existentes.
- Se conserva la clave de una solicitud cuando falla su respuesta para permitir
  reintentos. Las unidades comprometidas en inspección o reintegro no pueden
  solicitarse nuevamente. Se excluye el envío y se prorratea el importe pagado
  después de descuentos, con ajuste de centavos en la última devolución.
- AD y personal ES/CA autorizado revisan y reciben dentro de su empresa y
  sucursal. El servidor revalida el usuario, los roles y el empleado al escribir.
  Se corrigieron los permisos heredados del cajero para este flujo.
- La recepción distingue cantidades aceptadas, rechazadas y **no vendibles**.
  Estas últimas requieren describir su condición. La inspección no aumenta
  existencias: queda en `ESPERA_ACEPTACION` hasta que el cliente acepte el importe.
- La aceptación registra un comprobante estructurado con cantidades e importe,
  repone solo prendas vendibles una vez y pasa a `REEMBOLSO_PENDIENTE`.
  Comprobante comercial y confirmación del dinero son estados separados.
- El reintegro electrónico usa el medio original. No se permite registrar un
  pago QR/Stripe como entrega de efectivo u otro método. Para efectivo se exige
  aceptación previa y referencia del recibo de caja; repetirlo no registra otra
  entrega. Los simuladores solo confirman reintegros de pagos simulados cuando
  está habilitado el modo de prueba.
- Stripe usa credenciales propias de la empresa, referencia del pago original
  e idempotencia. Su conciliación valida empresa, moneda, importe y referencia;
  los nuevos reintegros se reciben en el webhook específico de la empresa.
  Esto se verificó con datos de prueba, **sin mover dinero real**.
- Se generan avisos en la bandeja y cola push de forma transaccional. El envío
  FCM real mantiene su dependencia externa pendiente.
- Flutter retira datos al cambiar de sesión y descarta respuestas anteriores.
  Se corrigieron contrastes, foco visible y el landmark duplicado en web.

### Migración y validación

Migración `2026_10_31_posventa_politicas`, archivo
`database/migracion_posventa_politicas.sql`, aplicada localmente con respaldo
`.private/antes_posventa_20261031_211202.dump`. Dos ejecuciones del inicializador
preservaron pagos, ventas, devoluciones, entregas, existencias y movimientos.
La API inicia correctamente con StyleAR local. No se cambiaron contraseñas.

- Regresión comercial: **96 pruebas API/PostgreSQL aprobadas** en base desechable
  (incluía las primeras ocho de posventa). Tras ampliar cobertura, **11 pruebas
  específicas de posventa aprobadas**, incluidas efectivo, cantidades en espera
  de aceptación y permisos del cajero por sucursal.
- Nueve regresiones de cambios remotos aprobadas; se adaptó la prueba del
  reintegro a su nuevo servicio conservando propagación de 404 y actor/empresa.
- Flutter: **47 pruebas aprobadas**, análisis sin incidencias. Las tres nuevas
  verifican aceptación con comprobante y dinero pendiente, clave tras error e
  inspección con unidades no vendibles.
- Angular: compilación de producción correcta; avisos CommonJS existentes.
- Edge/Playwright y AXE: recorrido completo aprobado desde configuración hasta
  reintegro QR simulado, incluyendo inspección no vendible y aceptación del cliente.

### Cómo probar

1. Iniciar los proyectos con los comandos del principio del documento.
2. Como AD, abrir **Políticas de posventa**, habilitar devoluciones y guardar el
   plazo y las condiciones reales de la empresa. Las políticas locales siguen
   deshabilitadas hasta que se configuren; los valores de prueba no se cargaron
   en StyleAR.
3. Como cliente, abrir **Mis devoluciones**, seleccionar una compra pagada y
   enviar motivo y cantidades.
4. Como personal autorizado de su sucursal, abrir **Devoluciones**, aprobar y
   registrar recepción e inspección. Marcar no vendibles cuando corresponda.
5. Como cliente, revisar el importe y aceptar. Consultar el comprobante.
6. Como personal, solicitar el reintegro original o registrar la entrega efectiva
   de efectivo con recibo si la compra original fue en efectivo.

### Pendientes que no se consideran cerrados

- **CU19**: selección y reserva de reemplazo, operación de cambio y aceptación
  de diferencia económica. Utilizará esta base de políticas y cantidades.
- **CU20 real**: conexión y validación de reintegros bancarios QR y Stripe por
  empresa. Un QR real sin integración responde que falta la conexión bancaria;
  no se convierte en un reintegro manual ficticio.
- Se mantienen como cierre obligatorio BCP, Stripe, Firebase y ORS. Faltan sus
  credenciales/configuración autorizadas y pruebas reales. No se declararon
  completados mediante los simuladores ni se alteró el `.env` para aparentarlo.

Se detuvieron las instancias temporales web/API y se eliminaron las bases
posventa desechables y sus archivos de conexión. Se conserva el respaldo local.
No se hicieron commits, push ni despliegues remotos.

Cierre de compilación mobile: **APK Android debug generado correctamente** en
`tr-mobile/build/app/outputs/flutter-apk/app-debug.apk`. No se instaló ni se probó
en un dispositivo físico. Se excluyó del control de versiones la caché local de
Kotlin creada al compilar. Permanecen los avisos de compatibilidad futura de
Kotlin/Firebase y Java existentes en la herramienta, sin impedir la compilación.

## Bloque 5 — CU19: cambios de prendas (31/10/2026)

Se implementó CU19 en web y mobile tomando como referencia la ficha de cambios
acordada en «Estructura informe con ICONIX». El cliente solicita un cambio,
ES/CA (o AD) inspecciona en su sucursal y el cliente elige y acepta el reemplazo.

### Flujo y reglas implementadas

- Cada solicitud corresponde a una línea de compra y su cantidad. Para cambiar
  líneas distintas se generan solicitudes independientes. Se comprueban propiedad,
  pago de la compra, plazo y política de cambios de la empresa.
- Cambios y devoluciones comparten el cálculo de unidades comprometidas: una
  unidad solicitada, aceptada o ya cambiada no puede tramitarse dos veces.
  La solicitud conserva su clave al reintentar una respuesta incierta.
- La tienda confirma la recepción física, registra la condición y distingue las
  unidades no vendibles. Rechazar exige una descripción; todavía no repone stock.
- El crédito usa el importe efectivamente pagado por las prendas originales,
  después de descuentos y sin envío. Se conservan sus condiciones originales.
  Los centavos se ajustan al consumir las últimas unidades elegibles.
- Se ofrecen variantes de la misma sucursal, incluidas tallas, colores y modelos
  distintos, con suficientes existencias libres. El reemplazo se cotiza por
  unidad al precio y promoción vigentes; no se crea un paquete mayorista nuevo.
- La cotización dura 15 minutos. Antes de aceptarla se verifican otra vez precio,
  stock y versión. El cliente acepta expresamente el reemplazo y la diferencia.
  Entonces se reserva la cantidad; todavía no se registra su salida definitiva.
- Diferencia cero: el cambio queda listo para entrega, sin crear un cobro.
- Diferencia positiva: se crea una orden específica de diferencia por Stripe o
  QR, vinculada con el cambio. La confirmación validada del pago habilita la
  entrega. Los reintentos concurrentes comparten la misma orden y sesión.
- Diferencia negativa: se reintegra **solo el excedente**, por el medio original
  y con la aceptación del cliente. Si la compra fue en efectivo se exige la
  referencia de su entrega en caja. Un pago electrónico no se registra como
  efectivo. La entrega del reemplazo espera la confirmación del reintegro.
- El cliente puede desistir antes de liquidar. Se libera la reserva cuando es
  seguro; un pago tardío de un intento cerrado pasa al reintegro por operación
  incumplida. No se libera una operación conectada con resultado incierto sin
  conciliarla con su proveedor.
- Si no se desea o no hay reemplazo disponible, el cliente puede continuar por
  devolución después de la inspección. La solicitud existente pasa a CU20, sin
  duplicar cantidades; exige aceptar su importe antes de reponer y reintegrar.
- ES/CA/AD confirma la entrega física antes de completar. En una transacción se
  libera la reserva, registra la salida del reemplazo y repone únicamente las
  prendas originales vendibles. Se emite el comprobante vinculado con la venta
  original. Repetir la entrega no repite movimientos ni comprobante.
- Se guarda el estado económico separado de la inspección y entrega. Un callback
  de reintegro repetido o tardío no degrada un cambio ya completado.
- El cliente consulta **Mis cambios** en la web y **Cambios de prendas** en su
  perfil mobile. El personal accede a la gestión de su sucursal. Las versiones,
  roles y sucursal se verifican en el servidor al ejecutar las acciones.
- Se generan avisos en la bandeja y en la cola push. La entrega FCM real sigue
  pendiente de la conexión externa acordada.

Se corrigió también una carrera en la pantalla de políticas: se bloquea el
formulario hasta terminar de cargar, para que la respuesta inicial no sobrescriba
una edición. La vista de cambios gestiona el foco en su detalle y Flutter retira
los datos al cambiar la sesión.

### Migración y preservación local

Migración `2026_10_31_cu19_cambios`, archivo
`database/migracion_cu19_cambios.sql`. Añade el registro de cambio, sus versiones,
reserva, cotización, comprobante y vínculo con la orden de diferencia. La base de
solicitudes comparte la elegibilidad con CU20, manteniendo separados sus flujos.

Aplicada localmente con respaldo previo:
`.private/antes_cu19_cambios_20261031_214745.dump`.
Dos ejecuciones del inicializador conservaron ventas, pagos, devoluciones,
existencias, movimientos y entregas anteriores. La API inicia con StyleAR migrado.
No se alteraron contraseñas ni se cargaron configuraciones comerciales de prueba
en la base local.

### Validaciones del bloque

- Las primeras nueve pruebas API de CU19 aprobaron precio igual, mayor y menor,
  reserva/entrega, unidades no vendibles, reintentos concurrentes, conversión a
  devolución, precio/stock/cotización inválidos y pagos tardíos tras cancelar.
- Se ampliaron los casos con tres cambios parciales de una compra con descuento:
  sus créditos suman exactamente lo pagado y el excedente total coincide con la
  diferencia, incluidos los centavos. También se verifican límites por sucursal,
  el callback del excedente y datos vacíos rechazados sin efectos comerciales.
- Flutter: **51 pruebas aprobadas**, análisis sin incidencias y APK Android debug
  compilado en `tr-mobile/build/app/outputs/flutter-apk/app-debug.apk`. No se
  instaló ni se probó en un dispositivo físico.
- Angular: compilación de producción correcta; permanecen los avisos CommonJS
  existentes de `leaflet` y `qrcode`.
- Edge/Playwright y AXE: recorrido completo aprobado con política configurada,
  solicitud del cliente, inspección de cajero, prenda no vendible, selección y
  aceptación del reemplazo, pago QR simulado de diferencia, entrega y comprobante.
- Nueve regresiones de integración remota aprobadas. El inicio de la API con
  StyleAR local migrado fue verificado sin levantar un servidor permanente.

### Recorrido manual

1. Iniciar los proyectos con los comandos del principio del documento.
2. Como AD, configurar **Políticas de posventa → Cambios**: plazo y condiciones.
3. Como cliente, abrir **Mis cambios**, elegir la línea y cantidad de una compra
   elegible e indicar el motivo.
4. Como personal autorizado de la sucursal, abrir **Cambios de prendas**, recibir
   e inspeccionar la prenda, registrar su condición y aprobar o rechazar.
5. Como cliente, consultar reemplazos, seleccionar la variante, cotizar y aceptar
   la diferencia. Se puede elegir otra variante o desistir antes de liquidar.
6. Si corresponde pagar, completar la orden de diferencia. En modo simulado se
   identifica claramente que la confirmación de prueba no mueve dinero real.
7. Si corresponde un excedente, el personal solicita el reintegro original, o
   registra el recibo si el pago original fue en efectivo. Esperar confirmación.
8. Como personal, confirmar la entrega física y completar. El cliente consulta
   su comprobante. Si se elige devolución, continuar en **Mis devoluciones**.

### Cierre externo obligatorio todavía pendiente

Este bloque no habilitó cobros ni reintegros bancarios reales. Se mantienen como
pendientes BCP, Stripe por empresa, Firebase y ORS con credenciales/configuración
autorizadas y pruebas reales. Las verificaciones de CU19 con simuladores y mocks
no cierran estas conexiones. No se presenta un QR sin conexión bancaria como
un pago real confirmado ni un reintegro electrónico como entrega manual de caja.

Cierre de validación del bloque 5:

- **111 pruebas API/PostgreSQL de regresión comercial aprobadas** en una base
  desechable, incluidas las primeras 12 de CU19 y los bloques anteriores.
- Dos casos adicionales aprobados: validaciones de textos vacíos sin efectos
  y desistimiento de una cotización de menor precio antes de aceptarla.
- Se amplió y volvió a aprobar la prueba del callback para comprobar que un
  reintegro tardío no degrada un cambio ya completado.
- Las instancias temporales web/API quedaron detenidas. Se eliminaron las bases
  CU19 de prueba y sus archivos de conexión; se conservó el respaldo de StyleAR.
- No se hicieron commits, push ni despliegues remotos. El siguiente cierre es
  el de conexiones externas reales ya enumeradas, que sigue pendiente.

## Cierre externo — configuración guiada iniciada (31/10/2026)

La usuaria confirmó que necesita guía para crear/configurar Firebase, ORS y
Stripe, y que todavía no solicitó acceso a la API QR del BCP. El cierre externo
permanece abierto. No se crearon cuentas ni se enviaron solicitudes al banco.

Diagnóstico local sin exponer valores:

- No había clave ORS. Se añadió `OPENROUTE_API_KEY=` vacío al `.env` privado para
  completarlo localmente. No se ejecutó una consulta real de rutas.
- Existen variables Stripe globales heredadas. Esto no demuestra que estén
  operativas ni autoriza asociarlas a todas las empresas; la integración nueva
  requiere identificar la cuenta y configurar credenciales por empresa.
- No se encontró configuración Firebase del servidor ni archivos de registro
  Android en el proyecto. No se verificó entrega FCM en un dispositivo.
- `.env.example` incluye los nombres de variables de estas integraciones, sin
  credenciales. Mobile tiene `firebase.defines.example.json`, deshabilitado y
  vacío; los valores locales se guardarán en `firebase.defines.local.json`.
  La cuenta de servicio privada se guarda solo en el backend, nunca en el APK.

### Paso 1: OpenRouteService

1. Abrir https://openrouteservice.org/log-in/ y crear o iniciar una cuenta desde
   su enlace oficial. Completar la verificación de correo solicitada.
2. En su panel de desarrollador, crear una API key para StyleAR.
3. Guardar su valor en `tr-backend/.env`, en la variable ya preparada
   `OPENROUTE_API_KEY`. No compartirla en el chat ni subir `.env` al repositorio.
4. Avisar una vez guardada. Se verificará una ruta real con ubicaciones de
   sucursal/destino y después la cotización desde el carrito. La existencia de
   la variable por sí sola no se registrará como conexión verificada.

Referencia oficial: [Acceso y obtención de API key de ORS](https://openrouteservice.org/log-in/).

### Paso 2: Firebase — siguiente configuración guiada

Crear un proyecto propio en https://console.firebase.google.com/ y registrar la
aplicación Android con su identificador actual `com.example.mobile_tr`.
Después se configurarán los datos públicos de la aplicación y su integración
nativa, y las credenciales privadas de envío únicamente en el servidor. El cierre
requiere permiso de notificaciones, registro de una instalación y recepción de
un aviso en un teléfono o emulador compatible; que FCM acepte una petición no
prueba por sí solo que el teléfono recibió el aviso.

Referencias oficiales: [Configuración Flutter](https://firebase.google.com/docs/flutter/setup),
[Cloud Messaging en Flutter](https://firebase.google.com/docs/cloud-messaging/flutter/get-started).

### BCP — solicitud pendiente

Solicitar al banco acceso de pruebas para generación y consulta de QR, la forma
oficial de confirmar pagos, credenciales y URL de sandbox, firma/autenticación,
reglas de reintentos y conciliación, habilitación por comercio/cuenta receptora,
y el procedimiento para reintegrar fondos. La página pública no basta para
implementar un webhook o una API de reintegros que no se ha documentado.

Referencia oficial: [BCP Bolivia — API Pagos QR SIMPLE](https://www.bcp.com.bo/Desarrollo/ApiPagosQR).

### Stripe — disponibilidad y titularidad antes de activar

Bolivia no figura en la lista oficial de países de alta directa para Stripe
Payments. Esto es distinto de poder presentar importes en BOB, moneda incluida
entre las admitidas para ciertos pagos. No se debe registrar un país ficticio
ni confundir recibir pagos mediante otra plataforma con disponer de una cuenta
propia de comercio. Antes de conectar se verificará la cuenta habilitada y su
modo de prueba, la titularidad por empresa y sus webhooks. Las variables globales
existentes no se copiarán automáticamente a los comercios.

Referencias oficiales: [Disponibilidad de Stripe](https://stripe.com/global),
[Monedas admitidas](https://docs.stripe.com/currencies).

### ORS: conexión real verificada (31/10/2026)

La usuaria guardó la clave localmente. Se comprobó su presencia sin mostrarla y
se ejecutó `_calcular_ruta` contra el endpoint real de OpenRouteService, sin mocks.
Desde la ubicación configurada de la sucursal se consultó un punto técnico cercano
(sin usar direcciones de clientes): resultado **2,15 km**, **6 minutos estimados**
y **36 puntos de geometría**. La tarifa local produjo **Bs 8,00** y la distancia
está dentro del máximo configurado. El costo lo calcula StyleAR; no es una tarifa
cobrada o determinada por ORS.

No se crearon compras, cotizaciones persistentes, pagos ni entregas. No se mostró
ni se copió la clave a archivos versionados. No se dejaron servidores corriendo.

Se considera verificada la autenticación y consulta real de rutas. Todavía se
requiere probar el recorrido desde el carrito y confirmar que las coordenadas
configuradas representan los locales físicos: actualmente las dos sucursales de
StyleAR tienen las mismas coordenadas. No se modificaron estas ubicaciones.

Siguiente paso guiado: crear el proyecto Firebase, registrar Android con
`com.example.mobile_tr` y guardar su archivo de configuración público en
`tr-mobile/android/app/google-services.json`. Después se completará la integración
nativa y el envío desde el servidor, sin incluir credenciales privadas en la app.

### Firebase Android: archivo recibido y configuración nativa (31/10/2026)

Se recibió y validó el JSON local para el paquete `com.example.mobile_tr`.
Se configuró el plugin oficial Google Services 4.5.0, aplicado cuando existe
`android/app/google-services.json`, y se generó `firebase.defines.local.json`
con Firebase habilitado y los datos públicos del registro Android. Ambos archivos
locales se comprobaron excluidos de Git. No contienen una cuenta de servicio
privada del backend.

El `.env` privado del backend identifica el proyecto Firebase. La ruta de cuenta
de servicio sigue vacía porque el archivo todavía no fue proporcionado. Se
comprobó que el backend informa `push_configurado: false` y mantiene disponible
la bandeja. No se presenta esta preparación como un envío FCM verificado.

Verificaciones: 51 pruebas Flutter aprobadas y análisis estático sin incidencias.
Se corrigió una advertencia de formato de una prueba de CU19. No se detectaron
telefonos ni emuladores Android conectados; no se instaló el APK ni se verificó
la recepción física de avisos.

Siguiente paso de la usuaria:

1. Firebase Console → Configuración del proyecto → Cuentas de servicio.
2. En Firebase Admin SDK, generar una nueva clave privada y descargar su JSON.
3. Guardarlo solo en
   `tr-backend/.private/firebase-service-account.json`.
4. Confirmar que Cloud Messaging API (V1) está habilitada en el proyecto.
5. Avisar cuando esté guardado; se validará que pertenece al mismo proyecto y se
   configurará la ruta privada del servidor. Después se probará el registro y
   recepción en un teléfono/emulador con Google Play Services.

La cuenta de servicio no se guarda en mobile ni se copia al APK. No se solicita
pegar su contenido en el chat.

Referencias oficiales consultadas:
[Configuración Android y plugin Google Services](https://firebase.google.com/docs/android/setup),
[Autorización de envío FCM HTTP v1](https://firebase.google.com/docs/cloud-messaging/send/v1-api).

Cierre de la preparación Android: APK debug compilado correctamente con Firebase
habilitado. Se verificaron los recursos nativos generados contra el registro
Android y la presencia de `POST_NOTIFICATIONS` en el manifiesto combinado.

Para mantener esta configuración al ejecutar o recompilar desde `tr-mobile`:

```powershell
$env:PUB_CACHE='C:\Users\Anghy\AppData\Local\Pub\Cache'
C:\src\flutter\bin\flutter.bat run --dart-define-from-file=firebase.defines.local.json
# Para generar el APK:
C:\src\flutter\bin\flutter.bat build apk --debug --dart-define-from-file=firebase.defines.local.json
```

La compilación sin estas definiciones mantiene `FIREBASE_ENABLED=false` por
omisión. El APK generado en este paso sí usa las definiciones locales habilitadas.
No se envió ninguna notificación ni se dio por verificada su recepción. El backend
sigue esperando la cuenta de servicio privada del mismo proyecto.

### Firebase servidor: autorización real verificada (31/10/2026)

Se validó el archivo `.private/firebase-service-account.json`: es una cuenta de
servicio válida, su clave se puede cargar y el proyecto coincide con Android.
El `.env` privado ya apunta a este archivo y proyecto. La credencial continúa
excluida de Git y no se copió a mobile ni al APK.

Se verificaron contra Google, sin mocks:

- Obtención correcta de autorización OAuth con el alcance de Firebase Messaging.
- Petición FCM HTTP v1 aceptada en modo `validate_only=true`. Este modo valida
  sin entregar el mensaje: no se envió una notificación a usuarios ni se marcó
  ningún registro de la cola como enviado.

Referencia oficial de esta prueba:
[FCM messages.send — validate_only](https://firebase.google.com/docs/reference/fcm/rest/v1/projects.messages/send).

La usuaria eligió probar con un teléfono Android. Todavía no se detectó uno
conectado/autorizado; la recepción sigue pendiente de la prueba física.

Se preparó un APK debug con Firebase habilitado y `API_URL=http://127.0.0.1:8000`
en las definiciones locales ignoradas. Para este APK de desarrollo se usará USB
con `adb reverse`, para llegar al backend de esta computadora. No apunta al
backend Railway anterior. Esta dirección de pruebas requiere el túnel USB y no
se considera configuración de despliegue de producción.

El trabajador de avisos ahora permite atender continuamente la cola:

```powershell
# Desde tr-backend, con Firebase configurado y la API funcionando:
.\.venv\Scripts\python.exe -m app.modules.ventas_inventario.services.push_worker --continuo --intervalo 10
```

El modo anterior de un solo lote se conserva. Se verificaron tres pruebas
sin red ni base de datos: detención sin configuración, recuperación ante fallo
transitorio sin exponer sus detalles y compatibilidad con procesamiento de un
solo lote. Las tres aprobaron. El APK con la URL de pruebas compiló correctamente.
No se arrancó el trabajador sobre la cola real ni se dejaron servidores corriendo.

Siguiente paso: conectar el teléfono por USB, habilitar depuración y autorizar la
computadora. Después se instalará el APK actualizado, se iniciará el backend
local y se registrará la instalación desde **Activar avisos push**. El cierre
requiere comprobar un aviso recibido en ese teléfono, además de su aceptación
por FCM. BCP y Stripe mantienen los pendientes externos ya documentados.

### Prueba Android por USB iniciada (31/10/2026)

Se detectó un único teléfono Android autorizado. Se instaló el APK debug con
`adb install -r` correctamente, conservando datos, y se configuró
`adb reverse tcp:8000 tcp:8000`. Se abrió StyleAR en el teléfono y se inició
la API local en `127.0.0.1:8000` para esta prueba. Su health check respondió.

Al comprobar el registro había cero instalaciones Android activas. Se espera que
la usuaria seleccione StyleAR, inicie sesión y pulse **Notificaciones → Activar
avisos push**, aceptando el permiso de Android. Aún no se envió un mensaje de
prueba ni se declaró recepción verificada. La API se mantiene temporalmente
corriendo para permitir el registro durante esta prueba interactiva.

### Firebase: recepción real confirmada en Android (31/10/2026)

La usuaria confirmó **«Dispositivo registrado»** desde la app. Se verificó una
única instalación Android de StyleAR con usuario activo, versión de acceso válida
y sesión vigente. Se creó un aviso de prueba y su registro de salida para esa
instalación; se utilizó el mismo envío FCM del servidor, sin procesar mensajes de
otros usuarios ni realizar compras/cobros.

FCM aceptó el envío real y se conservó su referencia en la salida correspondiente.
La usuaria confirmó **«Sí, llegó la notificación»** en su Redmi Note 12 Pro.
Quedan verificadas configuración Android, autorización del servidor, registro de
instalación y recepción real en el teléfono. Se conserva el aviso «Prueba de
Firebase» en la bandeja como evidencia. No se considera esta prueba una
verificación de APNs/iOS ni de todas las condiciones de entrega de Android.

El teléfono restringió la navegación de pantalla mediante ADB; se continuó con
la usuaria colocando la app en segundo plano manualmente, sin cambiar permisos
adicionales del teléfono.

Se cierra la instancia temporal de API y el túnel USB usados en esta prueba.
Para volver a probar localmente se necesitan la API, el trabajador de cola si
se esperan avisos automáticos y el túnel USB para este APK de desarrollo:

```powershell
# Terminal 1, desde tr-backend:
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# Terminal 2, desde tr-backend:
.\.venv\Scripts\python.exe -m app.modules.ventas_inventario.services.push_worker --continuo --intervalo 10
# Con el teléfono conectado y autorizado:
& 'C:\Users\Anghy\AppData\Local\Android\Sdk\platform-tools\adb.exe' reverse tcp:8000 tcp:8000
```

Firebase deja de estar pendiente para el entorno Android/local verificado.
ORS ya tiene consulta real verificada; conserva pendiente validar ubicaciones
físicas de sucursales y recorrido de carrito. Stripe por empresa y la API QR
real del BCP continúan abiertos; no se habilitaron movimientos bancarios reales.

## Stripe por empresa — conexión TEST iniciada (01/11/2026)

La usuaria confirmó que tiene acceso a la cuenta de las claves de prueba
existentes. Se verificaron consultas reales de cuenta y balance: autenticación
correcta, modo TEST confirmado, país de cuenta US y cobros comerciales todavía
no habilitados. No se cambió esa condición ni se usaron claves LIVE.

Se comprobó con Stripe real, en modo de pruebas, la creación de una sesión de
Checkout en BOB y su idempotencia (el reintento devuelve la misma sesión). Esa
sesión técnica se cerró sin pagar. La clave se configuró exclusivamente como
`STYLEAR_PAGOS_1_STRIPE_SECRET_KEY` para StyleAR; no se asignó a otras empresas
reales. La firma global heredada no se copió a los webhooks por empresa.

Se instaló Stripe CLI 1.55.6 dentro de `.private/stripe-cli`, desde la publicación
oficial y verificando el checksum SHA-256 específico de Windows. No se modificó
el PATH global. Se añadió `scripts/escuchar_stripe.py` para:

- Exigir la clave TEST propia de la empresa, sin fallback a claves globales.
- Reenviar eventos al webhook local de esa empresa.
- Guardar la firma anunciada por Stripe CLI sin imprimirla ni pasar la API key
  en argumentos del proceso.
- Detener únicamente su proceso hijo cuando termina el receptor.

Tres pruebas del receptor aprobaron: aislamiento de claves, resguardo de la
firma y rechazo de claves LIVE.

### Verificación completa en curso

Se creó una base **desechable** `stylear_test_stripe_*` y una empresa ficticia
para verificar Checkout con la misma cuenta TEST autorizada. Su clave y firma
existen solo en `.private/stripe_prueba.env`, separadas del `.env` de StyleAR.
No se modificaron compras ni stock de StyleAR local.

La API temporal y Stripe CLI están atendiendo el puerto 8000 para esta prueba.
Se confirmó rechazo HTTP 400 de una firma inválida. Antes del pago, la compra
estaba pendiente, `pago_recibido=false` y su stock de prueba seguía en 10.

Se proporcionó el Checkout alojado por Stripe a la usuaria para completar Bs 50
con la tarjeta de pruebas 4242 4242 4242 4242, fecha futura y CVC de prueba.
Se espera su resultado para comprobar el webhook real, la venta, inventario,
reintentos y reintegro. Esta fase todavía no se considera cerrada.

Referencia oficial:
[Stripe — pruebas con tarjetas](https://docs.stripe.com/testing),
[Stripe CLI — receptor de eventos](https://github.com/stripe/stripe-cli/wiki/listen-command).

Para pruebas locales posteriores de StyleAR, iniciar primero el receptor y luego
la API, para que esta cargue la firma guardada:

```powershell
.\.venv\Scripts\python.exe scripts/escuchar_stripe.py --empresa 1
# Cuando indique que guardó la firma, en otra terminal:
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Ese receptor local debe permanecer funcionando durante la prueba. No sustituye
un webhook HTTPS de un despliegue. La activación de cobros comerciales y la API
QR del BCP continúan pendientes.

### Stripe TEST: pago, webhook y reintegro verificados (01/11/2026)

La usuaria completó el Checkout alojado por Stripe con la tarjeta de prueba.
El receptor oficial entregó `checkout.session.completed` al backend con respuesta
HTTP 200. Se comprobaron en la base desechable:

- Orden `PAGADO`, pago recibido y venta `COMPLETADA`.
- Stock de prueba de 10 a 9, con un único evento de pago registrado.
- Dos reproducciones del evento real, firmadas para la prueba local, devolvieron
  éxito sin crear otra venta, evento ni descuento de stock.

Se ejecutó CU20 por API en la misma base aislada: política, solicitud, revisión,
recepción vendible, aceptación del importe por el cliente y reintegro. Stripe
confirmó un único reintegro de **Bs 50,00**, estado `succeeded`; la devolución
quedó `REEMBOLSADA` y el stock volvió a 10. Reintentar la solicitud de reintegro
conservó la misma referencia. Los eventos de reintegro recibieron HTTP 200.

La comprobación final contrastó la referencia e importe del reintegro con la
operación de Stripe y el PaymentIntent en modo de prueba. El objeto Refund de
esta versión de la API no incluye `livemode`; el modo se comprobó mediante el
PaymentIntent, las claves TEST y los eventos firmados. No se movió dinero real.

### Configuración de StyleAR local

- Credencial TEST y firma del receptor configuradas únicamente para empresa 1,
  código `stylear`. Las otras empresas reales no recibieron estas credenciales.
- Stripe de pruebas quedó habilitado en su configuración de pagos, conservando
  QR, titular y demás valores existentes. Se guardó la configuración anterior
  en `.private/stripe_configuracion_antes_20261101.json` y se auditó el cambio
  como configuración local, sin atribuirlo a una sesión de usuario ficticia.
- La base `stylear_test_stripe_*`, sus JWT y su archivo temporal de credenciales
  fueron eliminados. Se conserva un resumen sin secretos en
  `.private/stripe_resultado_20261101.json`.
- API y receptores temporales cerrados. No quedaron servidores de esta prueba
  corriendo. No se hicieron commits, push ni despliegues.

Para usar Stripe TEST en la web local:

1. Iniciar `scripts/escuchar_stripe.py --empresa 1` con el Python de `.venv`.
2. Cuando confirme que guardó la firma, iniciar o reiniciar la API local para
   que cargue esa firma desde `.env`.
3. Iniciar el frontend y completar una compra mediante Stripe con tarjeta de
   prueba. El pago se confirma automáticamente por webhook; no usar el botón
   de confirmar simulaciones para una sesión conectada a Stripe.
4. Mantener el receptor y API funcionando mientras se prueba. Las devoluciones
   y diferencias de cambio utilizan la misma cuenta y receptor de la empresa.

Se considera verificada **la conexión Stripe TEST local**: Checkout, firma,
confirmación automática, idempotencia y reintegro CU20. La cuenta continúa sin
cobros comerciales habilitados y el proyecto mantiene el guard de claves TEST.
Este resultado no habilita Stripe LIVE ni constituye validación de un despliegue
HTTPS. La API bancaria real del BCP sigue pendiente de solicitud y documentación.

## BCP — solicitud de habilitación pendiente (01/11/2026)

La usuaria confirmó que tiene una **cuenta personal BCP**, pero todavía no ha
solicitado acceso a la API. La página oficial presenta generación y consulta de
pagos QR; eso no acredita habilitación para una cuenta o proyecto particular.
No se dispone aún de un contrato técnico vigente, URL de sandbox, credenciales,
certificados ni mecanismo oficial de confirmación para StyleAR.

Se revisó la información pública oficial. La consulta directa adicional desde
Python al sitio fue interrumpida por el servidor remoto; no se desactivó TLS ni
se utilizaron documentos de terceros para inventar el contrato bancario.

Referencia: [BCP Bolivia — API Pagos QR SIMPLE](https://www.bcp.com.bo/Desarrollo/ApiPagosQR).

### Solicitud lista para copiar — no enviada

Asunto: Consulta de acceso sandbox API QR SIMPLE para proyecto académico StyleAR

Buenos días:

Soy titular de una cuenta personal BCP y desarrollo StyleAR como proyecto
académico, una plataforma web y móvil para tiendas de ropa. Deseo consultar si
puedo acceder a un ambiente de pruebas de la API QR SIMPLE y qué requisitos
aplican para persona natural o comercio.

La integración necesita generar un QR por compra, consultar y confirmar pagos
automáticamente, conciliar transacciones y gestionar reintegros totales o
parciales. El sistema contempla varias empresas; cada una debe recibir los
cobros en su propia cuenta, sin centralizar los fondos en la cuenta de StyleAR.

¿Podrían indicarme:

1. Si ofrecen acceso sandbox para este tipo de proyecto y cómo solicitarlo.
2. Requisitos para una cuenta personal y, si corresponde, para cada comercio.
3. Documentación técnica vigente, URL de pruebas y procedimiento de entrega de
   credenciales o certificados.
4. Mecanismo oficial de confirmación: notificaciones/callback o consultas de
   estado, autenticación, reintentos y conciliación.
5. Soporte y procedimiento para reintegros o reversas, incluidos los parciales.
6. Condiciones de integración con comercios independientes, costos y requisitos
   adicionales antes de pasar a producción.

Por ahora solicito información y acceso de pruebas, sin activar cobros reales.

Muchas gracias.
[Nombre y medio de contacto]

### Trabajo que depende de la respuesta

Después de recibir la documentación y habilitación del banco se implementarán
el adaptador concreto, autenticación, generación QR, confirmación verificable,
conciliación y reintegros admitidos por el contrato. Se probará el aislamiento
por empresa, reintentos, estados pendientes, fallos y ausencia de duplicaciones.
No se puede afirmar que el banco ofrezca un endpoint de reintegro o callbacks
específicos hasta que lo confirme su documentación.

El endpoint BCP real conserva su respuesta de integración pendiente y no se
convierte un QR simulado en un cobro bancario. Stripe TEST, Firebase Android y
la consulta real ORS mantienen las verificaciones anteriores. No se enviaron
mensajes al banco, se activaron servicios bancarios ni se modificaron compras,
stock, credenciales o configuraciones de pago en este paso.

### 2026-11-01 — Cuentas de prueba por rol
- Creadas en StyleAR: admin.prueba (ADMINISTRADOR), cajero.prueba (CAJERO), encargado.prueba (ENCARGADO_SUCURSAL), ventas.prueba (PERSONAL_VENTAS) y proveedor.prueba (PROVEEDOR).
- Cajero, encargado y ventas asignados a Suc Banzer; proveedor vinculado a una ficha exclusiva de pruebas.
- No se crearon clientes ni administradores SaaS ni se modificaron cuentas existentes. Se respetaron los limites del plan y se registro la creacion en bitacora.
- Verificado el inicio de sesion de las cinco cuentas con su rol exclusivo y empresa stylear; sesiones de verificacion cerradas. Claves fuera del seguimiento y del codigo versionado.
