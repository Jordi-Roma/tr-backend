"""Validaciones reutilizables de suscripcion y funciones por empresa."""

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from psycopg2.extras import RealDictCursor

from app.database.connection import get_connection

LIMITES_ADMITIDOS = {
    "usuarios", "empleados", "productos", "sucursales",
    "respaldos_manuales_semana", "retencion_respaldos_dias", "frecuencia_respaldo_dias",
    "reportes_programados",
}
FUNCIONES_ADMITIDAS = {
    "recomendaciones", "asistente", "reportes", "vestidor",
    "respaldos_automaticos", "horario_respaldo_configurable",
    "reportes_pdf", "reportes_excel", "reportes_interpretacion", "reportes_voz",
    "reportes_programacion", "respaldos_manuales",
}

# Todas las escrituras que consumen cupo y las ediciones de planes comparten
# este cerrojo. La edición exclusiva espera a las operaciones ya iniciadas.
LOCK_PLANES = 2026110526
FUNCIONES_LIBRES = {"reportes", "recomendaciones", "asistente", "vestidor"}
CAPACIDADES = {
    "reportes_pdf": ("Exportar PDF", "Reportes", []),
    "reportes_excel": ("Exportar Excel", "Reportes", []),
    "reportes_interpretacion": ("Consultas en lenguaje natural", "Reportes", []),
    "reportes_voz": ("Consultas por voz", "Reportes", ["reportes_interpretacion"]),
    "reportes_programacion": ("Programar y enviar reportes", "Reportes", []),
    "respaldos_manuales": ("Crear respaldos manuales", "Administración", []),
    "respaldos_automaticos": ("Crear respaldos automáticos", "Administración", []),
    "horario_respaldo_configurable": ("Elegir horario de respaldo", "Administración", ["respaldos_automaticos"]),
}
LIMITES_CATALOGO = {
    "usuarios": ("Usuarios activos, incluidos clientes y personal", "cuentas", 1),
    "empleados": ("Empleados activos; su cuenta también consume un usuario", "empleados", 0),
    "sucursales": ("Sucursales activas", "sucursales", 1),
    "reportes_programados": ("Programaciones activas", "programaciones", 0),
    "respaldos_manuales_semana": ("Respaldos manuales en los últimos siete días", "copias/7 días", 0),
    "retencion_respaldos_dias": ("Retención para copias nuevas", "días", 1),
    "frecuencia_respaldo_dias": ("Intervalo entre copias automáticas", "días", 1),
}


def catalogo_capacidades():
    descripciones={
        'reportes_pdf':'Descargar reportes listos para imprimir o compartir.',
        'reportes_excel':'Descargar datos de reportes en una hoja de cálculo.',
        'reportes_interpretacion':'Convertir una consulta escrita en filtros de reporte.',
        'reportes_voz':'Permitir el micrófono del cliente; la API recibe la transcripción como texto.',
        'reportes_programacion':'Generar y enviar reportes periódicos por correo; requiere PDF o Excel.',
        'respaldos_manuales':'Crear una copia a solicitud, consumiendo la cuota móvil de siete días.',
        'respaldos_automaticos':'Crear copias periódicas sin consumir la cuota manual.',
        'horario_respaldo_configurable':'Permitir elegir la hora y zona del calendario de respaldos.',
    }
    return {
        "funciones": [{"clave": k, "nombre": v[0], "modulo": v[1], "dependencias": v[2],
                       "descripcion":descripciones[k],"tipo": "booleano", "esencial": False,
                       "requiere_alguna":['reportes_pdf','reportes_excel'] if k=='reportes_programacion' else []} for k, v in CAPACIDADES.items()],
        "limites": [{"clave": k, "nombre": v[0], "unidad": v[1], "minimo": v[2],
                     "tipo": "entero", "ausencia": "sin límite" if k in {"usuarios", "empleados", "sucursales", "reportes_programados"} else "usar valor persistido"}
                    for k, v in LIMITES_CATALOGO.items()],
        "esenciales": ["acceso", "perfil", "seguridad", "empresa", "consulta_suscripcion",
                       "catalogo_basico", "inventario_basico", "ventas_basicas", "comprobantes", "reportes"],
        "incluidas_sin_diferenciar_plan": ["mayorista", "delivery", "asistente", "recomendaciones", "vestidor"],
        "nota_voz": "La API recibe texto: el origen dictado no se puede demostrar en el servidor.",
    }


def normalizar_politica(plan):
    """Transición compatible: las claves explícitas siempre prevalecen."""
    funciones = {k: True for k in CAPACIDADES}
    funciones.update(plan.get("funciones") or {})
    funciones.update({k: True for k in FUNCIONES_LIBRES})
    limites = {"respaldos_manuales_semana": 5, "retencion_respaldos_dias": 30, "frecuencia_respaldo_dias": 1}
    limites.update(plan.get("limites") or {})
    return {"funciones": funciones, "limites": limites}


