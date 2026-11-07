# Seguimiento de implementación de StyleAR

Autor: Angeles Rosales Colque.

Este archivo reúne el arranque local, las reparaciones y el avance por bloques. Se actualizará con cada implementación.

## Estado actual — cierre local CU22–CU27 (07/11/2026)

Implementación de los siete bloques completada en web y Flutter, incluida administración SaaS móvil. R2 conectado y verificado con respaldo/restauración reales sobre datos sintéticos: empresa con archivos y aislamiento, y copia global restaurada en otra base vacía. Base de trabajo con 18/18 migraciones. Regresión final: 51 comprobaciones backend aprobadas (48 de integración CU22–27, una adicional de renovación/cambio de empresa y dos con R2 real), 33 web y 83 Flutter. Se retiraron bases, cuentas y objetos de ensayo.

Backend local http://127.0.0.1:8000 y web http://127.0.0.1:4200/empresa iniciados y comprobados con HTTP 200, junto con el directorio de empresas. No iniciar otra instancia en esos puertos mientras sigan activos. Los procesos y logs del arranque están en .private/local_procesos.json y .private/local_{backend,frontend}.{out,err}.log.

El APK release de prueba ya instalado utiliza API_URL=http://127.0.0.1:8000. Al cierre ADB no detecta el Redmi. Para usarlo con esta API, reconectar el USB autorizado y ejecutar `adb reverse tcp:8000 tcp:8000`. La cuenta temporal de Atelier Norte fue retirada; cerrar esa sesión y elegir la empresa real StyleAR para las pruebas locales. No se borraron datos de la aplicación ni se cambió su instalación.

Límite externo: BCP QR real no puede habilitarse sin la documentación y credenciales sandbox del banco. Se conserva la simulación identificada como tal; no se anuncia conexión bancaria real. No hay despliegue ni publicación de APK de tienda.

Validación física confirmada: aviso en primer plano, segundo plano, proceso cerrado, pantalla bloqueada y bandeja con permiso Android desactivado/reactivado. Cambio de cuenta, renovación y categoría silenciada tienen cobertura automatizada de servidor; no se acreditan como ensayos físicos. Dictado y recorrido físico completo de las pantallas administrativas siguen sin acreditación manual, sin pendientes de implementación identificados por las pruebas.

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

### 2026-11-06 — CU22 a CU27, bloque 1: migraciones, sesión SaaS móvil y capacidades

Alcance acordado: integración local en web y Flutter, incluyendo administración SaaS móvil con el mismo alcance funcional de plataforma que web. Se conservan los módulos y pantallas anteriores. No se desplegó ni se modificaron servicios externos.

- Base PostgreSQL comprobada como local. Respaldo previo: `.private/antes_cu22_cu27_20261106.dump`. Aplicadas CU25 R2 (`2026_11_05_cu25_respaldos_r2`), CU26 (`2026_11_05_cu26_planes`) y CU22/CU27 (`2026_11_06_cu22_cu27_mejoras`). Segunda ejecución sin reaplicar versiones. Lectura real de capacidades StyleAR verificada: 12 funciones y 5 cupos.
- Flutter: entrada «Administración de la plataforma» desde el directorio; login SaaS sin empresa, restauración de sesión, salida y pantalla inicial con empresas/planes desde API. La sesión SaaS no envía X-Empresa-Codigo y el cliente bloquea rutas comerciales en ese ámbito. El servidor mantiene la autorización definitiva. Los formularios de gestión se completan en bloque 2.
- Flutter: modelos de capacidades y PlanProvider compartido, separado de permisos de usuario. Consulta al iniciar sesión y cada minuto, refresco tras escrituras que consumen cupos y rechazos comerciales; el estado se reemplaza al cambiar generación. SaaS no consulta capacidades de empresa ni registra automáticamente avisos push comerciales.
- Web: EstadoPlanService conserva capacidades efectivas, funciones habilitadas, cupos y motivos. Se consulta para todos los usuarios de empresa al navegar y cada minuto; refresca tras consumos/rechazos y descarta solicitudes al invalidar contexto. No usa nombres de planes como regla comercial.
- Web: alineada continuidad con backend para chat, dashboard, detalle, pausa de reportes y previsualización/restauración de respaldos. El interceptor conserva el detalle estructurado y cuerpo original además del mensaje compatible con pantallas anteriores.
- Archivos principales: mobile `core/session/contexto_sesion.dart`, `core/network/api_client.dart`, `providers/auth_provider.dart`, `providers/plan_provider.dart`, `models/capacidades_plan.dart`, `screens/auth`, `screens/saas/plataforma_screen.dart`, `main.dart`; web `core/models/capacidades-plan.models.ts`, `core/services/estado-plan.service.ts`, `error-api.ts`, `core/interceptors/auth.interceptor.ts`, `shared/components/estado-empresa`.
- Verificación: build Angular de producción aprobado (advertencias existentes leaflet/qrcode); 19 pruebas web aprobadas. Node 25 requiere ejecutar pruebas con NODE_OPTIONS=--no-experimental-webstorage para usar localStorage de JSDOM. Análisis Flutter limpio y suite previa con cinco pruebas nuevas aprobada: 56 pruebas. La prueba adicional de la pantalla SaaS se verifica por separado al cierre del bloque. No se afirma prueba física ni APK de distribución en este bloque.

Bloques pendientes: 2) CRUD SaaS y Mi plan; 3) respaldos; 4) reportes; 5) recomendaciones y chat; 6) notificaciones y Android; 7) recorridos completos y APK físico. La pantalla inicial SaaS de este bloque no representa todavía la gestión completa de plataforma.

