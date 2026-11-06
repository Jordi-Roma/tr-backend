# CU22 y CU27 — mejoras del backend

Implementación del alcance de servidor de `PLAN_MEJORAS_CU22_CU27.md`. Se ampliaron Inteligencia, Ventas e Inventario y los productores de eventos de Reservas; se reutilizaron los controles de Administración y Autenticación. No se crearon módulos nuevos.

## CU22: consultas y métricas

- `POST /api/v1/reportes/dashboard`: resumen, serie de ventas, productos más vendidos, reservas y existencias bajas. Acepta `fecha_desde`, `fecha_hasta`, `sucursal_id` opcional, `tipo_venta` opcional (`PRESENCIAL` o `DIGITAL`) y `comparar` (predeterminado `true`). DIGITAL corresponde a WEB en las tablas existentes.
- El período anterior tiene igual cantidad de días y termina el día anterior al inicio solicitado. Se devuelven ambos valores, diferencia absoluta y porcentaje. Con base anterior cero, el porcentaje es `null` y el motivo es `BASE_ANTERIOR_CERO`.
- Ambos períodos se consultan en una misma transacción de lectura con aislamiento repetible. El inventario se informa como estado actual, sin comparación histórica.
- Ventas: registros activos COMPLETADA por fecha de venta, sin duplicar ventas por sus órdenes. `importe_vendido` suma el campo `venta.total` existente, en BOB; no representa utilidad. En una reserva finalizada, ese total ya descuenta el anticipo aplicado, conforme al registro comercial existente.
- Cobros: órdenes con pago recibido o confirmado, incluidas las que posteriormente requirieron reembolso. Se usa fecha de pago; para registros antiguos sin ella se usa actualización y luego creación. En caja presencial se añade únicamente el saldo no representado en órdenes pagadas, sin volver a sumar el anticipo que el registro de venta ya descontó.
- Reembolsos: confirmaciones de `reembolso_pago` y devoluciones/cambios efectivamente reembolsados, por fecha de confirmación. Si un mismo reembolso aparece en ambas fuentes, coincidiendo venta, moneda y referencia, se conserva la devolución. No se fusionan referencias de ventas distintas ni varios recibos de una misma fuente.
- Neto: cobros del período menos reembolsos del período; cada moneda se presenta separadamente. Los importes exactos nuevos se devuelven como texto decimal.
- El filtro de canal afecta ventas y flujos monetarios. Reservas e inventario usan empresa y sucursal; no se les atribuye un canal que no existe en su registro.

## Acceso y paginación

Administrador: su empresa. Encargado: solo su sucursal activa asignada; omitirla aplica automáticamente esa sucursal y solicitar otra devuelve 403. Catálogo, interpretación, generación, detalle, dashboard y exportaciones respetan el alcance. USUARIOS y la gestión de programaciones quedan reservados al administrador. SaaS y clientes no acceden a los reportes comerciales mediante estas rutas.

Los permisos de PDF, Excel, interpretación, voz y programación siguen sujetos a CU26. La consulta básica se conserva cuando vence la suscripción.

`POST /api/v1/reportes/detalle` admite los filtros de generación, `pagina` desde 1 y `tamano` de 1 a 500 (predeterminado 100). Devuelve filas de la página, total completo, resumen completo y gráfico del resultado completo, con orden estable. La consulta usa un límite de ejecución de 15 segundos. Las fechas conservan el límite vigente de 366 días de diferencia.

Se mantienen las rutas antiguas y sus exportaciones. Admiten hasta 5.000 filas completas; si hay más, devuelven 422 indicando usar paginación o reducir el período. No se genera un archivo truncado. Las órdenes de pago se presentan como importes nominales, separados por moneda, sin confundirlos con cobros. En un detalle con varias monedas, `resumen.importe` es `null` y `resumen.importes_por_moneda` contiene cada importe.

## Editar una programación

`PATCH /api/v1/reportes/programados/{id}`:

```json
{
  "revision": 1,
  "cambios": {
    "titulo": "Ventas semanales",
    "frecuencia": "SEMANAL",
    "dia": "LUNES",
    "hora": "09:00"
  }
}
```

Usar la `revision` que devuelve el listado vigente. Los nombres y valores de frecuencia/día se validan con el calendario existente; consultar el esquema de la API para sus valores admitidos. Se pueden modificar los campos del esquema de creación, incluidos filtros, destinatario, período, formato, sucursal y estado. No se permite modificar empresa, identificador ni historial.

Se conserva una pausa si no se solicita activación. Activar comprueba cupo, plan y formato. La edición recalcula la próxima ejecución y aumenta revisión; una revisión obsoleta devuelve 409. El envío conserva su ocurrencia y revisión intentadas; revalida antes de generar y bloquea la configuración durante el envío. Cambios de plan y pausas también aumentan revisión. El historial se conserva y no se reenvía automáticamente una ocurrencia cuyo resultado haya quedado incierto.

## CU27: bandeja y navegación

Se conserva `GET /api/v1/notificaciones` (lista antigua de hasta 100 avisos) y las rutas existentes de dispositivos y lectura individual. Nuevas rutas:

