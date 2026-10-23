"""Validaciones reutilizables de suscripcion y funciones por empresa."""

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from psycopg2.extras import RealDictCursor

from app.database.connection import get_connection

LIMITES_ADMITIDOS = {"usuarios", "empleados", "productos", "sucursales"}
FUNCIONES_ADMITIDAS = {"recomendaciones", "asistente", "reportes", "vestidor"}


def _leer_plan(cursor, empresa_id: int, bloquear: bool = False, validar_vigencia: bool = True) -> dict[str, object]:
    if bloquear:
        # La operacion que consume un cupo debe mantener esta transaccion abierta
        # y contar el uso DESPUES del lock, antes de insertar.
        cursor.execute("SELECT id FROM empresa WHERE id=%s FOR UPDATE", (empresa_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Empresa no encontrada.")
    cursor.execute(
        """SELECT e.estado AS empresa_estado, s.estado AS suscripcion_estado,
                  s.fecha_inicio, s.fecha_vencimiento,
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
        funciones = plan.get("funciones") or {}
        if plan["plan_codigo"] == "STYLEAR_LEGADO" and clave not in funciones:
            return
        if funciones.get(clave) is not True:
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
