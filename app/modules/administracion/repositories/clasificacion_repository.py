"""CU09: escrituras del catálogo y su auditoría en una única transacción."""
import ipaddress

from fastapi import HTTPException
from psycopg2 import sql
from psycopg2.errors import UniqueViolation

from app.core.contexto_empresa import exigir_empresa_id
from app.modules.autenticacion.repositories.perfil_repository import _transaccion
from app.modules.autenticacion.repositories.administracion_acceso_repository import validar_actor
from .control_comercial import preparar_escritura


# Identificadores cerrados: ningún nombre SQL procede de la petición.
CAMPOS = {
    'categoria': ('nombre', 'descripcion', 'categoria_padre_id'),
    'talla': ('nombre', 'descripcion', 'tipo_prenda', 'ancho_cm', 'largo_cm'),
    'color': ('nombre', 'codigo_hex'),
    'marca': ('nombre', 'descripcion'),
    'temporada': ('nombre', 'anio'),
    'coleccion': ('nombre', 'descripcion', 'temporada_id'),
}


def _padre(cur, tabla, datos, registro_id, empresa_id):
    campo, destino = ('categoria_padre_id', 'categoria') if tabla == 'categoria' else ('temporada_id', 'temporada')
    padre_id = datos.get(campo)
    if padre_id is None:
        return
    cur.execute(sql.SQL('SELECT activo FROM {} WHERE id=%s AND empresa_id=%s FOR UPDATE').format(sql.Identifier(destino)),
                (padre_id, empresa_id))
    padre = cur.fetchone()
    if not padre or not padre['activo']:
        raise HTTPException(409, 'El padre seleccionado no existe en su empresa o está inactivo.')
    if tabla == 'categoria' and registro_id is not None:
        # UNION evita bucles incluso si una base antigua contiene ciclos.
        cur.execute('''WITH RECURSIVE ancestros AS (
            SELECT id,categoria_padre_id FROM categoria WHERE id=%s AND empresa_id=%s
            UNION
            SELECT c.id,c.categoria_padre_id FROM categoria c JOIN ancestros a
                ON c.id=a.categoria_padre_id WHERE c.empresa_id=%s
            ) SELECT 1 FROM ancestros WHERE id=%s''', (padre_id, empresa_id, empresa_id, registro_id))
        if cur.fetchone():
            raise HTTPException(409, 'La categoría padre produciría un ciclo en la jerarquía.')


def _dependencias(cur, tabla, registro_id, empresa_id):
    consultas = {
        'categoria': '''SELECT 1 FROM categoria WHERE categoria_padre_id=%s AND empresa_id=%s AND activo
            UNION ALL SELECT 1 FROM producto WHERE categoria_id=%s AND empresa_id=%s AND activo''',
        'marca': 'SELECT 1 FROM producto WHERE marca_id=%s AND empresa_id=%s AND activo',
        'talla': 'SELECT 1 FROM producto_variante WHERE talla_id=%s AND empresa_id=%s AND activo',
        'color': 'SELECT 1 FROM producto_variante WHERE color_id=%s AND empresa_id=%s AND activo',
        'temporada': 'SELECT 1 FROM coleccion WHERE temporada_id=%s AND empresa_id=%s AND activo',
        'coleccion': '''SELECT 1 FROM producto_coleccion pc JOIN producto p ON p.id=pc.producto_id
            AND p.empresa_id=pc.empresa_id WHERE pc.coleccion_id=%s AND pc.empresa_id=%s AND pc.activo AND p.activo''',
    }
    params = (registro_id, empresa_id) * (2 if tabla == 'categoria' else 1)
    cur.execute(consultas[tabla] + ' LIMIT 1', params)
    if cur.fetchone():
        raise HTTPException(409, 'No se puede desactivar: existen asociaciones activas. Desactívelas o reasígnelas primero.')