def validar_politica(limites, funciones):
    if set(limites) - LIMITES_ADMITIDOS or set(funciones) - FUNCIONES_ADMITIDAS:
        raise ValueError("La configuración contiene claves desconocidas.")
    for k, v in limites.items():
        minimo = LIMITES_CATALOGO.get(k, (None, None, 0))[2]
        if type(v) is not int or v < minimo or v > 2147483647:
            raise ValueError(f"Límite inválido para {k}; mínimo: {minimo}.")
        if k in {'retencion_respaldos_dias','frecuencia_respaldo_dias'} and v>3650:
            raise ValueError(f'{k} admite como máximo 3650 días.')
    if any(type(v) is not bool for v in funciones.values()):
        raise ValueError("Las funciones requieren valores booleanos.")
    if any(funciones.get(k) is False for k in FUNCIONES_LIBRES):
        raise ValueError("Reportes básicos, asistente, recomendaciones y vestidor se incluyen en todos los planes.")
    for clave, (_, _, dependencias) in CAPACIDADES.items():
        if funciones.get(clave) and any(not funciones.get(d) for d in dependencias):
            raise ValueError(f"{clave} requiere: {', '.join(dependencias)}.")
    if funciones.get("reportes_programacion") and not any(funciones.get(k) for k in ("reportes_pdf", "reportes_excel")):
        raise ValueError("Programar reportes requiere PDF o Excel habilitado.")
    if funciones.get("reportes_programacion") and limites.get("reportes_programados") == 0:
        raise ValueError("La programación habilitada requiere un cupo mayor a cero.")
    if funciones.get("respaldos_manuales") and limites.get("respaldos_manuales_semana", 0) < 1:
        raise ValueError("Los respaldos manuales habilitados requieren un cupo mayor a cero.")


def uso_empresa_cursor(cursor, empresa_id):
    uso = {}
    for clave, tabla in (("usuarios", "usuario"), ("empleados", "empleado"), ("sucursales", "sucursal"),
                         ("reportes_programados", "reporte_programado")):
        cursor.execute(f"SELECT count(*) AS total FROM {tabla} WHERE empresa_id=%s AND activo=TRUE", (empresa_id,))
        row = cursor.fetchone()
        uso[clave] = int(row["total"] if isinstance(row, dict) else row[0])
    cursor.execute("SELECT count(*) AS total FROM respaldo WHERE empresa_id=%s AND origen='MANUAL' AND fecha >= CURRENT_TIMESTAMP - INTERVAL '7 days'", (empresa_id,))
    row = cursor.fetchone()
    uso["respaldos_manuales_semana"] = int(row["total"] if isinstance(row, dict) else row[0])
    return uso


def seleccionar_pausas_reportes(filas, politica):
    """Conserva las primeras programaciones permitidas por ID; nunca reactiva."""
    funciones, limites = politica["funciones"], politica["limites"]
    mantener, pausar = [], []
    for fila in sorted((f for f in filas if f["activo"]), key=lambda f: f["id"]):
        formato = "reportes_pdf" if fila["formato"] == "PDF" else "reportes_excel"
        cupo = limites.get("reportes_programados")
        if not funciones["reportes_programacion"] or not funciones[formato] or (cupo is not None and len(mantener) >= cupo):
            pausar.append(fila["id"])
        else:
            mantener.append(fila["id"])
    return pausar


def capacidades_empresa(empresa_id):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            plan = _leer_plan(cur, empresa_id, validar_vigencia=False)
            politica = normalizar_politica(plan)
            uso = uso_empresa_cursor(cur, empresa_id)
        return {"empresa_id": empresa_id, "plan_codigo": plan["plan_codigo"],
                "plan": {"id":plan.get('plan_id'),"codigo":plan['plan_codigo'],"nombre":plan.get('plan_nombre'),"revision":plan.get('plan_revision')},
                "suscripcion": {"estado":plan['suscripcion_estado'],"fecha_inicio":plan['fecha_inicio'],"fecha_vencimiento":plan['fecha_vencimiento']},
                "operaciones_habilitadas": plan["operaciones_habilitadas"],
                "funciones": {k: {"incluida": v, "habilitada": v and (k in FUNCIONES_LIBRES or plan["operaciones_habilitadas"]),
                                  "motivo": None if v and (k in FUNCIONES_LIBRES or plan["operaciones_habilitadas"]) else "SUSCRIPCION_NO_VIGENTE" if v else "FUNCION_NO_INCLUIDA"}
                              for k, v in politica["funciones"].items()},
                "limites": politica["limites"], "uso": uso,
                "cupos": {k:{"limite":politica['limites'].get(k),"uso":v,
                    "disponibles":max(0,politica['limites'][k]-v) if k in politica['limites'] else None,
                    "agotado":k in politica['limites'] and v>=politica['limites'][k],
                    "motivo":"CUPO_AGOTADO" if k in politica['limites'] and v>=politica['limites'][k] else None}
                    for k,v in uso.items()}, "catalogo": catalogo_capacidades()}
    finally:
        conn.close()


