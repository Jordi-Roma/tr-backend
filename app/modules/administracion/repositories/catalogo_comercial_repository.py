"""CU10: cambios comerciales atómicos, con historial y aislamiento por empresa."""
from contextlib import contextmanager
from datetime import timedelta
import ipaddress

from fastapi import HTTPException
from psycopg2 import sql
from psycopg2.errors import UniqueViolation

from app.core.contexto_empresa import exigir_empresa_id
from app.modules.autenticacion.repositories.administracion_acceso_repository import validar_actor
from app.modules.autenticacion.repositories.perfil_repository import _transaccion
from .control_comercial import preparar_escritura
from .producto_repository import _exigir_cupo_producto_cursor


PRODUCTO = ('categoria_id','marca_id','nombre','descripcion','material','genero',
            'tipo_prenda','tipo_corte','ancho_base_cm','largo_base_cm','modelo_3d_url')
VARIANTE = ('talla_id','color_id','sku','ancho_cm','largo_cm')
PROMOCION = ('nombre','descripcion','tipo_descuento','valor','fecha_inicio','fecha_fin')


@contextmanager
def escritura(actor, modulo, accion, ip=None, ua=None, nueva=True):
    empresa = exigir_empresa_id(actor)
    try:
        with _transaccion() as cur:
            preparar_escritura(cur, int(actor['id']), empresa, None, nueva)
            validar_actor(cur, actor)
            evento = {}
            yield cur, empresa, evento
            try:
                ip = str(ipaddress.ip_address(ip)) if ip else None
            except ValueError:
                ip = None
            cur.execute('''INSERT INTO bitacora(usuario_id,empresa_id,accion,modulo,descripcion,resultado,direccion_ip,user_agent)
                VALUES(%s,%s,%s,%s,%s,'EXITOSO',%s::inet,%s)''', (actor['id'],empresa,accion,modulo,str(evento),ip,ua))
    except UniqueViolation as error:
        raise HTTPException(409, 'Ya existe ese SKU o esa combinación de talla y color en el producto, incluso entre los inactivos.') from error


def registro(cur, tabla, rid, empresa, activo=False):
    cur.execute(sql.SQL('SELECT * FROM {} WHERE id=%s AND empresa_id=%s FOR UPDATE').format(sql.Identifier(tabla)), (rid,empresa))
    fila = cur.fetchone()
    if fila is None:
        raise HTTPException(404, f'{tabla.capitalize()} no encontrado en su empresa.')
    if activo and not fila['activo']:
        raise HTTPException(409, f'{tabla.capitalize()} está inactivo.')
    return dict(fila)


def producto_de_variante(cur, vid, empresa, activo=False):
    # Consultar el padre sin bloquear primero al hijo. Reservas y administración
    # adquieren siempre producto -> variante -> inventario para evitar interbloqueos.
    cur.execute('SELECT producto_id FROM producto_variante WHERE id=%s AND empresa_id=%s', (vid,empresa))
    variante = cur.fetchone()
    if variante is None:
        raise HTTPException(404, 'Variante no encontrada en su empresa.')
    return registro(cur,'producto',variante['producto_id'],empresa,activo)


def guardar_fila(cur, tabla, campos, datos, empresa, rid=None):
    if rid is None:
        columnas = (*campos,'empresa_id')
        cur.execute(sql.SQL('INSERT INTO {} ({}) VALUES ({}) RETURNING id').format(
            sql.Identifier(tabla),sql.SQL(',').join(map(sql.Identifier,columnas)),
            sql.SQL(',').join(sql.Placeholder() for _ in columnas)), [datos[c] for c in campos]+[empresa])
    else:
        cur.execute(sql.SQL('UPDATE {} SET {} WHERE id=%s AND empresa_id=%s RETURNING id').format(
            sql.Identifier(tabla),sql.SQL(',').join(sql.SQL('{}=%s').format(sql.Identifier(c)) for c in campos)),
            [datos[c] for c in campos]+[rid,empresa])
    return int(cur.fetchone()['id'])


def vinculos(cur, tabla, campo_origen, origen, campo_destino, destinos, empresa):
    cur.execute(sql.SQL('UPDATE {} SET activo=FALSE WHERE {}=%s AND empresa_id=%s').format(
        sql.Identifier(tabla),sql.Identifier(campo_origen)), (origen,empresa))
    for destino in destinos:
        cur.execute(sql.SQL('''INSERT INTO {} ({},{},empresa_id,activo) VALUES(%s,%s,%s,TRUE)
            ON CONFLICT({},{}) DO UPDATE SET activo=TRUE''').format(
            sql.Identifier(tabla),sql.Identifier(campo_origen),sql.Identifier(campo_destino),
            sql.Identifier(campo_origen),sql.Identifier(campo_destino)), (origen,destino,empresa))


