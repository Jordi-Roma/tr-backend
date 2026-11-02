"""Paquetes por modelo, sucursal y empresa. Precio mayorista sin promoción acumulada."""
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from uuid import UUID
import hashlib
import json
from fastapi import HTTPException
from pydantic import BaseModel, Field, ConfigDict, model_validator
from app.core.contexto_empresa import exigir_empresa_id
from app.modules.autenticacion.repositories.perfil_repository import _transaccion
from app.modules.administracion.repositories.control_comercial import preparar_escritura
from app.modules.autenticacion.repositories.administracion_acceso_repository import validar_actor, LOCK_ACCESOS
from app.core.plan_empresa import exigir_operaciones_empresa

CANTIDADES = {'CUARTA': 3, 'MEDIA': 6, 'DOCENA': 12}
Tipo = Literal['CUARTA', 'MEDIA', 'DOCENA']

class PrecioRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tipo: Tipo
    descuento: Decimal | None = Field(default=None, gt=0, lt=100, max_digits=5, decimal_places=2)
    habilitado: bool = False
    version: int = Field(default=0, ge=0)

    @model_validator(mode='after')
    def precio_requerido(self):
        if self.habilitado and self.descuento is None:
            raise ValueError('Configura un porcentaje antes de habilitar el paquete.')
        return self

class Seleccion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    producto_variante_id: int = Field(gt=0)
    cantidad: int = Field(gt=0, le=12, strict=True)

class PaqueteRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    clave_operacion: UUID
    producto_id: int = Field(gt=0)
    sucursal_id: int = Field(gt=0)
    tipo: Tipo
    seleccion: list[Seleccion] = Field(min_length=1, max_length=12)


def producto(cur, empresa, pid):
    cur.execute('SELECT id FROM producto WHERE id=%s AND empresa_id=%s AND activo', (pid, empresa))
    if not cur.fetchone():
        raise HTTPException(404, 'Producto no encontrado en esta empresa.')


def configuracion(cur, empresa, pid):
    producto(cur, empresa, pid)
    cur.execute('SELECT * FROM precio_mayorista WHERE empresa_id=%s AND producto_id=%s', (empresa, pid))
    filas = {r['tipo']: dict(r) for r in cur.fetchall()}
    return [filas.get(t, dict(tipo=t, descuento=None, habilitado=False, version=0)) for t in CANTIDADES]


def guardar(actor, pid, datos):
    empresa = exigir_empresa_id(actor)
    with _transaccion() as cur:
        preparar_escritura(cur, actor['id'], empresa, None, nueva=False)
        validar_actor(cur, actor)
        producto(cur, empresa, pid)
        cur.execute('SELECT version FROM precio_mayorista WHERE empresa_id=%s AND producto_id=%s AND tipo=%s FOR UPDATE', (empresa, pid, datos.tipo))
        previo = cur.fetchone()
        if datos.version != (previo['version'] if previo else 0):
            raise HTTPException(409, 'El porcentaje cambió. Actualiza antes de guardar.')
        cur.execute('''INSERT INTO precio_mayorista(empresa_id,producto_id,tipo,descuento,habilitado,version)
            VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(empresa_id,producto_id,tipo) DO UPDATE SET
            descuento=EXCLUDED.descuento,habilitado=EXCLUDED.habilitado,version=EXCLUDED.version,actualizado_en=CURRENT_TIMESTAMP''',
            (empresa, pid, datos.tipo, datos.descuento, datos.habilitado, datos.version+1))
        cur.execute("INSERT INTO bitacora(usuario_id,empresa_id,accion,modulo,descripcion) VALUES(%s,%s,'CONFIGURAR','MAYORISTA',%s)", (actor['id'],empresa,f'Producto {pid}: {datos.tipo}, descuento {datos.descuento}%.'))
        return configuracion(cur, empresa, pid)