def exigir_capacidad_cursor(cursor, empresa_id, clave, *, validar_vigencia=True, bloquear=False):
    plan = _leer_plan(cursor, empresa_id, bloquear=bloquear, validar_vigencia=validar_vigencia)
    if normalizar_politica(plan)["funciones"].get(clave) is not True:
        raise HTTPException(403, {"codigo": "FUNCION_NO_INCLUIDA", "funcion": clave,
                                  "mensaje": "Esta función no está incluida en el plan."})
    return plan


def _leer_plan(cursor, empresa_id: int, bloquear: bool = False, validar_vigencia: bool = True) -> dict[str, object]:
    if bloquear:
        cursor.execute("SELECT pg_advisory_xact_lock_shared(%s)", (LOCK_PLANES,))
        # La operacion que consume un cupo debe mantener esta transaccion abierta
        # y contar el uso DESPUES del lock, antes de insertar.
        cursor.execute("SELECT id FROM empresa WHERE id=%s FOR UPDATE", (empresa_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Empresa no encontrada.")
    cursor.execute(
        """SELECT e.estado AS empresa_estado, s.estado AS suscripcion_estado,
                  s.fecha_inicio, s.fecha_vencimiento,
                  p.id AS plan_id,p.nombre AS plan_nombre,p.revision AS plan_revision,
                  p.codigo AS plan_codigo, p.activo AS plan_activo,
                  p.limites, p.funciones
           FROM empresa e
           LEFT JOIN LATERAL (
               SELECT * FROM suscripcion WHERE empresa_id=e.id
               ORDER BY fecha_creacion DESC, id DESC LIMIT 1
           ) s ON TRUE
           LEFT JOIN plan p ON p.id=s.plan_id
           WHERE e.id=%s LIMIT 1""",
        (empresa_id,),
    )
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Empresa no encontrada.")
    plan = dict(row) if isinstance(row, dict) else dict(zip((col[0] for col in cursor.description), row))
    hoy = datetime.now(ZoneInfo("America/La_Paz")).date()
    vigente = not (
        plan["empresa_estado"] != "ACTIVA"
        or plan["suscripcion_estado"] != "ACTIVA"
        or plan["plan_activo"] is not True
        or plan["fecha_inicio"] is None
        or plan["fecha_inicio"] > hoy
        or (plan["fecha_vencimiento"] is not None and plan["fecha_vencimiento"] < hoy)
    )
    plan["operaciones_habilitadas"] = vigente
    if validar_vigencia and not vigente:
        raise HTTPException(status_code=403, detail={
            "codigo": "SUSCRIPCION_NO_VIGENTE",
            "mensaje": "No se permiten operaciones nuevas. Puede consultar sus datos, pagar pendientes y gestionar devoluciones.",
        })
    return plan


def exigir_funcion_empresa(empresa_id: int, clave: str, *, permitir_consulta: bool = False) -> None:
    """Bloquea funciones deshabilitadas; StyleAR legado conserva acceso."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            plan = _leer_plan(cur, empresa_id, validar_vigencia=not permitir_consulta)
        if clave in FUNCIONES_LIBRES:
            return
        if normalizar_politica(plan)["funciones"].get(clave) is not True:
            raise HTTPException(status_code=403, detail="Funcion no incluida en el plan.")
    finally:
        conn.close()


def exigir_operaciones_empresa(empresa_id: int, cursor=None) -> None:
    """Valida antes de una escritura nueva; admite la transacción del repositorio."""
    if cursor is not None:
        _leer_plan(cursor, empresa_id, bloquear=True)
        return
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _leer_plan(cur, empresa_id)
    finally:
        conn.close()


def bloquear_empresa_y_obtener_limite(cursor, empresa_id: int, clave: str) -> int | None:
    """Llamar dentro de la misma transaccion ANTES de contar e insertar.

    None = sin limite configurado. No usar un conteo obtenido antes de este lock.
    """
    plan = _leer_plan(cursor, empresa_id, bloquear=True)
    limite = plan["limites"].get(clave)
    if limite is None:
        return None
    if not isinstance(limite, int) or limite < 0:
        raise HTTPException(status_code=500, detail="Limite del plan invalido.")
    return limite


def exigir_cupo_usuarios(cursor, empresa_id: int, usuario_id: int | None = None) -> None:
    """Cuenta cuentas activas (clientes y personal); serializa altas/reactivaciones."""
    limite = bloquear_empresa_y_obtener_limite(cursor, empresa_id, "usuarios")
    if usuario_id is not None:
        cursor.execute("SELECT activo FROM usuario WHERE id=%s AND empresa_id=%s", (usuario_id, empresa_id))
        actual = cursor.fetchone()
        if actual and (actual["activo"] if isinstance(actual, dict) else actual[0]):
            return
    cursor.execute("SELECT count(*) AS total FROM usuario WHERE empresa_id=%s AND activo=TRUE", (empresa_id,))
    row = cursor.fetchone()
    total = int(row["total"] if isinstance(row, dict) else row[0])
    if limite is not None and total >= limite:
        raise HTTPException(status_code=409, detail={"codigo": "LIMITE_USUARIOS", "mensaje": "Se alcanzó el límite de cuentas activas del plan."})
