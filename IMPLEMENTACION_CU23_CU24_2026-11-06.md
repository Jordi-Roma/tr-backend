# CU23 y CU24 — mejoras del backend

Implementación de `PLAN_MEJORAS_CU23_CU24.md`. Se ampliaron los archivos existentes de Inteligencia, con ajustes compartidos de Catálogo, continuidad de consultas y la constante de vigencia de Reservas. No se crearon módulos nuevos ni se modificaron web o Flutter.

## CU23: correcciones concretas

- Las recomendaciones revalidan las variantes disponibles y con precio, según talla y sucursal. El importe mostrado ya no puede proceder de una variante agotada más barata.
- Las sugerencias iniciales excluyen también favoritos/compras usados como semillas cuando no hay vectores. No repiten productos.
- La elección de candidatos usa una consulta de IDs y metadatos, limitada a 2.000 productos activos disponibles, con orden estable por stock e ID. Sustituye la construcción de hasta 500 fichas completas y permite considerar productos que antes quedaban fuera de esa primera selección. Sigue siendo una selección acotada, no una promesa de clasificación exhaustiva de catálogos mayores.
- Solo se cargan embeddings de los candidatos y semillas necesarios para la consulta personal o contextual. No se indexa automáticamente al recomendar.
- Se descartan vectores vacíos, no finitos, de norma cero o dimensiones incompatibles; si no hay un perfil utilizable, se conservan sugerencias iniciales identificadas como tales.
- Los motivos distinguen personalización y sugerencias iniciales; el score no es una probabilidad de compra.
- `usar_historial=false` conserva la lista personal vacía. El chatbot también lo respeta e informa que la personalización está desactivada. El cliente puede consultar sus favoritos propios.

### Separación de índices

La clave del índice es ahora `PROVEEDOR:MODELO`, dentro de la columna existente. Los vectores anteriores sin proveedor explícito no se reutilizan suponiendo su origen. Mientras no exista un índice compatible, funciona el fallback.

No se ejecutó indexación externa ni se generaron embeddings de pago. La ruta existente `POST /api/v1/recomendaciones/indexar`, reservada al administrador, sigue disponible para una indexación deliberada posterior con el proveedor configurado. El campo informativo `modelo` de su respuesta conserva el nombre del modelo.

## CU24: consultas ampliadas

Se conserva `POST /api/v1/asistente/chat`, tanto para visitantes con `X-Empresa-Codigo` como para usuarios autenticados de esa empresa.

### Catálogo e información pública

- Productos y variantes con descripción, material, talla, color, sucursal e identificación real.
- Precio vigente, precio final exacto en BOB y promoción aplicable según sucursal. La búsqueda utiliza `precio_catalogo()` y la promoción vigente de la fuente compartida del catálogo.
- Precios superpuestos ya no duplican stock o seleccionan un precio antiguo en la ficha de catálogo: se elige el precio vigente más reciente, igual que en la función comercial existente.
- Stock utilizable por variante/sucursal, con aclaración de que consultar no aparta unidades.
- Búsqueda por precio final promocionado y consulta de promociones disponibles.
- Distinción de variante no publicada, ausencia de stock y precio no disponible cuando existe una prenda seleccionada. «Sin coincidencias» no se presenta como inexistencia de todo el producto.
- Alternativas señaladas expresamente como posibles resultados que no cumplen todos los filtros iniciales.
- Sucursales con dirección, ciudad y teléfono publicados. Los horarios no existen como fuente mantenida en este alcance; el asistente lo explica y ofrece el contacto disponible.
- La búsqueda reconoce nombres de sucursal de la empresa y normaliza acentos; la talla se compara de forma exacta para evitar confundir S con XS.

Los datos textuales de material, descripción y marca se consultan también desde el producto seleccionado, aunque no tenga stock. No se inventan atributos faltantes.

### Políticas y ayuda

El asistente consulta la política real de cambios y devoluciones de la empresa: habilitación, plazo y condiciones. Explica el proceso sin aprobar solicitudes.

La ayuda de pagos usa los medios digitales realmente habilitados y el modo configurado. No ofrece Stripe o QR como universales ni presenta una simulación como dinero real.

