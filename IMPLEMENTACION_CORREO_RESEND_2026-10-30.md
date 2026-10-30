# Correos con Resend y destino único — StyleAR

Fecha: 30 de octubre de 2026.

## Qué quedó implementado

El backend puede enviar por la API HTTPS de Resend, compatible con Railway Hobby.
Los códigos de recuperación (empresa y administrador SaaS) y las notas de venta
PDF pasan por el mismo servicio. Con `MAIL_TO_OVERRIDE`, todos se dirigen a una
única cuenta; no se envían copias al correo del cliente. No se modifican los
correos registrados en la base.

El PDF conserva la empresa, sucursal, numeración y datos de la venta. La empresa
figura como nombre visible del remitente y `onboarding@resend.dev` como dirección
técnica. En destino fijo también se puede enviar la nota de una venta sin correo
de cliente. Antes del envío se mantienen los permisos de empresa y sucursal.

Las respuestas de recuperación y la bitácora informan el destino configurado,
sin publicar su dirección. El aviso inicial de Flutter ahora es neutral; la
pantalla muestra después el mensaje del backend. Angular ya consume esa respuesta;
solo se ajustó el texto accesible del botón de envío para indicar «por correo».

Si Resend falla, el backend no vuelve a SMTP ni al correo del cliente. Responde
503 sin exponer claves, códigos o el cuerpo del error del proveedor. La venta y
su PDF permanecen disponibles. Recuperación permite volver a solicitar después
del límite existente de un minuto. No se agregaron reintentos automáticos de
envío: tras un timeout, el proveedor podría haber aceptado ya el mensaje.

## Configuración en Railway

Primero subir estos cambios del backend. En el servicio **backend**, abrir
**Variables** y agregar estas cuatro variables por separado:

| Variable | Valor |
| --- | --- |
| `MAIL_PROVIDER` | `resend` |
| `RESEND_API_KEY` | La llave creada en Resend; pegarla directamente en Railway |
| `RESEND_FROM` | `StyleAR <onboarding@resend.dev>` |
| `MAIL_TO_OVERRIDE` | El Gmail exacto con el que se registró la cuenta de Resend |

Guardar los cambios y desplegar el backend para que los cargue. La clave no
debe ir en el frontend, en Flutter, en archivos versionados ni en capturas.

Para pruebas locales se usan las mismas variables en `tr-backend/.env`, que ya
está excluido de Git. No se modificó ese archivo privado durante esta tarea.
`.env.example` documenta las variables sin incluir secretos ni una dirección real.

Sin `MAIL_PROVIDER`, el valor predeterminado sigue siendo `smtp` para conservar
la configuración anterior. Elegir `resend` exige clave, remitente y destino fijo;
una configuración incompleta bloquea el envío. Las variables antiguas de SMTP
no intervienen cuando se selecciona Resend.

## Alcance del modo de demostración

`resend.dev` permite enviar mensajes de prueba solamente a la dirección asociada
a la cuenta de Resend. No hace falta verificar un dominio propio para estas
pruebas. Para enviar a otros destinatarios después se deberá verificar un dominio
y revisar expresamente el destino fijo.

Todos los códigos llegan al dueño de esa bandeja; los clientes no reciben sus
propios códigos mientras esté activado este modo. La recuperación sigue ligada
a la cuenta y empresa originales; cambiar el destino no cambia de quién es el
código ni habilita recuperaciones entre empresas.

El registro de empresas continúa sin verificación real de correo y con
aprobación manual del administrador SaaS. Los reportes programados no envían
correo automáticamente: eso no forma parte de esta integración.

## Comprobación funcional después del despliegue

1. Solicitar recuperación para una cuenta propia de prueba; comprobar la llegada
   del código al Gmail central y usarlo en esa misma cuenta/empresa.
2. En una venta autorizada existente, enviar la nota; comprobar la llegada del
   PDF y los datos de su empresa. No hace falta crear una venta para la prueba.
3. Revisar Resend → Emails para distinguir aceptación, entrega o rechazo.

La implementación se verificó con respuestas controladas del proveedor, sin
enviar mensajes reales ni tocar la base de negocio. La llegada real queda
pendiente de introducir la llave y desplegar.

Resultado local: **69 pruebas aprobadas**, incluidas **35 pruebas de correo**.
Se omitieron 10 módulos de integración que requieren PostgreSQL desechable; no
se ejecutaron contra la base real. Se verificó el formato de la pantalla Flutter
modificada y la ausencia de errores de espacios en los tres repositorios.

No se requieren migraciones ni nuevas dependencias: se utiliza `requests`, ya
incluido. No se modificaron el vestidor, la confirmación QR ni el historial.

## Referencias

- [Resend: envío por API](https://resend.com/docs/api-reference/emails/send-email).
- [Resend: adjuntos](https://resend.com/docs/dashboard/emails/attachments).
- [Resend: restricción del dominio de prueba](https://resend.com/docs/knowledge-base/403-error-resend-dev-domain).
- [Railway: SMTP y APIs HTTPS](https://docs.railway.com/networking/outbound-networking).
