"""Calendario puro de reportes; reutilizado por API, repositorio y ejecutor."""
from calendar import monthrange
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

DIAS = {nombre: i for i, nombre in enumerate(
    ("LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES", "SABADO", "DOMINGO"))}


def validar_calendario(frecuencia, hora, dia, zona_horaria):
    ZoneInfo(zona_horaria)
    if len(hora) != 5:
        raise ValueError("La hora debe tener formato HH:MM.")
    datetime.strptime(hora, "%H:%M")
    if frecuencia == "SEMANAL" and str(dia).upper() not in DIAS and str(dia) not in {str(i) for i in range(7)}:
        raise ValueError("Indica un día de la semana: LUNES a DOMINGO o 0 a 6.")
    if frecuencia == "MENSUAL":
        try:
            if not 1 <= int(dia) <= 31:
                raise ValueError()
        except (ValueError,TypeError):
            raise ValueError("Indica un día del mes entre 1 y 31.") from None
    if frecuencia not in {"DIARIA","SEMANAL","MENSUAL"}:
        raise ValueError("Frecuencia inválida.")


def proxima_ejecucion(item, despues=None):
    despues = despues or datetime.now(timezone.utc)
    zona = ZoneInfo(item.get("zona_horaria","America/La_Paz"))
    frecuencia,hora,dia=item["frecuencia"],item["hora"],item.get("dia")
    validar_calendario(frecuencia,hora,dia,zona.key)
    local=despues.astimezone(zona)
    h,m=map(int,hora.split(":"))
    fecha=local.date()
    # Encontrar la siguiente ocurrencia estrictamente posterior. En meses
    # cortos, un día 29/30/31 se ejecuta el último día del mes.
    for salto in range(370):
        candidato=fecha+timedelta(days=salto)
        semanal=DIAS.get(str(dia).upper(),int(dia) if str(dia).isdigit() else -1)
        if frecuencia=="SEMANAL" and candidato.weekday()!=semanal:
            continue
        if frecuencia=="MENSUAL" and candidato.day!=min(int(dia),monthrange(candidato.year,candidato.month)[1]):
            continue
        instante=datetime(candidato.year,candidato.month,candidato.day,h,m,tzinfo=zona)
        if instante.astimezone(timezone.utc)>despues:
            return instante.astimezone(timezone.utc)
    raise ValueError("No se pudo calcular la próxima ejecución.")


def periodo_reporte(item, ocurrencia):
    hoy=ocurrencia.astimezone(ZoneInfo(item.get("zona_horaria","America/La_Paz"))).date()
    periodo=item.get("periodo","SEGUN_FRECUENCIA")
    if periodo=="SEGUN_FRECUENCIA":
        periodo={"DIARIA":"DIA_ANTERIOR","SEMANAL":"SEMANA_ANTERIOR","MENSUAL":"MES_ANTERIOR"}[item["frecuencia"]]
    if periodo=="DIA_ANTERIOR":
        fin=hoy-timedelta(days=1)
        return fin,fin
    if periodo=="SEMANA_ANTERIOR":
        fin=hoy-timedelta(days=hoy.weekday()+1)
        return fin-timedelta(days=6),fin
    if periodo=="MES_ANTERIOR":
        fin=hoy.replace(day=1)-timedelta(days=1)
        return fin.replace(day=1),fin
    raise ValueError("Período inválido.")