Cierre de verificación del bloque 1: la prueba visual automatizada de la pantalla inicial SaaS aprobó; las seis pruebas del nuevo archivo `test/saas_sesion_test.dart` pasaron, incluyendo pantalla, restauración y separación de sesiones. Total de pruebas Flutter verificadas: 57 (51 anteriores y 6 nuevas). La preparación de almacenamiento del widget usa runAsync para no bloquear el reloj simulado. No se dejaron servidores de pruebas iniciados.

### 2026-11-06 — CU26, bloque 2: planes, empresas y suscripciones en web y Flutter

Web:
- Ampliadas las rutas existentes `/saas/planes`, `/saas/empresas` y `/mi-plan`; se conserva el CRUD y la asignación/renovación existente.
- Planes consume el catálogo comercial real. Añade descripción, condiciones, precio de referencia, moneda, publicación y estado; muestra cupos y funciones editables de reportes/respaldos. No ofrece interruptores para retirar funciones esenciales ni incorpora productos como diferenciador nuevo.
- Edición con previsualización de impacto, empresas afectadas, excesos de uso, reportes a pausar y restablecimiento de horario. Guardado con el mismo contenido y token; volver a editar invalida la previa. Ante 409 conserva el formulario, descarta la confirmación y exige revisar nuevamente. Solo se envían campos modificados, para conservar metadatos y claves históricas no editadas, incluidos cambios simultáneos de otra sesión.
- Añadidos historial de planes (antes/después), comparación y conteos de empresas únicas, vigentes y no vigentes. Enlace por plan al listado remoto, filtros por nombre/código/estado y páginas de 20 empresas.
- Configuración de empresa incluye capacidades efectivas e historial de suscripciones, manteniendo nombre, estado, aprobación, alta y renovación. El contacto de solicitudes pendientes se consulta desde la API existente al abrir el detalle. Respuestas tardías de listas/detalles y datos al cambiar sesión se descartan.
- Mi plan usa el estado compartido de capacidades, sin fallback por nombre/código de plan. Muestra uso, disponibles, cero/sin límite, vigencia y motivos. Una actualización del estado compartido se refleja en la vista ya abierta.
- Archivos principales: `modules/administracion/models/saas.models.ts`, `services/saas.service.ts`, `pages/saas/planes.page.ts` y `.html`, `empresas.page.ts`, `mi-plan.page.ts`, componente reutilizable `capacidades-plan.component.ts` y estilos existentes `saas.css`.

Flutter:
- La entrada SaaS incorpora accesos a Gestionar planes, Gestionar empresas y Auditoría de plataforma.
- Nuevas pantallas dentro de `lib/screens/saas`: listado/comparación/conteos de planes, editor con previsualización y confirmación, historial, listado paginado de empresas y registro/configuración de empresa. Incluyen alta del administrador inicial, cambio de nombre/estado, aprobación por suscripción, asignación/renovación, capacidades e historial.
- Se mantienen los alcances separados: ADMIN_SAAS opera solo rutas de plataforma. El administrador de empresa tiene Mi plan en Perfil, sin editar planes ni asignar suscripciones.
- Dependencias del catálogo y límites validados, sin enviar null para borrar cupos. La edición parcial y el 409 siguen las mismas reglas de web. El formulario bloquea envíos duplicados y muestra el error de conflicto al volver al inicio de la pantalla.
- Agregados `models/saas_models.dart`, `services/saas_service.dart`, widgets de sesión/errores y `screens/perfil/mi_plan_screen.dart`; reutilizado PlanProvider y ApiClient. El APK de debug utiliza el archivo local de defines existente.

Verificación del bloque:
- Flutter: análisis limpio; 62 pruebas aprobadas, incluidas cinco de CU26 (dependencias/fechas, edición parcial, contrato preview/token, conflicto 409 y empresas filtradas). APK debug actualizado: `tr-mobile/build/app/outputs/flutter-apk/app-debug.apk`.
- Web: 19 pruebas unitarias aprobadas. Recorridos Playwright/Edge contra PostgreSQL y FastAPI desechables: creación/edición/impacto/conflicto/conservación de claves e historial; empresas por plan, paginación con 21 registros, capacidades, historial y renovación; actualización de capacidades de una sesión de empresa ya abierta. Incluyen AXE, foco de revisión/historial y pantalla estrecha. Se corrigen regiones desplazables para teclado y niveles de encabezados.
- Las cuentas/empresas creadas por los recorridos pertenecen exclusivamente a la base desechable `stylear_test_cu26_ui_*`, no a la base local de trabajo. No se hicieron despliegues, cobros ni restauraciones. No se afirma prueba física de las pantallas nuevas ni APK de distribución.
- Respaldos R2, programación y presentación push nueva siguen en sus bloques correspondientes. La fixture antigua informa fallos de respaldos automáticos por falta de configuración R2; esos avisos no acreditan funcionamiento de CU25 ni se trataron como éxito.

Siguiente bloque: CU25, respaldos de empresa en ambas aplicaciones y ampliación del alcance SaaS, con almacenamiento simulado en las pruebas y sin restaurar la base de trabajo.

Cierre del bloque 2: build web de producción aprobado con las advertencias CommonJS existentes; 19 pruebas unitarias web aprobadas. Los tres recorridos nuevos de Edge/AXE aprobaron (plan y empresas en la ejecución conjunta; actualización de sesión en repetición aislada tras corregir una carrera de navegación del propio test). Flutter terminó con análisis limpio, 62 pruebas aprobadas y APK debug compilado con el código final. La API temporal fue detenida y la base desechable, su DSN y los archivos de fixture/correo fueron eliminados. No se dejó un servidor nuevo corriendo ni se instaló el APK en el teléfono.

### 2026-11-06 — CU25, bloque 3: respaldos de empresa y plataforma