def variantes(cur, empresa, pid, sid):
    producto(cur, empresa, pid)
    cur.execute('SELECT id FROM sucursal WHERE id=%s AND empresa_id=%s AND activo', (sid, empresa))
    if not cur.fetchone():
        raise HTTPException(404, 'Sucursal no encontrada en esta empresa.')
    cur.execute('''SELECT v.id producto_variante_id,v.talla_id,v.color_id,COALESCE(t.nombre,'Sin talla') talla,
        COALESCE(c.nombre,'Sin color') color,COALESCE(GREATEST(i.stock_disponible-i.stock_reservado,0),0)::int stock,
        pp.precio precio_base FROM producto_variante v
        LEFT JOIN talla t ON t.id=v.talla_id AND t.empresa_id=v.empresa_id
        LEFT JOIN color c ON c.id=v.color_id AND c.empresa_id=v.empresa_id
        LEFT JOIN inventario_sucursal i ON i.producto_variante_id=v.id AND i.empresa_id=v.empresa_id AND i.sucursal_id=%s AND i.activo
        LEFT JOIN LATERAL(SELECT precio FROM precio_producto p WHERE p.producto_variante_id=v.id AND p.empresa_id=v.empresa_id
          AND p.activo AND CURRENT_DATE BETWEEN p.fecha_inicio AND COALESCE(p.fecha_fin,CURRENT_DATE)
          ORDER BY p.fecha_inicio DESC,p.id DESC LIMIT 1) pp ON TRUE
        WHERE v.producto_id=%s AND v.empresa_id=%s AND v.activo ORDER BY t.nombre,c.nombre,v.id''', (sid,pid,empresa))
    return [dict(r) for r in cur.fetchall()]


def precio_neto(base, descuento):
    return (Decimal(base)*(1-Decimal(descuento)/100)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)


def motivo(tipo, filas, cfg, seleccion=None):
    if not cfg['habilitado'] or cfg['descuento'] is None:
        return 'Porcentaje mayorista pendiente de configuración o paquete deshabilitado.'
    tallas = {r['talla_id'] for r in filas if r['talla_id'] is not None}
    if len(tallas)<2:
        return 'La compra por mayor requiere al menos dos tallas del producto.'
    disponibles = [r for r in filas if r['stock']>0 and r['precio_base'] and precio_neto(r['precio_base'], cfg['descuento'])>0]
    req_tallas = 2 if tipo=='CUARTA' else 3 if tipo=='MEDIA' else len(tallas)
    req_colores = 2 if tipo=='CUARTA' else 3 if tipo=='MEDIA' else 0
    if req_tallas > CANTIDADES[tipo]:
        return 'Las tallas del producto no caben en este paquete fijo.'
    if seleccion is not None:
        ids = [s['producto_variante_id'] for s in seleccion]
        if len(ids)!=len(set(ids)) or sum(s['cantidad'] for s in seleccion)!=CANTIDADES[tipo]:
            return f'El paquete debe contener exactamente {CANTIDADES[tipo]} prendas, sin variantes repetidas.'
        por_id = {r['producto_variante_id']:r for r in disponibles}
        if any(s['producto_variante_id'] not in por_id or s['cantidad']>por_id[s['producto_variante_id']]['stock'] for s in seleccion):
            return 'La selección incluye una variante sin precio o sin stock suficiente.'
        disponibles = [por_id[s['producto_variante_id']] for s in seleccion]
    elif sum(r['stock'] for r in disponibles)<CANTIDADES[tipo]:
        return f'No hay {CANTIDADES[tipo]} prendas disponibles para este paquete.'
    hay_tallas = {r['talla_id'] for r in disponibles if r['talla_id'] is not None}
    hay_colores = {r['color_id'] for r in disponibles if r['color_id'] is not None}
    if len(hay_tallas)<req_tallas or (tipo=='DOCENA' and not tallas.issubset(hay_tallas)):
        return f'Se requieren {req_tallas} tallas distintas'+(' (todas las del producto).' if tipo=='DOCENA' else '.')
    if len(hay_colores)<req_colores:
        return f'Se requieren {req_colores} colores distintos.'
    return None


def opciones(cur, empresa, pid, sid):
    filas = variantes(cur,empresa,pid,sid)
    cfgs = configuracion(cur,empresa,pid)
    return dict(producto_id=pid,sucursal_id=sid,variantes=filas,paquetes=[dict(**cfg,cantidad=CANTIDADES[cfg['tipo']],motivo=motivo(cfg['tipo'],filas,cfg),disponible=motivo(cfg['tipo'],filas,cfg) is None) for cfg in cfgs])


