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