Implementación:
- Web: nueva ruta `/respaldos` para ADMINISTRADOR, enlazada desde Administración. Se reutiliza la vista de respaldos existente con ámbito explícito EMPRESA/PLATAFORMA; `/saas/respaldos` conserva ADMIN_SAAS y su selector global. El servicio de empresa usa exclusivamente `/api/v1/respaldos` y la empresa de la sesión, sin selector ni purga de plataforma.
- Flutter: pantalla `screens/respaldos/respaldos_screen.dart` con ámbito explícito, accesible desde Perfil para ADMINISTRADOR y desde la entrada SaaS para ADMIN_SAAS. Incluye listado, creación, programación de empresa, revisión, eliminación y restauración; la purga de vencidos existe solo en plataforma.
- Listados con origen MANUAL/AUTOMATICO/PRE_RESTAURACION, alcance GLOBAL/EMPRESA, fecha, vencimiento, tamaño y estado. No se agregaron enlaces de descarga, URLs R2 ni secretos a los clientes.
- Cuota manual móvil de siete días desde capacidades, con uso/disponibles y distinción entre cero y sin límite. Eliminar no devuelve cupo; automáticos y preventivos no lo consumen. Retirar creación manual mantiene consulta y revisión/restauración de las copias disponibles.
- Programación: activa, fecha de inicio, hora HH:MM y zona. Se normaliza HH:MM:SS. Cuando el plan no permite editar horario, se muestra y envía 02:00/America/La_Paz. Frecuencia y retención se consultan desde el plan, sin campos de edición para el administrador de empresa. No se infieren cupos a partir de nombres de planes.
- Restauración: revisión previa y frase exacta escrita por el usuario, sin autocompletar. Enter no restaura. Para empresa se comprueba suspensión, se informa de la copia preventiva, cierre de sesiones y conservación de la suscripción actual. La restauración global se mantiene exclusivamente en un ensayo vacío separado de la base activa. Una restauración de empresa pide nuevo ingreso; SaaS conserva su sesión.
- Operaciones en curso bloqueadas para impedir doble envío. Ante timeout/resultado incierto no hay repetición automática: se bloquea repetir hasta consultar listado/uso mediante Actualizar. Se limpia selección/confirmación y estado al cambiar contexto. Los mensajes de servicio no disponible no muestran variables privadas del servidor.
- Se ajustó PlanProvider para compartir y esperar una consulta de capacidades ya en curso, evitando decidir sobre un cupo antes de recibir la respuesta.

Archivos principales:
- Web: `pages/saas/respaldos.page.ts` y nueva plantilla `.html`, `services/respaldos-empresa.service.ts`, modelos SaaS, rutas, menú y mensaje de ingreso posterior a restauración.
- Flutter: `models/respaldo_models.dart`, `services/respaldos_service.dart`, `screens/respaldos/respaldos_screen.dart`, enlaces en Perfil/Plataforma y PlanProvider.
- Pruebas: `respaldos.page.spec.ts`, `e2e/cu25-respaldos.spec.ts`, `test/cu25_respaldos_test.dart`; fixture E2E con R2 en memoria y ejecutores automáticos desactivados únicamente en modo STYLEAR_E2E_RESPALDOS. Instrucciones añadidas al README E2E existente.

Validación:
- 23 pruebas unitarias web aprobadas; 68 pruebas Flutter aprobadas y análisis limpio. APK debug actualizado con el archivo de defines local existente. No instalado ni probado físicamente en este bloque.
- Edge/AXE contra FastAPI/PostgreSQL reales y R2 en memoria: programación fija, dos copias manuales, 429 de cuota, eliminación sin liberar cupo, separación A/B (404 al acceder a copia ajena), bloqueo por rol, revisión de empresa activa, suspensión, frase exacta, Enter sin restaurar, restauración real de empresa, sesión anterior revocada, nombre del perfil recuperado, suscripción Básico actual preservada y copia preventiva registrada. La sesión de B permanece válida.
- Restauración global real mediante pg_dump/pg_restore hacia una segunda base desechable y vacía: clon con 18 versiones de esquema y cero sesiones activas. La base API original y la sesión SaaS permanecen disponibles. Incluye vista estrecha y AXE.
- Las bases utilizadas tienen prefijo `stylear_test_cu25_ui_*`. No se restauró ni modificó la base local de trabajo ni se usó un bucket real para las pruebas.

Pendiente externo concreto:
La comprobación local de configuración devolvió incompleta. Para crear copias reales en local deben completarse en el servidor `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_ENDPOINT_URL` y `STYLEAR_BACKUP_KEY` (con R2_REGION opcional). La clave de cifrado debe ser estable y corresponder a las copias existentes; no reemplazarla ni regenerarla si ya hay respaldos que dependan de ella. No se afirma validación contra R2 real. La interfaz y el contrato están implementados y probados con almacenamiento simulado.

Siguiente bloque: CU22, dashboard comercial, reportes paginados y programación/historial en ambas aplicaciones.

Cierre adicional del bloque 3: build web de producción aprobado; APK debug final compilado. La API de pruebas fue detenida y se retiraron las bases de API y ensayo, sus DSN y los JSON temporales de fixture/correo.

Incidencia del backend descargado detectada durante el recorrido: GET de usuarios y bitácora podía devolver 500 (`set_session cannot be used inside a transaction`). El contexto compartido adquiría un cerrojo antes de que esas consultas configuraran REPEATABLE READ/read-only. Se movió la configuración al inicio de `_transaccion`, antes del primer SELECT, y ambos listados ahora solicitan su política al abrir el contexto. Se mantienen el cerrojo y el aislamiento entre empresas; no se cambian permisos ni datos. Archivos: `perfil_repository.py`, `administracion_acceso_repository.py`, `bitacora_repository.py`.
Verificación de la incidencia: tres pruebas de integración existentes de listado de usuarios, alcance SaaS autorizado y aislamiento/detalle de bitácora aprobaron sobre PostgreSQL desechable. La base de regresión se retiró al finalizar. No se modificaron datos de la base local de trabajo.


### 2026-11-06 — CU22, bloque 4: dashboard, detalle paginado y reportes programados