def escribir_clasificacion(tabla, actor, datos=None, registro_id=None, activo=None, ip=None, ua=None):
    campos = CAMPOS[tabla]
    empresa = exigir_empresa_id(actor)
    datos = {c: datos[c] for c in campos} if datos is not None else None
    try:
        with _transaccion() as cur:
            # Mismo orden de bloqueos que CU04/CU07/CU08; serializa duplicados y jerarquías.
            preparar_escritura(cur, int(actor['id']), empresa, None, nueva=activo is not False)
            validar_actor(cur, actor)
            actual = None
            if registro_id is not None:
                cur.execute(sql.SQL('SELECT * FROM {} WHERE id=%s AND empresa_id=%s FOR UPDATE').format(sql.Identifier(tabla)),
                            (registro_id, empresa))
                actual = cur.fetchone()
                if not actual:
                    raise HTTPException(404, 'Clasificación no encontrada en su empresa.')
            if activo is False:
                _dependencias(cur, tabla, registro_id, empresa)
            elif tabla in ('categoria', 'coleccion'):
                _padre(cur, tabla, datos if datos is not None else actual, registro_id, empresa)

            if datos is not None:
                # La identidad incluye tipo de prenda/año/temporada según corresponda.
                # La misma clave que los índices únicos, incluso con locale C.
                condiciones = [sql.SQL(
                    'public.normalizar_nombre_catalogo(nombre) COLLATE "C" = '
                    'public.normalizar_nombre_catalogo(%s) COLLATE "C"'
                ), sql.SQL('empresa_id=%s')]
                params = [datos['nombre'], empresa]
                for campo in {'talla': ('tipo_prenda',), 'temporada': ('anio',), 'coleccion': ('temporada_id',)}.get(tabla, ()):
                    condiciones.append(sql.SQL('{}=%s').format(sql.Identifier(campo)))
                    params.append(datos[campo])
                if registro_id is not None:
                    condiciones.append(sql.SQL('id<>%s'))
                    params.append(registro_id)
                cur.execute(sql.SQL('SELECT 1 FROM {} WHERE {} LIMIT 1').format(sql.Identifier(tabla), sql.SQL(' AND ').join(condiciones)), params)
                if cur.fetchone():
                    raise HTTPException(409, 'Ya existe una clasificación con ese nombre y combinación, incluso entre las inactivas.')
                if registro_id is None:
                    columnas = (*campos, 'empresa_id')
                    cur.execute(sql.SQL('INSERT INTO {} ({}) VALUES ({}) RETURNING *').format(
                        sql.Identifier(tabla), sql.SQL(',').join(map(sql.Identifier, columnas)),
                        sql.SQL(',').join(sql.Placeholder() for _ in columnas)), [datos[c] for c in campos] + [empresa])
                else:
                    cur.execute(sql.SQL('UPDATE {} SET {} WHERE id=%s AND empresa_id=%s RETURNING *').format(
                        sql.Identifier(tabla), sql.SQL(',').join(sql.SQL('{}=%s').format(sql.Identifier(c)) for c in campos)),
                        [datos[c] for c in campos] + [registro_id, empresa])
            else:
                cur.execute(sql.SQL('UPDATE {} SET activo=%s WHERE id=%s AND empresa_id=%s RETURNING *').format(sql.Identifier(tabla)),
                            (activo, registro_id, empresa))
            fila = dict(cur.fetchone())
            if tabla == 'coleccion':
                cur.execute('SELECT nombre FROM temporada WHERE id=%s AND empresa_id=%s', (fila['temporada_id'], empresa))
                fila['temporada_nombre'] = cur.fetchone()['nombre']
            elif tabla == 'categoria':
                cur.execute('SELECT nombre FROM categoria WHERE id=%s AND empresa_id=%s', (fila['categoria_padre_id'], empresa))
                padre = cur.fetchone()
                fila['categoria_padre_nombre'] = padre['nombre'] if padre else None
            try:
                ip = str(ipaddress.ip_address(ip)) if ip else None
            except ValueError:
                ip = None
            accion = ('CREAR' if registro_id is None else 'ACTUALIZAR') if datos is not None else ('ACTIVAR' if activo else 'DESACTIVAR')
            cur.execute('''INSERT INTO bitacora(usuario_id,empresa_id,accion,modulo,descripcion,resultado,direccion_ip,user_agent)
                VALUES(%s,%s,%s,'CATALOGO',%s,'EXITOSO',%s::inet,%s)''',
                (actor['id'], empresa, accion, f'{tabla}: id={fila["id"]}', ip, ua))
            return fila
    except UniqueViolation as error:
        raise HTTPException(409, 'Ya existe una clasificación con ese nombre y combinación.') from error