La explicación de reservas reutiliza `DIAS_RESERVA_GRATUITA`, compartida con la creación y validación de citas del repositorio de Reservas. El comportamiento sigue siendo gratuito y de siete días; los anticipos históricos conservan su información propia.

Para delivery se explica que costo y tiempo deben salir del checkout/cotización vigente. El chat no crea cotizaciones ni inventa tarifas, rutas o horas de llegada.

### Operaciones personales

Con sesión válida y cliente de la empresa, se consultan proyecciones acotadas de:

| Recurso | Información permitida |
| --- | --- |
| RESERVA | Código, estado registrado, cita, vencimiento, importe y sucursal |
| VENTA | Compra propia, fecha, estado, importe, moneda y sucursal |
| ORDEN_PAGO | Pago propio, concepto, estado, fecha e importe/moneda |
| DELIVERY | Entrega propia, estado, sucursal y estimación/entrega registrada si existe |
| CAMBIO | Estado del cambio, diferencia y política guardada de la operación |
| DEVOLUCION | Estado, importe aprobado/de reintegro, fecha de reembolso y política guardada |
| REEMBOLSO_PAGO | Estado propio del reembolso, fecha e importe/moneda |

Las consultas privadas filtran simultáneamente empresa y cliente derivado del usuario. No heredan permisos administrativos globales del chat. Un código o ID ajeno no permite consultar otro cliente.

Se muestran hasta cinco operaciones recientes y se pide precisar una si hay varias. La respuesta añade `hay_mas` cuando se alcanza el exceso consultado. No se publican direcciones privadas de entrega, correos, notas internas, tokens, checkout URLs o credenciales.

En reembolsos se distingue el estado y el indicador `reembolso_confirmado`. Aprobación o trámite pendiente no se presentan como dinero devuelto. Un seguimiento desde un pago consulta el reembolso de ese pago, no otro con identificador coincidente. Para un número ambiguo entre fuentes se pide aclaración.

Las condiciones de una devolución/cambio en curso se toman de los campos públicos de su snapshot al consultar esa operación. Las preguntas generales reciben la política vigente de la empresa.

## Contrato compatible y contexto

Las respuestas conservan `respuesta`, `tipo`, `productos`, `alternativas`, `acciones`, `filtros_detectados` y `requiere_login`.

Campos añadidos:

- `fuentes`: etiquetas comprensibles de las fuentes consultadas.
- `consultado_en`: momento de consulta.
- `datos`: proyecciones estructuradas de sucursales, políticas u operaciones propias.
- `contexto`: selección y filtros breves para la siguiente pregunta.
- `aclaracion`: indica que falta identificar una prenda u operación.
- `hay_mas`: indica que la lista está limitada.

Las prendas añaden `variante_id`, `sucursal_id`, `precio_final`, `precio_final_exacto`, `moneda`, `descripcion`, `material`, `promocion` y `motivo` cuando corresponda. Se mantiene `precio_vigente` con su significado anterior; las aplicaciones deberán usar el precio final para mostrar el descuento.

Ejemplo de consulta pública:

```json
{
  "mensaje": "¿Tienen esta prenda en M y azul en Centro?",
  "contexto": {"producto_id": 123}
}
```

Los números son ilustrativos: usar un producto real de la empresa. Para continuar, reenviar el `contexto` devuelto y cambiar el mensaje a «¿y en negro?».

El contexto admite empresa, producto, variante, sucursal, recurso/tipo, términos y filtros acotados. Si se suministra una variante sola, se resuelve su producto real; si producto y variante no coinciden, se rechaza la combinación. Se comprueban de nuevo pertenencia y autorización en cada pregunta. Cambiar cuenta o empresa no conserva el acceso a una operación anterior.

Los tipos de recursos son los enumerados en la tabla anterior; tipo e ID deben enviarse juntos. No se admiten campos arbitrarios como `usuario_id`, mensajes de sistema o historiales completos. No se guardan conversaciones permanentemente.

Las solicitudes anteriores sin contexto o con solo producto/sucursal continúan siendo válidas. Los nuevos campos deben integrarse en web y Flutter en una fase posterior; no se afirma que esas aplicaciones ya los representen.

## Autenticación, solo lectura y proveedores