Implementación web y Flutter:
- Dashboard comercial con rango de fechas, sucursal, canal y comparación opcional con el período anterior calculado por el servidor. Ventas presenciales/digitales, reservas, stock actual, serie, productos más vendidos y definiciones. Flujos separados por moneda; importes mostrados como cadenas decimales del servidor. Neto significa cobrado menos reembolsado, no ganancia. Una base anterior cero se muestra sin porcentaje; no se inventa una variación.
- Detalle mediante POST /reportes/detalle, con páginas remotas de 20 filas y resumen/serie del resultado completo. No se descargan miles de filas para paginar en memoria. Se conservan los filtros de la consulta visible para cambiar de página y exportar aunque el editor haya cambiado. Flutter muestra también las fechas de esa consulta, no las del formulario en edición.
- Exportaciones PDF/Excel sujetas a capacidades efectivas. Más de 5.000 filas siguen siendo consultables; se pide reducir el rango para exportar, sin producir archivos truncados. La exportación HTML móvil preexistente obtiene el reporte completo dentro del mismo límite.
- Interpretación distingue origen TEXTO/VOZ y aplica capacidades de interpretación/dictado, sin decidir por nombre del plan. Conserva revisión de filtros antes de consultar. No se afirma prueba física del micrófono en este bloque.
- ADMINISTRADOR consulta su empresa y administra programaciones. ENCARGADO_SUCURSAL tiene dashboard/reportes de su sucursal asignada, sin selector Todas, tipo USUARIOS ni sección Automáticos. Se habilitó su acceso en rutas/menú sin darle los contadores administrativos globales. ADMIN_SAAS conserva su alcance de plataforma.
- Programaciones: alta, edición parcial con revisión, frecuencia/día/hora/zona/período, sucursal, formato, destinatario, filtros, activo/pausado e historial de ejecuciones. Ante 409 se conserva el formulario y se exige revisar la versión vigente. Solo los cambios explícitos se guardan; se conservan pausas y filtros concurrentes no editados. Cambiar la frecuencia normaliza el día correspondiente.
- Envío manual con confirmación, bloqueo de doble envío y prohibición de ejecutar una programación pausada. Una respuesta incierta bloquea repetir hasta revisar historial y autorizar expresamente otra ejecución; no hay reintentos automáticos. El mensaje refleja el transporte configurado sin afirmar entrega a una dirección que el servidor pudiera sustituir.
- Web mantiene /dashboard y /reportes; Flutter reutiliza ReportesAdminScreen y su sección Automáticos, separando widgets de dashboard/programación para evitar otra implementación paralela. Datos y respuestas se invalidan al cambiar contexto de sesión.

Archivos principales:
- Web: modelos/servicio de reportes; dashboard-comercial.component.ts; reportes.page.ts/.html; programaciones-reportes.component.ts; rutas/menú y dashboard existente.
- Flutter: reporte_models.dart, reporte_service.dart, reportes_admin_screen.dart, dashboard_comercial_tab.dart y programados_reportes_tab.dart.
- Pruebas: reportes.page.spec.ts, e2e/cu22-reportes.spec.ts, test/cu22_reportes_test.dart; fixture exclusiva STYLEAR_E2E_REPORTES documentada en el README E2E existente.

Validación:
- 25 pruebas unitarias web aprobadas. Build de producción aprobado con advertencias CommonJS preexistentes.
- Flutter: 72 pruebas aprobadas y análisis sin incidencias. APK debug generado con el archivo local de defines existente; sin instalación ni validación física de las pantallas nuevas.
- Dos recorridos Edge aprobados contra FastAPI/PostgreSQL reales desechables: 5.200 ventas, total 10.400, 260 páginas, cambio de formulario sin alterar la página consultada, bloqueo de exportación grande, descarga PDF de usuarios, alta/edición 409/formulario conservado/pausa preservada, activación, envío con adjunto capturado e historial ENVIADO; encargado sin opciones prohibidas y 403 al pedir sucursal ajena. AXE sin incidencias en dashboard, detalle y programación a ancho estrecho.
- Los ejecutores automáticos y proveedores externos se sustituyen solo en la fixture. No se enviaron correos reales ni se modificó la base local de trabajo. No se agregaron migraciones en este bloque.

Pendientes: verificación física de pantallas/dictado en el bloque final; configuración R2 real sigue pendiente según el bloque 3. Siguiente bloque: recomendaciones y asistente/chat (CU23–CU24), seguido de notificaciones y recorrido Android.

Cierre del bloque 4: repetición final de 25 pruebas web y build de producción aprobada; análisis Flutter limpio y APK debug final generado. API temporal detenida, puerto 58127 libre y base stylear_test_cu22_ui_* retirada junto con su DSN y los JSON de fixture/correo. No se dejaron servidores nuevos ni se instaló el APK en el teléfono.


### 2026-11-07 — CU23–CU24, bloque 5: recomendaciones, preferencias y asistente