def validar_grupos(cur, empresa, items):
    """Devuelve motivos por paquete y asigna precios actuales sin alterar su composición."""
    grupos = defaultdict(list)
    for item in items:
        if item.get('paquete_id'):
            grupos[item['paquete_id']].append(item)
    errores = {}
    for gid, seleccion in grupos.items():
        cur.execute('SELECT * FROM carrito_paquete WHERE id=%s AND empresa_id=%s AND activo', (gid,empresa))
        grupo = cur.fetchone()
        if not grupo:
            errores[gid] = 'Paquete no disponible.'
            continue
        try:
            filas = variantes(cur,empresa,grupo['producto_id'],seleccion[0]['sucursal_id'])
        except HTTPException:
            errores[gid] = 'El producto o la sucursal del paquete ya no está disponible.'
            for item in seleccion:
                item['tipo_compra'] = grupo['tipo']
                item['precio_unitario'] = Decimal('0')
                item['subtotal'] = Decimal('0')
            continue
        cfg = next(c for c in configuracion(cur,empresa,grupo['producto_id']) if c['tipo']==grupo['tipo'])
        error = motivo(grupo['tipo'],filas,cfg,seleccion)
        if error: errores[gid] = error
        por_id = {r['producto_variante_id']:r for r in filas}
        for item in seleccion:
            r = por_id.get(item['producto_variante_id'])
            item['tipo_compra'] = grupo['tipo']
            item['descuento_mayorista'] = cfg['descuento']
            item['precio_unitario'] = precio_neto(r['precio_base'],cfg['descuento']) if r and r['precio_base'] and cfg['descuento'] else Decimal('0')
            item['subtotal'] = item['precio_unitario']*item['cantidad']
    return errores


def agregar(actor, datos):
    from app.modules.reservas.repositories import carrito_repository as cart
    empresa = exigir_empresa_id(actor)
    if 'CLIENTE' not in actor.get('roles',[]): raise HTTPException(403,'Se requiere una cuenta de cliente.')
    seleccion = sorted([s.model_dump() for s in datos.seleccion], key=lambda s:s['producto_variante_id'])
    huella = hashlib.sha256(json.dumps(dict(producto=datos.producto_id,sucursal=datos.sucursal_id,tipo=datos.tipo,seleccion=seleccion),sort_keys=True).encode()).hexdigest()
    with _transaccion() as cur:
        cur.execute('SELECT pg_advisory_xact_lock(%s)',(LOCK_ACCESOS,))
        cur.execute('SELECT id FROM empresa WHERE id=%s FOR UPDATE',(empresa,))
        exigir_operaciones_empresa(empresa,cur)
        cur.execute('''SELECT u.id FROM usuario u WHERE u.id=%s AND u.empresa_id=%s AND u.activo AND u.version_acceso=%s
            AND EXISTS(SELECT 1 FROM usuario_rol ur JOIN rol r ON r.id=ur.rol_id AND r.activo WHERE ur.usuario_id=u.id AND ur.activo AND r.nombre='CLIENTE')''',(actor['id'],empresa,actor.get('version_acceso',0)))
        if not cur.fetchone():raise HTTPException(401,'La cuenta cambió. Inicia sesión nuevamente.')
        cid = cart._obtener_cliente_id_por_usuario_cursor(cur,actor['id'],empresa)
        if not cid: raise HTTPException(403,'Cliente no disponible.')
        carrito = cart._obtener_o_crear_carrito_cursor(cur,cid)
        cur.execute('SELECT id,huella,activo FROM carrito_paquete WHERE carrito_id=%s AND clave=%s',(carrito,str(datos.clave_operacion)))
        previo=cur.fetchone()
        if previo:
            if previo['huella']!=huella or not previo['activo']: raise HTTPException(409,'La clave pertenece a otro paquete o a uno ya retirado.')
            return cart._armar_carrito_cursor(cur,carrito)
        filas = variantes(cur,empresa,datos.producto_id,datos.sucursal_id)
        # Descontar del disponible las unidades y paquetes ya presentes en el carrito.
        for r in filas:
            r['stock']-=cart._obtener_cantidad_item_cursor(cur,carrito,r['producto_variante_id'],datos.sucursal_id)
        cfg = next(c for c in configuracion(cur,empresa,datos.producto_id) if c['tipo']==datos.tipo)
        error = motivo(datos.tipo,filas,cfg,seleccion)
        if error:raise HTTPException(409,error)
        cur.execute('INSERT INTO carrito_paquete(empresa_id,carrito_id,producto_id,tipo,clave,huella) VALUES(%s,%s,%s,%s,%s,%s) RETURNING id', (empresa,carrito,datos.producto_id,datos.tipo,str(datos.clave_operacion),huella))
        gid=cur.fetchone()['id']
        por_id = {r['producto_variante_id']:r for r in filas}
        for s in seleccion:
            cur.execute('INSERT INTO carrito_item(carrito_id,producto_variante_id,sucursal_id,cantidad,precio_unitario,paquete_id) VALUES(%s,%s,%s,%s,%s,%s)',
                (carrito,s['producto_variante_id'],datos.sucursal_id,s['cantidad'],precio_neto(por_id[s['producto_variante_id']]['precio_base'],cfg['descuento']),gid))
        return cart._armar_carrito_cursor(cur,carrito)