def referencias_producto(cur, datos, empresa):
    registro(cur,'categoria',datos['categoria_id'],empresa,True)
    if datos['marca_id'] is not None:
        registro(cur,'marca',datos['marca_id'],empresa,True)
    for cid in datos['colecciones_ids']:
        col = registro(cur,'coleccion',cid,empresa,True)
        registro(cur,'temporada',col['temporada_id'],empresa,True)
    for pid in datos['proveedores_ids']:
        registro(cur,'proveedor',pid,empresa,True)


def imagenes(cur, pid, entradas, empresa):
    cur.execute('UPDATE imagen_producto SET activo=FALSE,es_principal=FALSE WHERE producto_id=%s AND empresa_id=%s',(pid,empresa))
    for img in entradas:
        cur.execute('SELECT id FROM imagen_producto WHERE producto_id=%s AND empresa_id=%s AND url=%s ORDER BY id LIMIT 1', (pid,empresa,img['url']))
        existente = cur.fetchone()
        if existente:
            cur.execute('UPDATE imagen_producto SET activo=TRUE,es_principal=%s WHERE id=%s AND empresa_id=%s',(img['es_principal'],existente['id'],empresa))
        else:
            cur.execute('INSERT INTO imagen_producto(producto_id,empresa_id,url,es_principal) VALUES(%s,%s,%s,%s)',(pid,empresa,img['url'],img['es_principal']))


def guardar_producto(actor, datos, pid=None, ip=None, ua=None):
    with escritura(actor,'PRODUCTOS','CREAR' if pid is None else 'ACTUALIZAR',ip,ua) as (cur,empresa,evento):
        if pid is not None:
            actual = registro(cur,'producto',pid,empresa)
            cur.execute('''SELECT 1 FROM producto_variante v JOIN talla t ON t.id=v.talla_id AND t.empresa_id=v.empresa_id
                WHERE v.producto_id=%s AND v.empresa_id=%s AND t.tipo_prenda<>%s LIMIT 1''',(pid,empresa,datos['tipo_prenda']))
            if actual['tipo_prenda'] != datos['tipo_prenda'] and cur.fetchone():
                raise HTTPException(409, 'El tipo de prenda es incompatible con las tallas de sus variantes existentes.')
        else:
            _exigir_cupo_producto_cursor(cur,empresa)
        referencias_producto(cur,datos,empresa)
        pid = guardar_fila(cur,'producto',PRODUCTO,datos,empresa,pid)
        vinculos(cur,'producto_coleccion','producto_id',pid,'coleccion_id',datos['colecciones_ids'],empresa)
        vinculos(cur,'producto_proveedor','producto_id',pid,'proveedor_id',datos['proveedores_ids'],empresa)
        imagenes(cur,pid,datos['imagenes'],empresa)
        for variante in datos.get('variantes',[]):
            vid = _guardar_variante(cur,{**variante,'producto_id':pid},empresa)
            if variante.get('precio') is not None:
                _precio(cur,vid,variante['precio'],empresa)
        evento['producto_id'] = pid
        return pid


def _guardar_variante(cur, datos, empresa, vid=None):
    if vid is not None:
        producto = producto_de_variante(cur,vid,empresa,True)
        actual = registro(cur,'producto_variante',vid,empresa)
        datos = {**datos,'producto_id':actual['producto_id']}
    else:
        producto = registro(cur,'producto',datos['producto_id'],empresa,True)
    if datos['talla_id'] is not None:
        talla = registro(cur,'talla',datos['talla_id'],empresa,True)
        if talla['tipo_prenda'] != producto['tipo_prenda']:
            raise HTTPException(409,'La talla no corresponde al tipo de prenda del producto.')
    if datos['color_id'] is not None:
        registro(cur,'color',datos['color_id'],empresa,True)
    cur.execute('''SELECT 1 FROM producto_variante WHERE empresa_id=%s AND id IS DISTINCT FROM %s
        AND (lower(btrim(sku))=lower(btrim(%s)) OR (producto_id=%s AND talla_id IS NOT DISTINCT FROM %s AND color_id IS NOT DISTINCT FROM %s)) LIMIT 1''',
        (empresa,vid,datos['sku'],datos['producto_id'],datos['talla_id'],datos['color_id']))
    if cur.fetchone():
        raise HTTPException(409,'Ya existe ese SKU o esa combinación de talla y color, incluso entre los inactivos.')
    return guardar_fila(cur,'producto_variante',(*VARIANTE,'producto_id'),datos,empresa,vid)