Implementación:
- Se amplían las pantallas actuales: web /para-ti, detalle de prenda y chat flotante; Flutter modo Para ti del catálogo, detalle de prenda y AsistenteScreen. No se crea otro chatbot ni se modifican compras, reservas o pagos para atender consultas.
- Preferencias móviles en un sheet accesible desde el icono de ajustes de la cabecera al entrar en Para ti, sin superponer el acceso flotante al chat. Lectura/guardado de categorías (máximo 10) y usar_historial; carga, fallo recuperable, formulario conservado y bloqueo de doble guardado. Desactivar personalización deja vacía la lista personal y conserva favoritos. Web explicita el mismo comportamiento y añade controles de carga, límite de categorías, errores y contraste.
- Recomendaciones conservan el motivo real del servidor; no convierten score en porcentaje ni prometen uso de IA cuando son sugerencias iniciales. Las tarjetas móviles existentes ya usaban precioFinal. Web corrige precio cero válido; precios ausentes se muestran pendientes. El detalle móvil reconsulta por talla/sucursal y descarta resultados anteriores al cambiar selección.
- Contratos del asistente ampliados con contexto permitido completo (empresa/producto/variante/sucursal, recurso tipo+ID, términos/colores/tallas/precio), fuentes, consultado_en, datos, aclaración y hay_mas. Cada siguiente pregunta reenvía el contexto devuelto, sin mandar historiales completos ni campos arbitrarios. Hay una acción para quitar selección e iniciar otra consulta.
- Desde el detalle se abre el mismo asistente con la prenda/variante/sucursal real; web conserva también talla/color seleccionados cuando todavía hay varias variantes. La selección de una tarjeta puede fijar la variante consultada para el siguiente turno.
- Tarjetas de prendas muestran precio_final_exacto, precio_final o precio_vigente en ese orden, conservando cero y distinguiendo null; moneda, promoción, descripción/material, disponibilidad y motivo. Las alternativas se identifican como posibles resultados que no cumplen todos los filtros. Consultar no reserva stock.
- Datos estructurados se muestran con etiquetas comprensibles: sucursales y políticas públicas, reservas, ventas, órdenes de pago, deliveries, cambios, devoluciones y reembolsos. Se conserva reembolso_confirmado y condiciones de la operación; no se transforma aprobación en dinero reintegrado. Varias operaciones requieren elegir explícitamente tipo+ID, sin seleccionar la primera automáticamente.
- Para RESERVA, ORDEN_PAGO y DELIVERY se abre el detalle existente con su identificador correspondiente. VENTA nunca se trata como orden de pago; los restantes tipos mantienen consulta y seguimiento en el chat, sin inventar relaciones ni rutas de detalle. Acciones de web y móvil usan destinos internos permitidos; no se abren URLs arbitrarias del mensaje.
- Mensajes de hasta 600 caracteres, carga/error, 401 sin repetir como visitante y 429 respetando Retry-After (o espera conservadora), sin reintentos automáticos. ApiException móvil conserva Retry-After sin alterar el tratamiento anterior de errores.
- Cambio de cuenta/empresa limpia conversación, selección, texto y recomendaciones en memoria. Respuestas en vuelo se descartan por generación; cambiar selección también invalida consultas de recomendaciones anteriores. Se limpian preferencias visibles de un sheet que permanece montado. No se guarda conversación permanentemente.

Archivos principales:
- Web: asistente.models.ts, asistente.service.ts, componente asistente-chat, ParaTiPage y detalle de producto.
- Flutter: asistente_models.dart, recomendacion_service.dart, ApiException/ApiClient, AsistenteScreen y helper datos_chat.dart; nuevo preferencias_recomendaciones_sheet.dart dentro de catálogo y ajustes en catálogo/detalle existentes.
- Pruebas: asistente-chat.component.spec.ts, e2e/cu23-cu24.spec.ts y test/cu23_cu24_test.dart. Fixture y README E2E existentes ampliados; no se crea otro archivo de seguimiento.

Verificación realizada:
- 29 pruebas unitarias web aprobadas y build de producción aprobado (advertencias CommonJS existentes). Incluyen contexto devuelto, tipo+ID, cambio de sesión con respuesta pendiente, 429 sin repetición, precio exacto/cero/null y rechazo de destinos arbitrarios.
- 76 pruebas Flutter aprobadas; las cuatro nuevas cubren contratos/precio/destinos, continuidad y limpieza de chat, preferencias desactivadas conservadas ante fallo, y descarte de respuesta de una sesión anterior.
- Recorrido Edge/AXE contra FastAPI/PostgreSQL desechables aprobado: favoritos conservados con personalización apagada, precio promocionado BOB 40.00 y material, continuación con talla M, dos reservas propias sin elección silenciosa, seguimiento de vencimiento, 403/404 al producto de otra empresa y cliente de B sin reservas de A. AXE sin incidencias en Para ti y chat en vista estrecha.
- Se usan datos sintéticos, RULES y ausencia de embeddings externos. No se cambió la configuración real de IA, no se indexaron productos ni se enviaron correos/push. CU23/CU24 no requieren nuevas migraciones.

Límites pendientes: validación física del chat, voz, preferencias y navegación en el teléfono dentro del bloque final; este bloque no acredita proveedor real de IA ni APK de distribución. Configuración R2 real y documentación/credenciales BCP continúan pendientes según registros anteriores. Siguiente bloque: CU27, bandejas/preferencias/destinos y avisos emergentes Android.

Cierre del bloque 5: repetición final del recorrido Edge/AXE aprobada; build web de producción aprobado; análisis Flutter sin incidencias y APK debug generado con los defines locales existentes. No instalado en el teléfono. API temporal detenida y base stylear_test_cu23_ui_* eliminada junto con el DSN y los JSON de fixture/correo. Se conserva la base local de trabajo y no se dejan servidores nuevos corriendo.


### 2026-11-07 — CU27, bloque 6: bandejas, preferencias, destinos y Android

Implementación web:
- La clase NotificacionesPage conserva la ruta /notificaciones y se separa del archivo de pagos de empresa mediante reexportación, sin crear otro módulo. PagoService/modelos existentes incorporan bandeja paginada de 20 avisos, resumen global, lectura individual/todas, preferencias, destino y trazabilidad.
- Lectura/categoría, total filtrado, contador de no leídas global independiente del filtro/página y paginación remota. Marcar todas alcanza la cuenta completa y refresca la consulta; se ajusta la página si el filtro queda vacío. Estados de carga, error y bloqueo de operaciones duplicadas.
- Preferencias dentro de la misma bandeja: categorías GENERAL/COMPRA/PAGO/RESERVA/ENTREGA/CAMBIO/DEVOLUCION/REEMBOLSO. Se guardan solo cambios explícitos para conservar ajustes simultáneos; un fallo mantiene el formulario. Silenciar afecta push y no elimina la bandeja.
- Cada apertura consulta /{id}/destino con la sesión vigente. Reserva, orden de pago y delivery usan sus detalles existentes. Cambio/devolución abren sus flujos con selección inicial. VENTA nunca se trata como orden de pago; ante falta de destino apropiado o recurso no disponible se explica la continuidad en bandeja. No se usan URLs arbitrarias del aviso.
- Trazabilidad distingue leído en bandeja, envíos aceptados por Firebase, pendientes/fallidos/omitidos. No equipara aceptación FCM con visualización. Se limpian listas, preferencias, contadores y trazabilidad al cambiar contexto; respuestas anteriores se descartan.

