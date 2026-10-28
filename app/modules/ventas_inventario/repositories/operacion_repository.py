"""Reintentos comerciales y bloqueo estable antes de tocar existencias."""
import hashlib
import json


def iniciar_operacion(cur, empresa_id, usuario_id, operacion, clave, datos):
    if clave is None:
        return None
    clave = str(clave)
    huella = hashlib.sha256(json.dumps(datos, sort_keys=True, default=str,
                                       ensure_ascii=False).encode()).hexdigest()
    contexto = f'operacion:{empresa_id}:{usuario_id}:{operacion}:{clave}'
    cur.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', (contexto,))
    cur.execute('''SELECT recurso_id,huella FROM operacion_comercial
        WHERE empresa_id=%s AND usuario_id=%s AND operacion=%s AND clave=%s''',
        (empresa_id, usuario_id, operacion, clave))
    previa = cur.fetchone()
    if previa and previa['huella'] != huella:
        raise ValueError('Esta clave de operación ya se utilizó con otros datos.')
    return int(previa['recurso_id']) if previa else None


def finalizar_operacion(cur, empresa_id, usuario_id, operacion, clave, datos, recurso_id):
    if clave is None:
        return
    huella = hashlib.sha256(json.dumps(datos, sort_keys=True, default=str,
                                       ensure_ascii=False).encode()).hexdigest()
    cur.execute('''INSERT INTO operacion_comercial
        (empresa_id,usuario_id,operacion,clave,huella,recurso_id) VALUES(%s,%s,%s,%s,%s,%s)''',
        (empresa_id,usuario_id,operacion,str(clave),huella,recurso_id))


def bloquear_existencias(cur, empresa_id, pares):
    """Serializa también filas aún inexistentes, siempre en el mismo orden.

    Los bloqueos de fila continúan siendo la protección de cantidad. Este
    bloqueo evita carreras INSERT y transferencias A→B/B→A entre estas rutas.
    """
    for sucursal_id, variante_id in sorted(set(pares)):
        cur.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                    (f'stock:{empresa_id}:{sucursal_id}:{variante_id}',))


def auditar_operacion(cur, usuario_id, empresa_id, accion, descripcion):
    cur.execute('''INSERT INTO bitacora(usuario_id,empresa_id,accion,modulo,descripcion)
        VALUES(%s,%s,%s,'VENTAS_INVENTARIO',%s)''', (usuario_id,empresa_id,accion,descripcion))