El acceso opcional del asistente reutiliza `obtener_usuario_actual()` cuando hay credenciales. Esto incluye versión de acceso, usuario activo, sesión vigente y empresa. Un token presentado pero inválido/revocado ya no se transforma silenciosamente en visitante. Sin token, las consultas personales piden ingreso.

La ruta de chat se considera una consulta para las reglas de continuidad, manteniendo la atención de operaciones propias cuando la empresa está suspendida o la suscripción vence. No ejecuta nuevas operaciones comerciales.

Las proyecciones de operaciones se ejecutan con transacción READ ONLY y límite SQL de cinco segundos. En particular, consultar reservas no llama a los listados que ejecutan vencimientos como efecto secundario: muestra el estado y fechas registrados y deja las transiciones al proceso correspondiente.

Los hechos se redactan mediante plantillas del servidor. Se evita la redacción libre sobre precios, stock, importes y estados, y los datos privados no se envían al modelo.

El intérprete público existente usa Vertex/Gemini solo si el selector lo indica. Su salida se reduce a tipos públicos y filtros validados/acotados; no puede elegir empresa, usuario, SQL o permisos. RULES funciona sin llamadas externas aunque exista `OPENAI_API_KEY`. Se eliminó la ruta incidental que llamaba a OpenAI para redactar por el mero hecho de existir una clave; no se añadió un proveedor nuevo. Proveedores no utilizados o respuestas erróneas conservan el fallback por reglas.

Se evitan llamadas al intérprete cuando el mensaje contiene patrones evidentes de credenciales/correo. El cliente de interpretación tiene timeout de diez segundos, un intento y salida limitada a 600 tokens. No se registran respuestas sensibles ni excepciones internas en el mensaje del usuario.

La ruta aplica una protección técnica de 60 solicitudes por minuto y origen observado, con memoria acotada a 4.096 orígenes por proceso; devuelve 429 y Retry-After. No es una cuota de plan ni un límite global distribuido. Se utiliza el origen de la conexión, sin confiar directamente en un X-Forwarded-For proporcionado por el cliente; su alcance depende de la configuración de proxies del despliegue.

## Base de datos y despliegue

CU23/CU24 no necesitaron migraciones ni nuevas variables de entorno. Se conserva el esquema existente, incluida la columna del modelo para distinguir índices. La prueba local aplicó las migraciones existentes mediante `init_db.py` en una base nueva desechable.

No se ejecutaron llamadas reales de IA, indexaciones externas, envíos de correo, commits ni despliegues. Los cambios locales anteriores de CU22/CU27 y los archivos ajenos se conservaron.

## Verificación y límites

Pruebas con proveedores simulados y PostgreSQL local desechable: precio promocionado y filtro de presupuesto, precios superpuestos sin duplicar stock, disponibilidad reservada, material real, contexto de variantes y empresas ajenas, políticas/medios de pago, consultas privadas de todos los recursos, reservas sin ejecutar vencimientos, preferencias, reembolsos pendientes/confirmados, snapshot, candidatos fuera de los primeros 500 y autenticación revocada. También se verificaron los contratos, vectores incompatibles, RULES, fallback del intérprete y protección técnica.

Resultado: **59 pruebas distintas aprobadas**, ejecutadas en lotes. Un lote de 52 cubrió CU23/CU24, recomendaciones, catálogo/reservas, un control de CU26 y la suite de cuenta; otro lote de 36 revalidó las funciones nuevas y añadió reportes y controles de CU22/CU27. Un cierre de 23 pruebas revalidó la ayuda de delivery y añadió una prueba de normalización de preguntas. Los lotes comparten pruebas; la cifra de 59 no suma repeticiones. Compilación de Python y `git diff --check` correctos. Las advertencias observadas corresponden a dependencias y al ciclo de vida de FastAPI ya usado en el proyecto.

La implementación usa clasificación por reglas con interpretación pública opcional, no comprensión ilimitada de cualquier formulación. Cuando falta una identificación inequívoca, pide aclaración o no encuentra coincidencias; no se promete resolver preguntas arbitrarias. No aprueba operaciones, no asegura stock futuro ni garantiza una entrega bancaria o un plazo de delivery.

Pendientes de otra fase: conectar las interfaces web y Flutter con los campos estructurados/contexto y probar la experiencia completa. No se acreditó funcionamiento de un proveedor real de IA con credenciales de producción.