Implementación Flutter/Android:
- NotificacionesScreen consume el mismo contrato paginado y conserva la sección preexistente de reembolsos de compras no completadas. Preferencias en sheet; selección y errores se conservan y limpian por generación de sesión. La navegación elimina el antiguo PagoStripeScreen(checkoutUrl:'') para consultas.
- Helper de destinos tipados reutiliza ReservaDetalleScreen, DetallePagoScreen(esAdmin:false), DetalleDeliveryScreen(esStaff:false), CambiosScreen y DevolucionesScreen. Estos dos últimos admiten selección inicial autorizada dentro de sus flujos; no se confunden venta y pago por coincidencia de ID.
- Aviso de primer plano mediante puente nativo Android `stylear/notificaciones` en MainActivity.kt, sin dependencias Flutter nuevas ni actualización masiva de SDK. Canal `stylear_transacciones_v1`, importancia alta inicial y sin sobrescribir un canal existente, icono monocromo dedicado y contenido genérico. Se declara POST_NOTIFICATIONS y el canal/icono por defecto de Firebase en AndroidManifest.xml.
- Inicialización de SDK/handlers separada de solicitar permiso. FCM onMessage valida sesión/empresa y acceso al aviso antes de presentar localmente; deduplica por generación/empresa/notificación. En segundo plano se conserva la notificación que presenta Android, sin crear otra en el handler de fondo.
- Aperturas mediante onMessageOpenedApp/getInitialMessage y callback/inicio nativo para avisos locales. PuentePush usa un navegador nuevo por generación y consulta el destino con autorización actual. Sin ingreso se conserva solo referencia mínima; al cambiar cuenta se descarta contenido anterior. No se navega directamente con IDs del payload.
- UUID de instalación persistente y renovación de token con activación previa. Logout intenta desvincular con sesión aún válida antes de revocar el acceso y limpia avisos locales. Los cambios de cuenta invalidan referencias/contadores; el backend conserva sus validaciones de sesión y preferencia en la cola.
- Arranque de la aplicación no espera indefinidamente al SDK; un fallo de preparación puede reintentarse. Sin Firebase o permiso/canal disponible continúa la bandeja. Los ajustes de Android solo se abren por acción del usuario; no se elevan permisos ni importancia silenciosamente.

Validación local completada:
- 33 pruebas unitarias web y build de producción aprobados. Recorrido Edge/AXE aprobado sobre PostgreSQL/FastAPI desechables: más de 40 avisos y tres páginas; contador global al filtrar; marcado de todas fuera de filtro/página; preferencias parciales con cambio concurrente conservado; trazabilidad; compra sin abrir pago; reserva correcta; 404 de aviso ajeno. Vista estrecha sin incidencias AXE.
- 82 pruebas Flutter aprobadas; seis nuevas cubren destinos y referencia mínima, desvinculación con UUID/token de sesión, contador/lectura de todas/reembolsos, preferencias fallidas conservadas, respuesta tardía descartada y puente Android por acción explícita. La prueba antigua de CU16 se actualizó al contrato de bandeja paginada, conservando su verificación de reintento/lectura/Firebase ausente.
- Análisis Flutter limpio. APK release de prueba compilado e instalado mediante actualización, sin borrar datos de la app. La configuración release existente firma con clave de depuración para pruebas locales; no se afirma publicación ni firma de distribución de tienda.
- Manifiesto combinado release verificado: POST_NOTIFICATIONS, canal `stylear_transacciones_v1` e icono dedicado. Dispositivo conectado Android 13/API33; paquete instalado minSdk24/targetSdk36. El permiso de notificaciones ya figuraba concedido al inspeccionar el paquete.

Prueba física en curso:
El usuario confirmó teléfono conectado y disponible. Se instaló el APK y preparó una base `stylear_test_cu27_ui_*`, una cuenta cliente sintética y una API de ensayo sin ejecutores automáticos. Aún no se emitió ningún FCM real en este bloque: el teléfono seguía bloqueado y la base de ensayo tenía cero dispositivos vinculados. Se pidió desbloquear StyleAR, ingresar a la cuenta temporal y pulsar Activar avisos push. No se acredita todavía recuadro visible, apertura real en primer/segundo plano/proceso terminado, pantalla bloqueada, canal/permiso denegado ni renovación física. Mantener esos puntos pendientes hasta obtener evidencia; no sustituirlos por aceptación del proveedor.