| Método y ruta bajo `/api/v1/notificaciones` | Resultado |
| --- | --- |
| GET `/bandeja` | `pagina`, `tamano` (1–100), `leida` y `categoria` opcionales; total filtrado, contador global no leído y página ordenada por identificador descendente |
| GET `/resumen` | Total y no leídas del usuario y empresa actuales |
| PATCH `/leer-todas` | Marca únicamente avisos propios; devuelve cuántos cambiaron |
| GET `/preferencias` | Categorías push habilitadas y estado de bandeja |
| PUT `/preferencias` | Actualización parcial mediante `{"categorias":{"COMPRA":false}}` |
| GET `/{id}/destino` | Destino permitido y nuevamente autorizado, o `ABRIR_BANDEJA` si ya no es accesible |
| GET `/{id}/estado` | Persistencia, salidas pendientes/fallidas/omitidas, aceptaciones FCM y lectura |

Categorías: GENERAL, COMPRA, PAGO, RESERVA, ENTREGA, CAMBIO, DEVOLUCION y REEMBOLSO. Al silenciar push, los avisos transaccionales siguen guardándose en la bandeja. Las preferencias son por empresa y usuario; no controlan el permiso de Android.

Destinos admitidos: VENTA, ORDEN_PAGO, RESERVA, DELIVERY, CAMBIO y DEVOLUCION. El identificador del mensaje no autoriza el recurso. Se vuelve a comprobar empresa y propiedad del cliente. No se aceptan enlaces arbitrarios ni se devuelven tokens de dispositivos.

Los eventos usan la transacción de la operación y una clave estable por evento. Se conservaron los productores de compra/pago, entrega y posventa; se añadieron avisos de creación, avance, cancelación, vencimiento, anticipo y finalización de reservas. Cambios y devoluciones se distinguen mediante su tipo real. Repetir una operación confirmada no duplica su aviso.

## Cola y Railway

El proceso de API existente atiende ahora la cola push cada 10 segundos en segundo plano; el contenedor actual sigue iniciando migraciones y API. No se necesita un proveedor nuevo ni otra variable propia de CU22/CU27.

Se reutilizan `STYLEAR_FIREBASE_PROJECT_ID` y `STYLEAR_FIREBASE_CREDENTIALS`. Sin configuración, se conserva la cola pendiente. También se mantiene el comando opcional existente:

```text
python -m app.modules.ventas_inventario.services.push_worker --continuo
```

Varios trabajadores comparten la cola mediante bloqueos de filas y SKIP LOCKED. Antes de enviar se verifican usuario, empresa, instalación, sesión, versión de acceso, preferencia y caducidad. Los fallos reintentan después de 30, 60, 120 y 240 segundos; se conserva el máximo de cinco intentos. Un token retirado se desactiva. Los avisos nuevos caducan para envío después de 24 horas. No se guardan respuestas sensibles en errores.

FCM Android: prioridad HIGH, TTL de 24 horas, canal `stylear_transacciones_v1`, etiqueta distinta por empresa/notificación, título y texto genéricos para privacidad, e identificadores de notificación/empresa en datos. ENVIADO significa aceptado por FCM; no acredita aparición en el teléfono. La respuesta de trazabilidad lo indica expresamente. Un timeout del proveedor puede tener resultado incierto: la aplicación deberá deduplicar por identificador.

CU25: restaurar invalida sesiones e instalaciones y convierte las salidas pendientes/fallidas recuperadas en OMITIDO para evitar reproducir avisos históricos. Se conservan preferencias y lectura recuperadas, sin alterar otra empresa.

## Migración y validación

Nueva migración registrada: `2026_11_06_cu22_cu27_mejoras`, archivo `database/migracion_cu22_cu27_mejoras.sql`. Debe ejecutarse con `init_db.py` antes de servir la API; el inicio verifica que esté aplicada. Amplía notificaciones, cola y revisiones de reportes, agrega preferencias e índices y clasifica eventos anteriores reconocibles. No modifica migraciones desplegadas.

Pruebas: esquemas y porcentajes, payload FCM simulado, SQL real de todos los detalles, 5.200 ventas y totales completos, monedas separadas, reembolsos sin duplicar, alcance del encargado, edición concurrente, transacciones de bandeja, preferencias, navegación, reintentos, cola concurrente y restauración con R2 simulado. Se ejecutan exclusivamente sobre PostgreSQL local desechable indicado por `STYLEAR_TEST_DATABASE_URL`, igual a `DATABASE_URL` y con nombre `stylear_test_*`. Firebase/correo/R2 se simulan; no se envían mensajes reales.

Resultado local: **68 pruebas distintas aprobadas** en lotes. El conjunto principal pasó 51 pruebas; las comprobaciones adicionales y regresiones de reservas, pagos, cambios y devoluciones pasaron 16; se añadió y aprobó una comprobación de compatibilidad del reporte monetario vacío (incluida en un lote de 12 pruebas unitarias repetidas). La migración se aplicó desde cero y se verificó su repetición mediante el registro de versiones. Compilación de Python y `git diff --check` correctos. Las advertencias de pruebas corresponden a APIs de dependencias en desuso; no hubo fallos pendientes.

## Pendiente de una fase posterior

Integrar web y Flutter con estos contratos. El APK necesita crear el canal con importancia alta, permiso de notificaciones, presentación local en primer plano y navegación al tocar el aviso. Se debe probar una compilación de distribución en teléfono físico en primer plano, segundo plano, inicio desde aviso y pantalla bloqueada. El backend preparado no acredita todavía el recuadro emergente Android solicitado. No se realizaron despliegues ni commits de esta implementación.
