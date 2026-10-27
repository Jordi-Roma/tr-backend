# Corrección de nombres Unicode en CU09

La identidad de nombres de categorías, tallas, colores, marcas, temporadas y
colecciones utiliza ahora una regla compartida entre consultas, validación de
altas/ediciones e índices únicos. No depende de la configuración regional por
defecto de PostgreSQL, incluso cuando es `C`.

## Comportamiento

- `ÚNICA`, `única` y ` única ` identifican el mismo nombre dentro del mismo ámbito.
- Las formas Unicode compuesta y descompuesta de una tilde son equivalentes.
- `Única` y `Unica` continúan siendo distintos; tampoco se confunden `Ñ` y `N`.
- Se conserva el nombre original presentado al usuario y el historial inactivo.
- La identidad continúa por empresa; talla distingue tipo de prenda, temporada
  distingue año y colección distingue temporada.
- Los índices impiden duplicados incluso mediante inserciones SQL concurrentes.

## Migración

`init_db.py` registra `2026_10_27_cu09_unicode_01`, correspondiente a
`database/migracion_cu09_unicode_01.sql`. Se ejecuta una sola vez mediante el
inicializador habitual, incluido el paso previo al despliegue ya configurado.
No ejecutar el SQL manualmente ni insertar la versión en el registro.

Requiere PostgreSQL con UTF8 e ICU. Crea una comparación ICU raíz (`und`) y una
función que recorta espacios, normaliza a NFC y convierte a minúsculas. Los
índices y las consultas comparan esa clave de forma binaria con `COLLATE "C"`.
No cambia la configuración regional general de la base ni elimina acentos.

Antes de sustituir los índices, la migración bloquea las escrituras de las seis
tablas y busca colisiones con la nueva regla. Si encuentra alguna, revierte
todo y detalla tabla, empresa y los IDs afectados. No renombra, fusiona ni borra
datos automáticamente. Deben revisarse esos registros antes de reintentar.

La API comprueba esta versión al iniciar para evitar servir tráfico sobre un
esquema sin la función y sus restricciones. Para instalaciones existentes,
preparar el respaldo habitual antes de ejecutar el inicializador.

## Verificación

Las pruebas se ejecutan exclusivamente sobre bases locales nuevas y desechables
`stylear_test_*`, con `DATABASE_URL` y `STYLEAR_TEST_DATABASE_URL` explícitas e
idénticas. No ejecutarlas sobre la base real del proyecto.

`tests/test_cu09_unicode_integration.py` cubre comparación con `C` e ICU,
normalización de tildes, edición, inactivos, aislamiento entre empresas,
identidades compuestas, consultas por nombre, concurrencia SQL directa,
migración con colisiones, conservación de IDs/referencias y repetición segura
del inicializador. También se conserva la regresión concurrente original de
`tests/test_cu09_integration.py`.

Resultado local del 27/10/2026: 203 pruebas distintas aprobadas por bloques:
22 regresiones originales de CU09 y 23 pruebas Unicode sobre una base con
configuración regional `C`, más 158 pruebas del resto del backend sobre otra
base con ICU. Las pruebas de migración se repitieron después de corregir la
reconstrucción del esquema anterior en su preparación de datos de prueba.

La auditoría de solo lectura sobre los datos locales existentes no encontró
colisiones en las seis tablas. Esa base todavía tiene un esquema anterior a
multitenant: este control no aplica migraciones ni acredita el estado de
producción. No se ejecutaron migraciones sobre la base real del proyecto.