def guardar_variante(actor, datos, vid=None, ip=None, ua=None):
    with escritura(actor,'VARIANTES','CREAR' if vid is None else 'ACTUALIZAR',ip,ua) as (cur,empresa,evento):
        vid = _guardar_variante(cur,datos,empresa,vid)
        evento['variante_id'] = vid
        return vid


def _sin_compromisos(cur, vids, empresa):
    cur.execute('''SELECT stock_reservado FROM inventario_sucursal
        WHERE producto_variante_id=ANY(%s) AND empresa_id=%s FOR UPDATE''',(vids,empresa))
    if any(int(r['stock_reservado'])>0 for r in cur.fetchall()):
        raise HTTPException(409,'Hay existencias reservadas. Resuelva las reservas antes de desactivar.')


def estado_producto(actor, pid, activo, ip=None, ua=None):
    with escritura(actor,'PRODUCTOS','ACTIVAR' if activo else 'DESACTIVAR',ip,ua,nueva=activo) as (cur,empresa,evento):
        actual = registro(cur,'producto',pid,empresa)
        if activo:
            if not actual['activo']:
                _exigir_cupo_producto_cursor(cur,empresa)
            registro(cur,'categoria',actual['categoria_id'],empresa,True)
            if actual['marca_id']:
                registro(cur,'marca',actual['marca_id'],empresa,True)
        else:
            cur.execute('SELECT id FROM producto_variante WHERE producto_id=%s AND empresa_id=%s FOR UPDATE',(pid,empresa))
            _sin_compromisos(cur,[r['id'] for r in cur.fetchall()],empresa)
            cur.execute('UPDATE producto_variante SET activo=FALSE WHERE producto_id=%s AND empresa_id=%s',(pid,empresa))
        evento['producto_id'] = pid
        cur.execute('UPDATE producto SET activo=%s WHERE id=%s AND empresa_id=%s',(activo,pid,empresa))


def estado_variante(actor, vid, activo, ip=None, ua=None):
    with escritura(actor,'VARIANTES','ACTIVAR' if activo else 'DESACTIVAR',ip,ua,nueva=activo) as (cur,empresa,evento):
        p = producto_de_variante(cur,vid,empresa,activo)
        v = registro(cur,'producto_variante',vid,empresa)
        if activo:
            if v['talla_id']:
                talla = registro(cur,'talla',v['talla_id'],empresa,True)
                if talla['tipo_prenda'] != p['tipo_prenda']:
                    raise HTTPException(409,'La talla es incompatible con el producto.')
            if v['color_id']:
                registro(cur,'color',v['color_id'],empresa,True)
        else:
            _sin_compromisos(cur,[vid],empresa)
        evento['variante_id'] = vid
        cur.execute('UPDATE producto_variante SET activo=%s WHERE id=%s AND empresa_id=%s',(activo,vid,empresa))


def _precio(cur, vid, datos, empresa):
    producto_de_variante(cur,vid,empresa,True)
    v = registro(cur,'producto_variante',vid,empresa,True)
    cur.execute('SELECT CURRENT_DATE hoy')
    hoy = cur.fetchone()['hoy']
    inicio = datos['fecha_inicio'] or hoy
    if hasattr(inicio,'date'):
        inicio = inicio.date()
    fin = datos['fecha_fin']
    if fin is not None and hasattr(fin,'date'):
        fin = fin.date()
    if fin is not None and fin < inicio:
        raise HTTPException(422,'La fecha fin no puede ser anterior a la fecha inicio.')
    cur.execute('''SELECT 1 FROM promocion pr JOIN promocion_producto pp ON pp.promocion_id=pr.id AND pp.empresa_id=pr.empresa_id AND pp.activo
        WHERE pp.producto_id=%s AND pr.empresa_id=%s AND pr.activo AND pr.tipo_descuento='MONTO_FIJO'
        AND pr.fecha_inicio<=COALESCE(%s,'infinity'::date) AND pr.fecha_fin>=%s AND pr.valor>%s LIMIT 1''',
        (v['producto_id'],empresa,fin,inicio,datos['monto']))
    if cur.fetchone():
        raise HTTPException(409,'El precio resultaría negativo con una promoción de monto fijo vigente en ese período.')
    cur.execute('''SELECT * FROM precio_producto WHERE producto_variante_id=%s AND empresa_id=%s AND activo
        AND fecha_inicio<=COALESCE(%s,'infinity'::date) AND COALESCE(fecha_fin,'infinity'::date)>=%s FOR UPDATE''',(vid,empresa,fin,inicio))
    for anterior in cur.fetchall():
        if fin is not None and (anterior['fecha_fin'] is None or anterior['fecha_fin']>fin):
            cur.execute('''INSERT INTO precio_producto(empresa_id,producto_variante_id,precio,fecha_inicio,fecha_fin)
                VALUES(%s,%s,%s,%s,%s)''',(empresa,vid,anterior['precio'],fin+timedelta(days=1),anterior['fecha_fin']))
        if anterior['fecha_inicio']<inicio:
            cur.execute('UPDATE precio_producto SET fecha_fin=%s WHERE id=%s',(inicio-timedelta(days=1),anterior['id']))
        else:
            cur.execute('UPDATE precio_producto SET activo=FALSE WHERE id=%s',(anterior['id'],))
    cur.execute('''INSERT INTO precio_producto(empresa_id,producto_variante_id,precio,fecha_inicio,fecha_fin)
        VALUES(%s,%s,%s,%s,%s) RETURNING id''',(empresa,vid,datos['monto'],inicio,fin))
    return cur.fetchone()['id']