Fuentes técnicas consultadas: Firebase Flutter receive-messages (https://firebase.google.com/docs/cloud-messaging/flutter/receive-messages), y referencia del paquete flutter_local_notifications para evaluar compatibilidad (https://pub.dev/packages/flutter_local_notifications). Se eligió el puente Android nativo en la estructura actual; no se añadió ese paquete.

Pendientes externos anteriores: R2 real incompleto y BCP sin documentación/credenciales sandbox. No se modificaron claves, proveedores ni datos de la base local de trabajo al preparar la prueba CU27.

Actualización al cierre local de CU27: APK release final generado y enviado como actualización al Redmi; análisis limpio y 82 pruebas Flutter aprobadas, 33 web aprobadas y build web de producción aprobado. La única regresión de prueba anterior era un mock con la lista plana antigua y fue corregida al contrato paginado. La API de ensayo en 127.0.0.1:58127 sigue activa, con ADB reverse tcp:8000 hacia tcp:58127 y ejecutores automáticos desactivados, para completar la prueba cuando el usuario desbloquee el teléfono y registre la cuenta temporal. Última verificación: cero dispositivos activos en la base de ensayo; no se envió FCM real. La base y su DSN deben retirarse después de la prueba física, no antes.

### 2026-11-07 — Recuperación de conexión del teléfono en CU27
El teléfono informó que no podía conectar. La lista ADB reverse estaba vacía. La verificación HTTP posterior confirmó que la API original de ensayo seguía activa en 127.0.0.1:58127 y aceptaba la misma cuenta; no fue necesario recrear la base ni cambiar credenciales. Se restableció adb reverse tcp:8000 tcp:58127. Una petición HTTP ejecutada desde Android hacia 127.0.0.1:8000 recibió HTTP/1.1 200 OK. Se solicitó reintentar en la app y registrar avisos para continuar la prueba física. El intento de iniciar otra instancia encontró el puerto ocupado y terminó; se mantiene la instancia original. No se emitió FCM como parte de esta recuperación.

Seguimiento de conexión CU27: se observó una nueva reconexión USB (túnel otra vez ausente). Se preparó un ayudante temporal y oculto .private/mantener_tunel_cu27.py, limitado a una hora y al teléfono de ensayo, que solo repone el mapeo si falta; no modifica conexiones existentes. Debe detenerse al terminar la prueba mediante el archivo .private/cu27_tunel_detener o su PID verificado. Se reabrió StyleAR para descartar conexiones previas. GET de empresa y POST de ingreso ejecutados desde Android devolvieron 200 OK. La pantalla de ingreso estaba seleccionando StyleAR, mientras la cuenta sintética pertenece a Atelier Norte; las credenciales originales siguen válidas en la empresa correcta. Android bloqueó la pulsación remota con INJECT_EVENTS, por lo que el cambio de empresa debe hacerlo el usuario manualmente; no se cambió la contraseña ni se intentó eludir ese permiso.

### 2026-11-07 — Validación real CU27 y error de registro Firebase
La app llegó correctamente a la bandeja y mostró Firebase Messaging/unknown con FCM Registration failed al pedir el token. Logcat confirmó ese error y SERVICE_NOT_AVAILABLE; Servicios de Google estaban presentes y habilitados, y se comprobó sin publicar valores que app ID, proyecto, remitente y clave pública coincidían con google-services.json. El registro funcionó posteriormente. El usuario aclaró que siempre utilizó Wi-Fi y no tenía datos móviles: no atribuir el fallo a un bloqueo de Wi-Fi ni afirmar que se resolvió cambiando de red. La causa exacta del fallo inicial no quedó demostrada.
Se verificó un único dispositivo activo vinculado al cliente sintético. Se enviaron tres avisos deliberados (IDs 50, 51 y 52), uno por prueba, solo a ese dispositivo; FCM aceptó los tres en un intento. El recuadro se observó en segundo plano y el usuario confirmó apertura de la reserva. Con StyleAR en primer plano se capturó el recuadro sobre el detalle de la reserva de ensayo. Después se llevó la app al inicio de Android, se cerró su proceso con am kill (sin force-stop) y se comprobó ausencia de PID antes del envío; el usuario confirmó que tocar el nuevo aviso inició la app y abrió la misma reserva.
La evidencia conservada de primer plano pertenece únicamente a StyleAR y a datos sintéticos: .private/cu27_primer_plano_1.png. Las capturas que incluían otras pantallas se descartaron y se añadió una comprobación de foco para capturar solo StyleAR. No interpretar recepción como lectura: el aviso de primer plano permanecía sin leer hasta abrirlo.
Se ajusta la interfaz para traducir fallos Firebase a un mensaje comprensible, conservar la bandeja y ofrecer Reintentar activación para la acción push; una prueba cubre que no se expongan java.io ni el código técnico. Los fallos de consulta mantienen su reintento de bandeja.
Pendientes de la revisión final: pantalla bloqueada, permiso/canal denegados, preferencia silenciada en dispositivo, renovación y cambio de cuenta físicos. La aceptación de esos escenarios no se infiere de las tres pruebas anteriores.

Cierre de la incidencia FCM: 83 pruebas Flutter aprobadas con el nuevo caso de mensaje comprensible y análisis sin incidencias. El estado del servidor confirma lectura de los avisos 50 (segundo plano) y 52 (apertura desde proceso cerrado); el aviso 51 recibido en primer plano permanece sin leer, manteniendo la distinción entre recepción y apertura. El registro y las tres recepciones funcionaron con Wi-Fi según aclaración del usuario. Se conserva la API y cuenta de ensayo para la matriz final pendiente; no se retiró la base todavía.

APK release final con manejo comprensible de error Firebase compilado y actualizado en el Redmi conservando datos. La cuenta de ensayo continúa disponible para los escenarios finales pendientes. Las pruebas efectuadas no determinan la causa exacta del fallo inicial del registro de Google.


### 2026-11-07 — Bloque 7: pantalla bloqueada y preparación de R2
El usuario confirmó que el aviso de ensayo apareció con el Redmi bloqueado (aviso 53; envío manual único aceptado por Firebase). Esta confirmación completa ese escenario físico y se suma a primer plano, segundo plano y apertura con proceso cerrado. Permiso/canal denegados, preferencia silenciada y cambio de cuenta/renovación físicos siguen pendientes; no se infieren de la recepción.
El usuario necesita crear una cuenta Cloudflare. Se inicia guía para registro y activación de R2; todavía no se acredita almacenamiento externo ni respaldos reales en R2. No compartir claves por el chat. La configuración debe usar bucket privado y credenciales S3 limitadas al bucket; la clave de cifrado de respaldos debe conservarse de forma estable.


Actualización bloque 7: el usuario desactivó temporalmente el permiso de notificaciones de Android, volvió a StyleAR y confirmó que la bandeja seguía funcionando; después reactivó el permiso. Esto verifica la continuidad de la bandeja con permiso desactivado, sin afirmar un envío físico durante esa desactivación ni una prueba independiente de canal silenciado. También confirmó cuenta Cloudflare creada y acceso al panel; sigue pendiente activar R2 y configurar el bucket y las credenciales.


### 2026-11-07 — Conexión real R2 verificada
El usuario creó stylear-respaldos-local y guardó las variables R2 en .env privado. Se verificó presencia sin mostrar valores. Faltaba boto3 en .venv, aunque requirements.txt ya declara boto3>=1.35,<2; se instaló boto3 1.43.126 y sus dependencias compatibles (la primera descarga agotó tiempo; el reintento terminó correctamente).
STYLEAR_BACKUP_KEY estaba ausente: se generó una clave Fernet y se guardó exclusivamente en .env, sin imprimirla. Conservar esta clave de forma estable y una copia segura para recuperar los respaldos. Se completó una operación real sobre R2 con contenido sintético pequeño: escritura cifrada, descarga, descifrado comparado con el original y eliminación del objeto temporal; todas aprobadas. No se subió la base de trabajo ni información de usuarios. La prueba acredita conexión/credenciales y cifrado, no un respaldo completo ni una restauración real en R2, que siguen pendientes. Se añadieron placeholders de configuración CU25 a .env.example, sin secretos.


### 2026-11-07 — Cierre del bloque 7: R2 completo, regresión y entorno local

- Nuevas pruebas optativas tests/test_cu25_r2_real.py: requieren STYLEAR_TEST_R2_REAL=1, DATABASE_URL igual a STYLEAR_TEST_DATABASE_URL apuntando a una base local stylear_test_*, destino global vacío con prefijo stylear_test_r2_destino_ en STYLEAR_TEST_R2_RESTORE_URL y bucket stylear-respaldos-local. Sin activación explícita no usan R2. Solo se operan y eliminan objetos creados por la ejecución; los assets son sintéticos y están aislados en tmp_path.
- Empresa: respaldo cifrado real en R2, previsualización, modificación de datos y eliminación válida de imagen/referencia, suspensión, copia preventiva, restauración, recuperación exacta de imagen y producto, empresa B intacta y eliminación mediante el servicio. La primera versión del ensayo dejó una referencia a una foto eliminada y el servidor rechazó correctamente una copia preventiva incompleta; se corrigió el escenario para simular una eliminación válida, sin debilitar esa protección.
- Plataforma: pg_dump de una base sintética, cifrado/subida R2, descarga/verificación y pg_restore en otra base inicialmente vacía; empresas verificadas y sesiones/dispositivos desactivados tras restaurar. Dos pruebas reales aprobadas; los objetos temporales se eliminaron y ambas bases se retiraron.
- Regresión PostgreSQL aislada: 48 pruebas aprobadas de test_cu22_cu27_integration.py, test_cu23_cu24_integration.py y test_cu26_planes_integration.py. Se ejecutó init_db.py dos veces en origen para comprobar idempotencia. Advertencias de deprecación existentes no impiden ejecución.
- Nueva regresión CU27 con PostgreSQL y proveedor FCM simulado: renovación del token en la misma instalación, uso del nuevo token, cambio de empresa, omisión de cola anterior, rechazo 404 de destino ajeno, baja tardía de la cuenta anterior sin desactivar la nueva, preferencia silenciada sin cola y con bandeja, desvinculación del propietario actual. Una prueba adicional aprobada; no se enviaron mensajes externos en ella.
- Verificación final de clientes: 33 pruebas web aprobadas; 83 pruebas Flutter aprobadas. pip check sin incompatibilidades. APK release instalado en la validación anterior; este cierre no cambió código móvil ni requiere otro APK. No se repitieron pruebas físicas que requieren manipulación del teléfono; ADB informa dispositivo ausente.
- Base local inspeccionada de forma solo lectura: 18/18 migraciones aplicadas, ninguna pendiente y ningún respaldo R2 previo registrado. No se restauró ni reemplazó esta base.
- Limpieza: detenidos procesos de la fixture CU27 identificados por su comando; ayudante de túnel marcado para detener; base stylear_test_cu27_ui_* eliminada mediante su DSN validado; retirados JSON de fixture/correo y DSN temporal. Se conservan logs/evidencia sintética ignorados por Git. No se borraron fotos de trabajo ni datos del teléfono.
- Arranque final: API normal con .env actual en 127.0.0.1:8000 y Angular de desarrollo en 127.0.0.1:4200, ambos ocultos y con logs privados. Backend health, directorio público (una empresa) y página /empresa devolvieron HTTP 200. Quedan corriendo para pruebas; no se mantiene la API temporal 58127. La app móvil necesita reconexión USB y reverse 8000→8000, más cierre de su sesión temporal y selección de la empresa real.

Conservar STYLEAR_BACKUP_KEY y las credenciales en un respaldo seguro fuera de Git. La clave no se volvió a generar durante las pruebas. BCP sigue condicionado exclusivamente a la entrega de acceso/documentación por el banco; no es correcto sustituirlo por una API inventada ni presentar el modo simulado como pago real.


### 2026-11-07 — Entorno detenido a petición del usuario
Se detuvieron el backend local 8000, Angular 4200 y sus procesos descendientes identificados mediante el registro privado de arranque. Se dejó la señal de parada del ayudante de túnel CU27. No se borraron bases, configuración, credenciales, archivos ni datos del teléfono. Los servidores ya no quedan corriendo; para retomar, usar los comandos de desarrollo local de este mismo documento.
