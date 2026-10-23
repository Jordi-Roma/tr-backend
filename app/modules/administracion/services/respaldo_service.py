"""Respaldos cifrados. Restauración selectiva en la empresa original; global en destino vacío.

No se admite una ruta o conexión proporcionada por el navegador. La configuración
de almacenamiento y del destino de ensayo pertenece al operador de la plataforma.
"""

import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
from urllib.parse import urlsplit, unquote
from zipfile import ZipFile, ZIP_DEFLATED, BadZipFile

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import parse_dsn
from psycopg2.extras import RealDictCursor
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException

from app.core.config import DATABASE_URL
from app.database.connection import get_connection
from app.modules.administracion.repositories.empresa_saas_repository import auditar

STATIC = Path(__file__).resolve().parents[4] / "static"
PLATAFORMA = {"empresa", "plan", "evento_plataforma", "respaldo", "schema_migrations"}


def configuracion():
    ruta = os.getenv("STYLEAR_BACKUP_DIR")
    clave = os.getenv("STYLEAR_BACKUP_KEY")
    try:
        dias = int(os.environ["STYLEAR_BACKUP_RETENTION_DAYS"])
        if not 1 <= dias <= 3650 or not ruta or not clave:
            raise ValueError()
        directorio = Path(ruta).resolve()
        if directorio == STATIC.resolve() or STATIC.resolve() in directorio.parents:
            raise ValueError()
        cifrador = Fernet(clave.encode("ascii"))
    except (ValueError, KeyError, UnicodeError) as error:
        raise HTTPException(503, "Configure directorio privado, clave de cifrado y conservación de respaldos.") from error
    directorio.mkdir(parents=True, exist_ok=True, mode=0o700)
    return directorio, cifrador, dias


