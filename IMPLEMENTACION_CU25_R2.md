# CU25: respaldos por empresa con Cloudflare R2

## Configuración de Railway

El backend necesita las seis variables R2 ya configuradas y una clave privada adicional, `STYLEAR_BACKUP_KEY`, para cifrar cada archivo antes de subirlo. Genérala en PowerShell con:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Guarda el resultado como variable secreta en Railway. No la regeneres después de crear respaldos: sin esa misma clave no se pueden descifrar.

## Políticas de referencia por plan

Configura estas claves desde los planes de CU26; el backend también reconoce estos valores predeterminados por código del plan:

| Plan | Respaldos manuales en 7 días | Retención | Frecuencia automática | Hora editable |
| --- | ---: | ---: | --- | --- |
| Básico | 1 | 7 días | Cada 7 días | No, 02:00 Bolivia |
| Intermedio | 2 | 30 días | Diaria | No, 02:00 Bolivia |
| Premium | 5 | 90 días | Diaria | Sí |

Claves de `limites`: `respaldos_manuales_semana`, `retencion_respaldos_dias`, `frecuencia_respaldo_dias`. Claves de `funciones`: `respaldos_automaticos` y `horario_respaldo_configurable`.

## Rutas para administrador de empresa

- `GET /api/v1/respaldos`: lista únicamente los respaldos de la empresa asociada a la sesión.
- `POST /api/v1/respaldos`: crea un respaldo manual, sujeto a la cuota móvil de siete días.
- `GET /api/v1/respaldos/programacion`: devuelve la política y programación automática.
- `PUT /api/v1/respaldos/programacion`: recibe `activa`, `fecha_inicio`, `hora_local` (`HH:MM`) y `zona_horaria`.
- `POST /api/v1/respaldos/{id}/previsualizar` y `POST /api/v1/respaldos/{id}/restaurar`: validan el alcance de empresa. La restauración exige confirmación exacta y genera antes un respaldo preventivo.
- `DELETE /api/v1/respaldos/{id}`: elimina solo un respaldo de esa empresa.

La programación corre dentro del backend cada minuto; un bloqueo de PostgreSQL evita que dos instancias de Railway procesen la misma tarea. Los respaldos se cifran antes de almacenarse en el bucket privado y se guardan bajo un prefijo por empresa. R2 aplica además cifrado administrado en reposo.

## Despliegue

El contenedor ejecuta `init_db.py` antes de iniciar Uvicorn. El script registra y aplica `database/migracion_cu25_respaldos_r2.sql` una sola vez. Si Railway tiene un comando de inicio personalizado, debe conservar ese orden: `python init_db.py` antes de iniciar la API.