def guardar_precio(actor, vid, datos, ip=None, ua=None):
    with escritura(actor,'VARIANTES','ASIGNAR_PRECIO',ip,ua) as (cur,empresa,evento):
        evento['variante_id'] = vid
        return _precio(cur,vid,datos,empresa)


def referencias_promocion(cur, datos, empresa):
    for pid in datos['producto_ids']:
        registro(cur,'producto',pid,empresa,True)
        if datos['tipo_descuento']=='MONTO_FIJO':
            cur.execute('''SELECT v.id FROM producto_variante v WHERE v.producto_id=%s AND v.empresa_id=%s AND v.activo
                AND (NOT EXISTS(SELECT 1 FROM precio_producto p WHERE p.producto_variante_id=v.id AND p.empresa_id=v.empresa_id AND p.activo
                    AND p.fecha_inicio<=%s AND COALESCE(p.fecha_fin,'infinity'::date)>=%s)
                OR EXISTS(SELECT 1 FROM precio_producto p WHERE p.producto_variante_id=v.id AND p.empresa_id=v.empresa_id AND p.activo
                    AND p.fecha_inicio<=%s AND COALESCE(p.fecha_fin,'infinity'::date)>=%s AND p.precio<%s)) LIMIT 1''',
                (pid,empresa,datos['fecha_fin'],datos['fecha_inicio'],datos['fecha_fin'],datos['fecha_inicio'],datos['valor']))
            if cur.fetchone():
                raise HTTPException(409,'El descuento fijo supera un precio o hay variantes sin precio en el período.')
    for sid in datos['sucursal_ids']:
        registro(cur,'sucursal',sid,empresa,True)


def guardar_promocion(actor, datos, rid=None):
    with escritura(actor,'PROMOCIONES','CREAR' if rid is None else 'ACTUALIZAR') as (cur,empresa,evento):
        if rid is not None:
            registro(cur,'promocion',rid,empresa)
        referencias_promocion(cur,datos,empresa)
        rid = guardar_fila(cur,'promocion',PROMOCION,datos,empresa,rid)
        vinculos(cur,'promocion_producto','promocion_id',rid,'producto_id',datos['producto_ids'],empresa)
        vinculos(cur,'promocion_sucursal','promocion_id',rid,'sucursal_id',datos['sucursal_ids'],empresa)
        evento['promocion_id'] = rid
        return rid


def estado_promocion(actor, rid, activo):
    with escritura(actor,'PROMOCIONES','ACTIVAR' if activo else 'DESACTIVAR',nueva=activo) as (cur,empresa,evento):
        actual = registro(cur,'promocion',rid,empresa)
        if activo:
            cur.execute('SELECT CURRENT_DATE hoy')
            if actual['fecha_fin']<cur.fetchone()['hoy']:
                raise HTTPException(409,'La promoción está vencida; edite su vigencia antes de reactivarla.')
            for tabla,campo in (('promocion_producto','producto_id'),('promocion_sucursal','sucursal_id')):
                cur.execute(sql.SQL('SELECT {} id FROM {} WHERE promocion_id=%s AND empresa_id=%s AND activo').format(sql.Identifier(campo),sql.Identifier(tabla)),(rid,empresa))
                actual['producto_ids' if campo=='producto_id' else 'sucursal_ids']=[r['id'] for r in cur.fetchall()]
            referencias_promocion(cur,actual,empresa)
        evento['promocion_id'] = rid
        cur.execute('UPDATE promocion SET activo=%s WHERE id=%s AND empresa_id=%s',(activo,rid,empresa))