def _json(valor):
    return json.dumps(valor, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _versiones(cur):
    cur.execute("SELECT version FROM schema_migrations ORDER BY version")
    return [r["version"] for r in cur.fetchall()]


def _esquema(cur):
    cur.execute("""SELECT table_name,column_name,is_nullable,data_type FROM information_schema.columns
                   WHERE table_schema='public' ORDER BY table_name,ordinal_position""")
    tablas = {}
    for r in cur.fetchall():
        tablas.setdefault(r["table_name"], {})[r["column_name"]] = dict(r)
    cur.execute("""SELECT tc.table_name,kcu.column_name,ccu.table_name AS padre,ccu.column_name AS columna_padre
                   FROM information_schema.table_constraints tc
                   JOIN information_schema.key_column_usage kcu USING (constraint_catalog,constraint_schema,constraint_name)
                   JOIN information_schema.constraint_column_usage ccu USING (constraint_catalog,constraint_schema,constraint_name)
                   WHERE tc.constraint_type='FOREIGN KEY' AND tc.table_schema='public'""")
    fks = [dict(r) for r in cur.fetchall()]
    # Un alcance por tabla. Las relaciones restantes se validan también por FK/triggers.
    alcances = {t: 't.empresa_id = %s' for t, cols in tablas.items() if 'empresa_id' in cols and t not in PLATAFORMA}
    while True:
        nuevos = {}
        for r in fks:
            t, padre = r['table_name'], r['padre']
            if t not in alcances and t not in PLATAFORMA and padre in alcances:
                condicion = alcances[padre].replace('t.', 'p.')
                # Los hijos sin empresa de este esquema dependen directamente de usuario.
                if 'empresa_id' not in tablas[padre]:
                    continue
                nuevos[t] = f'EXISTS (SELECT 1 FROM "{padre}" p WHERE p."{r["columna_padre"]}"=t."{r["column_name"]}" AND {condicion})'
        if not nuevos:
            break
        alcances.update(nuevos)
    cur.execute("""SELECT tc.table_name,k.column_name FROM information_schema.table_constraints tc
                   JOIN information_schema.key_column_usage k USING (constraint_catalog,constraint_schema,constraint_name)
                   WHERE tc.constraint_type='PRIMARY KEY' AND tc.table_schema='public' ORDER BY k.ordinal_position""")
    pks = {}
    for r in cur.fetchall():
        pks.setdefault(r['table_name'], []).append(r['column_name'])
    return tablas, fks, alcances, pks


def _filas(cur, tabla, alcance=None, empresa_id=None):
    query = sql.SQL('SELECT to_jsonb(t) AS fila FROM {} t').format(sql.Identifier(tabla))
    if alcance:
        query += sql.SQL(' WHERE ' + alcance)
    cur.execute(query, (empresa_id,) if alcance else ())
    return sorted([r['fila'] for r in cur.fetchall()], key=_json)


def _archivo_local(valor):
    if not isinstance(valor, str):
        return None
    ruta = unquote(urlsplit(valor).path)
    if '/static/' not in ruta:
        return None
    relativa = ruta.split('/static/', 1)[1]
    archivo = (STATIC / relativa).resolve()
    if STATIC.resolve() not in archivo.parents or archivo.is_symlink():
        raise HTTPException(409, "Referencia de archivo fuera del almacenamiento permitido.")
    if not archivo.is_file():
        raise HTTPException(409, "Falta un archivo local referenciado; no se genera una copia incompleta.")
    return archivo


def _archivos_en_filas(tablas):
    archivos = set()
    def visitar(valor):
        if isinstance(valor, dict):
            for v in valor.values():
                visitar(v)
        elif isinstance(valor, list):
            for v in valor:
                visitar(v)
        elif isinstance(valor, str):
            archivo = _archivo_local(valor)
            if archivo:
                archivos.add(archivo)
    visitar(tablas)
    return archivos


def _pg_env(dsn):
    parametros = parse_dsn(dsn)
    env = os.environ.copy()
    for nombre in ('PGHOST', 'PGPORT', 'PGUSER', 'PGPASSWORD', 'PGDATABASE', 'PGSERVICE'):
        env.pop(nombre, None)
    for clave, valor in parametros.items():
        env['PG' + ('DATABASE' if clave == 'dbname' else clave.upper())] = valor
    return env


def _pg(comando, dsn):
    try:
        subprocess.run(comando, env=_pg_env(dsn), check=True, capture_output=True, timeout=600)
    except (OSError, subprocess.SubprocessError) as error:
        # La salida de las herramientas puede contener cadenas de conexión.
        raise HTTPException(503, "Falló la herramienta PostgreSQL de respaldo/restauración. Revise el entorno privado.") from error


def crear_respaldo(actor_id: int, empresa_id: int | None = None):
    directorio, cifrador, dias = configuracion()
    identificador = uuid4()
    conn = get_connection()
    archivo = directorio / f'{identificador}.fernet'
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            versiones = _versiones(cur)
            manifiesto = {'formato': 1, 'id': str(identificador), 'tipo': 'EMPRESA' if empresa_id else 'GLOBAL', 'empresa_id': empresa_id, 'versiones': versiones}
            buffer = io.BytesIO()
            with ZipFile(buffer, 'w', ZIP_DEFLATED) as z:
                if empresa_id is not None:
                    cur.execute('SELECT codigo FROM empresa WHERE id=%s', (empresa_id,))
                    empresa = cur.fetchone()
                    if not empresa:
                        raise HTTPException(404, 'Empresa no encontrada.')
                    _, _, alcances, _ = _esquema(cur)
                    datos = {t: _filas(cur, t, alcance, empresa_id) for t, alcance in alcances.items()}
                    manifiesto['empresa_codigo'] = empresa['codigo']
                    z.writestr('datos.json', _json(datos))
                    # Referencias globales se verifican, nunca se sobrescriben al restaurar una empresa.
                    globales = {t: _filas(cur, t) for t in ('ciudad', 'rol', 'permiso', 'rol_permiso', 'plan')}
                    z.writestr('referencias.json', _json(globales))
                    archivos = _archivos_en_filas(datos)
                    manifiesto['conteos'] = {t: len(filas) for t, filas in datos.items()}
                else:
                    # Una instantánea exportada mantiene el dump y el manifiesto en la misma versión de la base.
                    cur.execute('SELECT pg_export_snapshot() AS snapshot')
                    snapshot = cur.fetchone()['snapshot']
                    with tempfile.TemporaryDirectory(prefix='stylear_dump_') as tmp:
                        dump = Path(tmp) / 'base.dump'
                        _pg(['pg_dump', '--format=custom', '--no-owner', '--no-privileges', '--snapshot=' + snapshot, '--file=' + str(dump)], DATABASE_URL)
                        z.write(dump, 'base.dump')
                    archivos = {p for p in STATIC.rglob('*') if p.is_file() and not p.is_symlink()} if STATIC.exists() else set()
                for p in sorted(archivos):
                    z.write(p, 'archivos/' + p.relative_to(STATIC).as_posix())
                manifiesto['archivos'] = len(archivos)
                z.writestr('manifiesto.json', _json(manifiesto))
            conn.rollback()
            contenido = cifrador.encrypt(buffer.getvalue())
            with archivo.open('xb') as f:
                f.write(contenido)
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""INSERT INTO respaldo (id,empresa_id,tipo,creado_por,vence_en,sha256,bytes)
                    VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id,tipo,empresa_id,fecha,vence_en,bytes,estado""",
                    (str(identificador),empresa_id,manifiesto['tipo'],actor_id,datetime.now(timezone.utc)+timedelta(days=dias),hashlib.sha256(contenido).hexdigest(),len(contenido)))
                resultado = dict(cur.fetchone())
                auditar(cur,actor_id,'CREAR_RESPALDO',empresa_id,str(identificador))
            conn.commit()
            return resultado
    except Exception:
        conn.rollback()
        archivo.unlink(missing_ok=True)
        raise
    finally:
        conn.close()


def listar_respaldos():
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('SELECT id,tipo,empresa_id,fecha,vence_en,bytes,estado FROM respaldo ORDER BY fecha DESC LIMIT 200')
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def _abrir(cur, identificador: UUID):
    directorio, cifrador, _ = configuracion()
    cur.execute("SELECT * FROM respaldo WHERE id=%s AND estado='DISPONIBLE' FOR UPDATE", (str(identificador),))
    registro = cur.fetchone()
    if registro is None:
        raise HTTPException(404, 'Respaldo no encontrado.')
    archivo = directorio / f'{identificador}.fernet'
    try:
        contenido = archivo.read_bytes()
        if hashlib.sha256(contenido).hexdigest() != registro['sha256']:
            raise ValueError()
        z = ZipFile(io.BytesIO(cifrador.decrypt(contenido)))
        manifiesto = json.loads(z.read('manifiesto.json'))
        if manifiesto['id'] != str(identificador) or manifiesto['empresa_id'] != registro['empresa_id'] or manifiesto['tipo'] != registro['tipo']:
            raise ValueError()
        return z, manifiesto
    except (OSError, ValueError, InvalidToken, KeyError, BadZipFile) as error:
        raise HTTPException(409, 'No se pudo verificar o descifrar el respaldo.') from error


def previsualizar_restauracion(identificador: UUID, actor_id: int):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            with _abrir(cur, identificador)[0] as z:
                manifiesto = json.loads(z.read('manifiesto.json'))
            if manifiesto['versiones'] != _versiones(cur):
                raise HTTPException(409, 'El esquema difiere del respaldo; requiere una migración supervisada.')
            resultado = {**manifiesto, 'confirmacion': 'RESTAURAR ' + str(identificador)}
            if manifiesto['empresa_id']:
                _, _, alcances, _ = _esquema(cur)
                resultado['conteos_actuales'] = {t: len(_filas(cur,t,c,manifiesto['empresa_id'])) for t,c in alcances.items()}
                resultado['destino'] = 'Empresa original suspendida; reemplaza sus datos comerciales y cierra sus sesiones.'
            else:
                resultado['destino'] = 'Base y carpeta de ensayo vacías configuradas por el operador; no sobrescribe producción.'
            auditar(cur,actor_id,'PREVISUALIZAR_RESTAURACION',manifiesto['empresa_id'],str(identificador))
        conn.commit()
        return resultado
    finally:
        conn.close()


def _restaurar_archivos(z, destino, nuevos):
    for nombre in z.namelist():
        if not nombre.startswith('archivos/') or nombre.endswith('/'):
            continue
        archivo = (destino / nombre.removeprefix('archivos/')).resolve()
        if destino.resolve() not in archivo.parents or archivo.is_symlink():
            raise HTTPException(409, 'Archivo fuera del destino permitido.')
        contenido = z.read(nombre)
        if archivo.exists():
            if archivo.read_bytes() != contenido:
                raise HTTPException(409, 'Un archivo existente difiere; no se sobrescriben recursos compartidos.')
            continue
        archivo.parent.mkdir(parents=True,exist_ok=True)
        with archivo.open('xb') as f:
            f.write(contenido)
        nuevos.append(archivo)
    return nuevos


def restaurar_respaldo(identificador: UUID, actor_id: int, confirmacion: str):
    if confirmacion != 'RESTAURAR ' + str(identificador):
        raise HTTPException(400, 'Debe confirmar la restauración del respaldo indicado.')
    conn = get_connection()
    nuevos = []
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            z, manifiesto = _abrir(cur,identificador)
            with z:
                if manifiesto['versiones'] != _versiones(cur):
                    raise HTTPException(409, 'El esquema difiere del respaldo.')
                if manifiesto['tipo'] == 'GLOBAL':
                    _restaurar_global(z, nuevos)
                else:
                    _restaurar_empresa(cur,z,manifiesto)
                    _restaurar_archivos(z,STATIC,nuevos)
                auditar(cur,actor_id,'RESTAURAR_RESPALDO',manifiesto['empresa_id'],str(identificador))
        conn.commit()
        return {'estado': 'RESTAURADO', 'destino': 'ENSAYO' if manifiesto['tipo']=='GLOBAL' else 'EMPRESA_ORIGINAL_SUSPENDIDA'}
    except Exception:
        conn.rollback()
        for archivo in nuevos:
            archivo.unlink(missing_ok=True)
        raise
    finally:
        conn.close()


def _restaurar_empresa(cur,z,manifiesto):
    empresa_id = manifiesto['empresa_id']
    cur.execute('SELECT codigo,estado FROM empresa WHERE id=%s FOR UPDATE', (empresa_id,))
    empresa = cur.fetchone()
    if not empresa or empresa['codigo'] != manifiesto['empresa_codigo'] or empresa['estado'] != 'SUSPENDIDA':
        raise HTTPException(409,'Suspenda la empresa original antes de restaurarla.')
    tablas,fks,alcances,pks = _esquema(cur)
    datos = json.loads(z.read('datos.json'))
    if set(datos) != set(alcances):
        raise HTTPException(409,'El inventario de tablas cambió.')
    # Evita escrituras concurrentes durante el reemplazo y permite verificar que B no cambie.
    for t in sorted(alcances):
        cur.execute(sql.SQL('LOCK TABLE {} IN EXCLUSIVE MODE').format(sql.Identifier(t)))
    cur.execute('SET CONSTRAINTS ALL DEFERRED')
    for t,filas in json.loads(z.read('referencias.json')).items():
        if filas != _filas(cur,t):
            raise HTTPException(409,'Cambió una referencia global; revise el respaldo antes de restaurar.')
    antes = {t:_filas(cur,t,'NOT ('+c+')',empresa_id) for t,c in alcances.items()}
    for t,filas in datos.items():
        for fila in filas:
            if 'empresa_id' in tablas[t] and fila['empresa_id'] != empresa_id:
                raise HTTPException(409,'Fila de otra empresa en el respaldo.')
            condicion = sql.SQL(' AND ').join(sql.SQL('{} IS NOT DISTINCT FROM %s').format(sql.Identifier(k)) for k in pks[t])
            cur.execute(sql.SQL('SELECT 1 FROM {} t WHERE ').format(sql.Identifier(t))+condicion+sql.SQL(' AND NOT ('+alcances[t]+')'),tuple(fila[k] for k in pks[t])+(empresa_id,))
            if cur.fetchone():
                raise HTTPException(409,'Un identificador pertenece a otra empresa.')
    # Rompe únicamente vínculos anulables de la empresa restaurada, luego elimina
    # hijos antes que padres, incluso cuando una FK usa ON DELETE RESTRICT.
    pendientes_orden = set(datos)
    orden = []
    while pendientes_orden:
        disponibles = sorted(t for t in pendientes_orden if not any(r['table_name']==t and r['padre'] in pendientes_orden and r['padre']!=t and tablas[t][r['column_name']]['is_nullable']=='NO' for r in fks))
        if not disponibles:
            raise HTTPException(409,'Dependencia circular obligatoria.')
        orden.extend(disponibles)
        pendientes_orden.difference_update(disponibles)
    for t in orden:
        anulables = {r['column_name'] for r in fks if r['table_name']==t and tablas[t][r['column_name']]['is_nullable']=='YES' and r['padre'] in datos and r['column_name'] not in pks[t]}
        if anulables:
            asignaciones = sql.SQL(',').join(sql.SQL('{}=NULL').format(sql.Identifier(k)) for k in sorted(anulables))
            cur.execute(sql.SQL('UPDATE {} t SET ').format(sql.Identifier(t))+asignaciones+sql.SQL(' WHERE '+alcances[t]),(empresa_id,))
    for t in reversed(orden):
        cur.execute(sql.SQL('DELETE FROM {} t WHERE ').format(sql.Identifier(t))+sql.SQL(alcances[t]),(empresa_id,))
    pendientes = set(datos)
    actualizaciones = []
    while pendientes:
        disponibles = sorted(t for t in pendientes if not any(r['table_name']==t and r['padre'] in pendientes and r['padre']!=t and tablas[t][r['column_name']]['is_nullable']=='NO' for r in fks))
        if not disponibles:
            raise HTTPException(409,'Dependencia circular obligatoria; no se restaura parcialmente.')
        for t in disponibles:
            anulables = {r['column_name'] for r in fks if r['table_name']==t and tablas[t][r['column_name']]['is_nullable']=='YES' and r['padre'] in datos}
            for fila in datos[t]:
                inicial = {k:(None if k in anulables else v) for k,v in fila.items()}
                cur.execute(sql.SQL('INSERT INTO {} SELECT (json_populate_record(NULL::{},%s::json)).*').format(sql.Identifier(t),sql.Identifier(t)),(_json(inicial),))
                if anulables:
                    actualizaciones.append((t,fila,anulables))
            pendientes.remove(t)
    for t,fila,columnas in actualizaciones:
        asignaciones = sql.SQL(',').join(sql.SQL('{}=r.{}').format(sql.Identifier(k),sql.Identifier(k)) for k in sorted(columnas))
        condicion = sql.SQL(' AND ').join(sql.SQL('t.{}=r.{}').format(sql.Identifier(k),sql.Identifier(k)) for k in pks[t])
        cur.execute(sql.SQL('UPDATE {} t SET ').format(sql.Identifier(t))+asignaciones+sql.SQL(' FROM json_populate_record(NULL::{},%s::json) r WHERE ').format(sql.Identifier(t))+condicion,(_json(fila),))
    cur.execute('SET CONSTRAINTS ALL IMMEDIATE')
    for t,c in alcances.items():
        if _filas(cur,t,c,empresa_id)!=datos[t] or _filas(cur,t,'NOT ('+c+')',empresa_id)!=antes[t]:
            raise HTTPException(409,'La verificación de datos restaurados o de otras empresas falló.')
    # Tokens guardados en una copia anterior no deben volver a habilitar sesiones.
    cur.execute('UPDATE sesion SET activa=FALSE WHERE empresa_id=%s',(empresa_id,))
    cur.execute('UPDATE token_recuperacion SET utilizado=TRUE WHERE usuario_id IN (SELECT id FROM usuario WHERE empresa_id=%s)',(empresa_id,))
    cur.execute('UPDATE password_reset_token SET usado=TRUE WHERE usuario_id IN (SELECT id FROM usuario WHERE empresa_id=%s)',(empresa_id,))


def _restaurar_global(z, nuevos):
    dsn = os.getenv('STYLEAR_RESTORE_DATABASE_URL')
    assets = os.getenv('STYLEAR_RESTORE_ASSETS_DIR')
    if not dsn or not assets or parse_dsn(dsn)==parse_dsn(DATABASE_URL):
        raise HTTPException(503,'Configure una base y una carpeta vacías de ensayo distintas de producción.')
    destino = Path(assets).resolve()
    if destino == STATIC.resolve() or STATIC.resolve() in destino.parents or (destino.exists() and any(destino.iterdir())):
        raise HTTPException(409,'El destino de archivos debe estar vacío y separado del activo.')
    ensayo = psycopg2.connect(dsn)
    try:
        with ensayo.cursor() as c:
            c.execute('SELECT current_database(),inet_server_addr()::text,inet_server_port()')
            identidad_destino = c.fetchone()
            activo = get_connection()
            try:
                with activo.cursor() as original:
                    original.execute('SELECT current_database(),inet_server_addr()::text,inet_server_port()')
                    if identidad_destino == original.fetchone():
                        raise HTTPException(409,'El destino es la base activa; use una base de ensayo distinta.')
            finally:
                activo.close()
            c.execute("SELECT 1 FROM information_schema.tables WHERE table_schema='public' LIMIT 1")
            if c.fetchone():
                raise HTTPException(409,'La base de ensayo debe estar vacía.')
    finally:
        ensayo.close()
    _restaurar_archivos(z,destino,nuevos)
    with tempfile.TemporaryDirectory(prefix='stylear_restore_') as tmp:
        dump = Path(tmp)/'base.dump'
        dump.write_bytes(z.read('base.dump'))
        _pg(['pg_restore','--dbname='+parse_dsn(dsn)['dbname'],'--single-transaction','--exit-on-error','--no-owner','--no-privileges',str(dump)],dsn)
    ensayo = psycopg2.connect(dsn)
    try:
        with ensayo.cursor() as c:
            c.execute('UPDATE sesion SET activa=FALSE')
            c.execute('UPDATE token_recuperacion SET utilizado=TRUE')
            c.execute('UPDATE password_reset_token SET usado=TRUE')
        ensayo.commit()
    finally:
        ensayo.close()


def eliminar_respaldo(identificador: UUID,actor_id: int):
    directorio,_,_ = configuracion()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE respaldo SET estado='ELIMINADO' WHERE id=%s AND estado='DISPONIBLE' RETURNING empresa_id",(str(identificador),))
            row = cur.fetchone()
            if not row:
                raise HTTPException(404,'Respaldo no encontrado.')
            auditar(cur,actor_id,'ELIMINAR_RESPALDO',row[0],str(identificador))
        conn.commit()
        (directorio/f'{identificador}.fernet').unlink(missing_ok=True)
        return {'estado':'ELIMINADO'}
    finally:
        conn.close()


def purgar_vencidos(actor_id: int):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM respaldo WHERE estado='DISPONIBLE' AND vence_en<CURRENT_TIMESTAMP")
            ids = [r[0] for r in cur.fetchall()]
    finally:
        conn.close()
    for identificador in ids:
        eliminar_respaldo(identificador,actor_id)
    return {"eliminados":len(ids)}
