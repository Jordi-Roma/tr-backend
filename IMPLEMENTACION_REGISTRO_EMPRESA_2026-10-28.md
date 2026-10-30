# Registro público de empresas — StyleAR

Fecha: 28/10/2026. Alcance: backend y web, dentro de CU01 y CU26. No requiere
pantallas Flutter, porque el alta y la administración SaaS corresponden a web.

## Decisión final

El visitante puede solicitar su propia empresa. **No hay verificación de correo,
códigos, enlaces de confirmación ni acceso de prueba automático**. El correo se
valida por formato y se conserva como contacto, sin atribuirle una verificación.
El administrador SaaS debe aprobar el acceso.

## Recorrido

1. En el directorio se muestra «Crear mi empresa», que abre `/crear-empresa`.
2. Se muestran solamente planes activos publicados expresamente por el AS.
3. El responsable elige plan e ingresa empresa, identificador público, nombre,
   apellido, usuario, correo y contraseña con confirmación.
4. En una transacción se crean la empresa, la suscripción solicitada, su
   administrador y el registro de la solicitud. Empresa y suscripción quedan
   `PENDIENTE`. No se inicia sesión ni se envía correo.
5. La empresa pendiente no aparece en el directorio y no permite iniciar sesión,
   consultar catálogo público ni crear clientes comerciales.
6. El AS revisa el contacto **sin verificar**, el plan y la vigencia. El botón
   «Aprobar y activar empresa» activa empresa y suscripción en una transacción y
   conserva la suscripción pendiente como historial cancelado.
7. La empresa aprobada aparece en el directorio y su administrador puede ingresar.
   Si el AS cancela una solicitud pendiente, empresa y suscripción quedan
   canceladas sin borrar la solicitud, la cuenta ni la auditoría.

La cuenta creada tiene exclusivamente el rol `ADMINISTRADOR` de su empresa.
Ningún campo público permite asignar `ADMIN_SAAS`, permisos, otra empresa,
estados activos ni fechas de suscripción. Se conserva la regla existente de
usuarios y correos únicos globalmente; no se reutilizan ni se elevan cuentas
anteriores para registrar otra empresa.

## Planes

El AS dispone de la opción «Disponible en el registro de empresas». Los planes
existentes conservan sus cuotas, funciones y suscripciones, y empiezan privados.
El plan de transición `STYLEAR_LEGADO` no puede publicarse. Un plan público debe
permitir al menos la cuenta administradora inicial. No se generan planes de
prueba ni se inventan precios o un cobro de suscripción.

Si no hay planes publicados, la página informa que no puede solicitarse el alta
y ofrece actualizar la lista. La aprobación permite al AS confirmar o cambiar
el plan y definir su fecha de inicio y vencimiento.

## Integridad y acceso

- Se validan longitudes, identificador público, formato de correo, usuario y
  contraseña; esta última se guarda con el mecanismo bcrypt existente.
- Se rechazan campos adicionales de privilegios o estado.
- La web envía las solicitudes por un cliente público separado: no adjunta la
  sesión ni el contexto de otra empresa abierta y no modifica esa sesión.
- Una clave UUID y una huella HMAC permiten reintentar una respuesta perdida
  sin duplicar empresa, cuenta o suscripción. Cambiar el contenido con la misma
  clave se rechaza. El cliente conserva la clave en memoria durante el intento;
  no guarda contraseñas en almacenamiento del navegador.
- La API limita a 20 altas por origen por hora, con control en PostgreSQL para
  varias réplicas. El origen se conserva mediante HMAC, sin guardar la IP literal.
- Se conserva la auditoría del alta pública, la aprobación y la cancelación.
- Las solicitudes pertenecen a la plataforma. Se excluyen del alcance comercial
  de los respaldos selectivos y se incluyen en el respaldo global.

## API y migración

- `GET /api/v1/empresas/registro/planes`: planes públicos; no expone datos de AS.
- `POST /api/v1/empresas/registro`: solicitud pública pendiente.
- La gestión AS reutiliza `/api/v1/saas/planes` y
  `/api/v1/saas/empresas/{id}/suscripcion`, con autorización de plataforma.
- No se puede aprobar una empresa pendiente cambiando solo su estado: exige
  asignar una suscripción válida. La cancelación sí se permite desde su estado.

Migración versionada: `2026_10_28_registro_empresa_01`, registrada en `init_db.py`.
Agrega la publicación de planes, los estados pendientes y la tabla de solicitudes.
No cambia contraseñas, roles, datos comerciales ni suscripciones existentes.
Se aplica con el inicializador habitual y se comprueba al arrancar la API.

## Cuenta del administrador SaaS

No existe usuario o contraseña predeterminados. El registro público nunca crea
este rol. La herramienta privada existente es:

```powershell
python -m app.modules.administracion.bootstrap_admin_saas
```

Se utiliza únicamente con `DATABASE_URL` apuntando explícitamente a la base
correcta y actualizada. Solicita identidad y contraseña de forma interactiva,
no muestra la contraseña y rechaza crear otro AS si ya existe uno activo.
No se ejecuta automáticamente en despliegues ni forma parte del registro público.
Si ya existe una cuenta, se usa `/saas/login` y su recuperación de contraseña.
En este trabajo no se crea un AS real ni se cambia su contraseña.

## Verificación y entrega

Las pruebas se ejecutan exclusivamente en PostgreSQL local desechable. No se
aplica esta migración a la base real ni se hacen commit, push o despliegue.
Se conserva el probador, el flujo QR, las imágenes previas del backend y el
stash móvil. El registro no requiere SMTP; la recuperación de acceso y los
comprobantes siguen usando sus mecanismos de correo existentes.

## Resultados comprobados

- **241 pruebas backend aprobadas**, incluidas 18 del registro público y la
  regresión de multitenant, cuentas, permisos, respaldos y operaciones previas.
- Revisión final focalizada de reintentos después de aprobación/cancelación:
  dos pruebas aprobadas, con mensajes coherentes con el estado actual.
- Migración aplicada correctamente en bases nuevas. Al repetir el inicializador,
  reconoce la versión aplicada y conserva los datos sin volver a ejecutar el SQL.
- **16 pruebas unitarias Angular aprobadas**.
- **7 recorridos de navegador distintos aprobados**, comprobados en tandas:
  cuatro del registro y tres previos de directorio, administración SaaS y teclado.
  Incluyen AXE y revisión del formulario completo en escritorio y pantalla estrecha.
- Los siete archivos locales previos del backend conservan sus hashes. Flutter
  permanece sin cambios y se conserva su stash anterior.

Entrega local: no se hizo commit, push ni despliegue de este bloque. El AS debe
publicar al menos un plan desde su panel para habilitar las solicitudes reales.
Las empresas y planes de prueba existen solo en bases desechables de pruebas.

La compilación final de producción de Angular terminó correctamente. Los avisos CommonJS de leaflet y qrcode son de dependencias existentes.
