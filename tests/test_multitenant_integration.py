"""Pruebas optativas sobre una base LOCAL desechable y explícitamente indicada.

STYLEAR_TEST_DATABASE_URL debe coincidir con DATABASE_URL y usar una base
stylear_test_* en localhost. Nunca se utiliza la configuración .env como destino.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import psycopg2
from psycopg2.extensions import parse_dsn
from psycopg2.extras import RealDictCursor
from fastapi import HTTPException
from cryptography.fernet import Fernet

DSN = os.getenv('STYLEAR_TEST_DATABASE_URL')
if not DSN:
    pytest.skip('Base local desechable no indicada.',allow_module_level=True)
PARAM = parse_dsn(DSN)
assert PARAM.get('host') in {'127.0.0.1','localhost'}
assert PARAM.get('dbname','').startswith('stylear_test_')
assert DSN == os.environ.get('DATABASE_URL')

from app.database.connection import get_connection
from app.core.security import hashear_password
from app.core.plan_empresa import exigir_operaciones_empresa
from app.modules.administracion.repositories import empresa_saas_repository as saas
from app.modules.administracion.repositories import catalogo_repository as catalogo
from app.modules.administracion.repositories import variante_repository as variantes
from app.modules.autenticacion.repositories.usuario_admin_repository import crear_usuario_con_rol
from app.modules.autenticacion.schemas.sesion.sesion_request import LoginRequest
from app.modules.autenticacion.services.sesion_service import iniciar_sesion
from app.modules.administracion.services import respaldo_service as respaldos


def consulta(query, params=(), una=False):
    conn=get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query,params)
            filas=cur.fetchall() if cur.description else []
        conn.commit()
        return (dict(filas[0]) if filas else None) if una else [dict(r) for r in filas]
    finally:
        conn.close()


@pytest.fixture(scope='module')
def actor():
    suffix=uuid4().hex[:10]
    consulta("INSERT INTO ciudad(nombre,departamento) VALUES(%s,'Prueba')",('Ciudad '+suffix,))
    actor=consulta("INSERT INTO usuario(nombre,apellido,username,correo,password_hash,empresa_id) VALUES('AS','Prueba',%s,%s,%s,NULL) RETURNING id",('as'+suffix,suffix+'@example.invalid',hashear_password('Prueba-AS-local-123')),True)['id']
    consulta("INSERT INTO usuario_rol(usuario_id,rol_id) SELECT %s,id FROM rol WHERE nombre='ADMIN_SAAS'",(actor,))
    return actor


@pytest.fixture
def empresas(actor):
    suffix=uuid4().hex[:10]
    plan=saas.crear_plan('T_'+suffix,'Prueba',{'usuarios':50,'productos':50,'sucursales':50,'empleados':50},{'reportes':True,'recomendaciones':True,'vestidor':True,'asistente':True},actor)
    def crear(codigo):
        datos={'codigo':codigo,'nombre':codigo,'plan_id':plan['id'],'fecha_inicio':date(2020,1,1),'fecha_vencimiento':None,'admin_nombre':'Admin','admin_apellido':'Prueba','admin_username':codigo,'admin_correo':codigo+'@example.invalid'}
        return saas.crear_empresa_con_admin(datos,hashear_password('Prueba-aislada-123'),actor)
    return crear('a-'+suffix),crear('b-'+suffix),plan,actor


def cliente(empresa):
    nombre='cl'+uuid4().hex[:12]
    rol=consulta("SELECT id FROM rol WHERE nombre='CLIENTE'",una=True)['id']
    usuario=crear_usuario_con_rol('Cliente','Prueba',nombre,nombre+'@example.invalid',hashear_password('Prueba-aislada-123'),rol,'CLIENTE',None,empresa['admin_usuario_id'],empresa['id'])
    cl=consulta('SELECT id FROM cliente WHERE usuario_id=%s',(usuario['id'],),True)['id']
    return usuario['id'],cl,nombre


def mercaderia(empresa,stock=4):
    eid=empresa['id']; c=catalogo.crear_categoria(None,'Ropa',None,empresa_id=eid)
    talla=catalogo.crear_talla('M',None,empresa_id=eid)
    color=catalogo.crear_color('Azul',None,empresa_id=eid)
    ciudad=consulta('SELECT id FROM ciudad ORDER BY id LIMIT 1',una=True)['id']
    sucursal=consulta("INSERT INTO sucursal(empresa_id,ciudad_id,nombre,direccion) VALUES(%s,%s,'Centro','Prueba') RETURNING id",(eid,ciudad),True)['id']
    producto=consulta("INSERT INTO producto(empresa_id,categoria_id,nombre) VALUES(%s,%s,'Prenda') RETURNING id",(eid,c['id']),True)['id']
    variante=variantes.crear_variante(eid,producto,talla['id'],color['id'],'MISMO-SKU')
    variantes.asignar_precio(variante,eid,Decimal('50'),date(2020,1,1),None)
    consulta('INSERT INTO inventario_sucursal(empresa_id,sucursal_id,producto_variante_id,stock_disponible) VALUES(%s,%s,%s,%s)',(eid,sucursal,variante,stock))
    return sucursal,producto,variante


def test_directorio_publico_incluye_consultables_y_no_expone_datos_saas(empresas):
    import httpx
    from app.main import app
    a,b,_,_=empresas
    consulta("UPDATE empresa SET estado='SUSPENDIDA' WHERE id=%s", (a['id'],))
    consulta("UPDATE empresa SET estado='CANCELADA' WHERE id=%s", (b['id'],))

    async def verificar():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://pruebas') as c:
            respuesta=await c.get('/api/v1/empresas/publicas')
            assert respuesta.status_code==200,respuesta.text
            empresas_publicas=respuesta.json()
            assert all(set(e)=={'id','nombre','codigo','estado'} for e in empresas_publicas)
            assert any(e['id']==a['id'] and e['estado']=='SUSPENDIDA' for e in empresas_publicas)
            assert not any(e['id']==b['id'] for e in empresas_publicas)
            assert (await c.get('/api/v1/empresas/publica/'+b['codigo'])).status_code==404
    asyncio.run(verificar())


def test_migrador_repetido_preserva_datos_y_versiones():
    from init_db import ejecutar_scripts
    antes=consulta('SELECT id,username,empresa_id FROM usuario ORDER BY id')
    ejecutar_scripts()
    assert consulta('SELECT id,username,empresa_id FROM usuario ORDER BY id')==antes
    assert len(consulta('SELECT version FROM schema_migrations'))==2


@pytest.mark.parametrize('entidad',['categoria','talla','color','marca'])
def test_catalogos_repetidos_y_ids_ajenos(empresas,entidad):
    a,b,_,_=empresas
    crear=getattr(catalogo,'crear_'+entidad)
    args=(None,'Compartido',None) if entidad=='categoria' else ('Compartido',None)
    ra=crear(*args,empresa_id=a['id']);rb=crear(*args,empresa_id=b['id'])
    plural={'categoria':'categorias','talla':'tallas','color':'colores','marca':'marcas'}[entidad]
    assert {r['id'] for r in getattr(catalogo,'listar_'+plural)(empresa_id=a['id'])}=={ra['id']}
    assert getattr(catalogo,'obtener_'+entidad+'_por_id')(rb['id'],empresa_id=a['id']) is None
    actualizar=getattr(catalogo,'actualizar_'+entidad)
    args_edicion=(rb['id'],None,'Ajeno',None) if entidad=='categoria' else (rb['id'],'Ajeno',None)
    assert actualizar(*args_edicion,empresa_id=a['id']) is None
    args_edicion=(ra['id'],None,'Propio',None) if entidad=='categoria' else (ra['id'],'Propio',None)
    assert actualizar(*args_edicion,empresa_id=a['id'])['nombre']=='Propio'
    assert getattr(catalogo,'desactivar_'+entidad)(rb['id'],empresa_id=a['id']) is False
    assert getattr(catalogo,'obtener_'+entidad+'_por_id')(rb['id'],empresa_id=b['id'])['activo'] is True


def test_categoria_recursiva_no_modifica_otra_empresa(empresas):
    a,b,_,_=empresas
    raiz=catalogo.crear_categoria(None,'Raiz',None,empresa_id=a['id'])
    hija=catalogo.crear_categoria(raiz['id'],'Hija',None,empresa_id=a['id'])
    ajena=catalogo.crear_categoria(None,'Raiz',None,empresa_id=b['id'])
    assert catalogo.obtener_descendientes_categoria(raiz['id'],empresa_id=a['id'])==[hija['id']]
    assert catalogo.desactivar_categoria(raiz['id'],empresa_id=a['id'])
    assert catalogo.obtener_categoria_por_id(hija['id'],empresa_id=a['id'])['activo'] is False
    assert catalogo.obtener_categoria_por_id(ajena['id'],empresa_id=b['id'])['activo'] is True
    assert catalogo.activar_categoria(raiz['id'],empresa_id=a['id'])
    assert catalogo.obtener_categoria_por_id(hija['id'],empresa_id=a['id'])['activo'] is True


def test_integridad_cruzada_y_sku_repetido(empresas):
    a,b,_,_=empresas
    sa,pa,va=mercaderia(a);sb,pb,vb=mercaderia(b)
    assert va!=vb
    with pytest.raises(psycopg2.Error):
        consulta('INSERT INTO inventario_sucursal(empresa_id,sucursal_id,producto_variante_id) VALUES(%s,%s,%s)',(a['id'],sa,vb))


def test_suspension_permite_consultas_y_pendientes_bloquea_altas(empresas):
    import httpx
    from app.main import app
    a,b,_,actor=empresas
    token=iniciar_sesion(LoginRequest(identificador=a['codigo'],password='Prueba-aislada-123',empresa_codigo=a['codigo'])).access_token
    saas.cambiar_estado_empresa(a['id'],'SUSPENDIDA',actor)
    # La identidad sigue siendo válida para entrar y resolver pendientes.
    assert iniciar_sesion(LoginRequest(identificador=a['codigo'],password='Prueba-aislada-123',empresa_codigo=a['codigo'])).access_token
    async def verificar():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://pruebas') as client:
            h={'Authorization':'Bearer '+token,'X-Empresa-Codigo':a['codigo']}
            r=await client.get('/api/v1/mi-empresa/plan',headers=h)
            assert r.status_code==200,r.text
            assert r.json()['operaciones_habilitadas'] is False
            assert (await client.get('/api/v1/categorias',headers=h)).status_code==200
            assert (await client.post('/api/v1/categorias',headers=h,json={'nombre':'Nueva'})).status_code==403
            # Una orden inexistente llega al servicio, en lugar del bloqueo general.
            assert (await client.post('/api/v1/pagos/qr/confirmar/9999999',headers=h)).status_code==404
            h['X-Empresa-Codigo']=b['codigo']
            assert (await client.get('/api/v1/categorias',headers=h)).status_code==403
    asyncio.run(verificar())


def test_vencimiento_bloquea_venta_reserva_checkout_y_registro(empresas):
    from app.modules.ventas_inventario.repositories.inventario_repository import crear_venta_presencial
    from app.modules.reservas.repositories.reserva_repository import crear_reserva_desde_carrito
    from app.modules.ventas_inventario.repositories.pago_repository import crear_orden_desde_carrito
    a,_,_,_=empresas
    consulta("UPDATE suscripcion SET fecha_vencimiento='2020-01-02' WHERE empresa_id=%s",(a['id'],))
    for llamada in [lambda:exigir_operaciones_empresa(a['id']),lambda:crear_venta_presencial(a['admin_usuario_id'],a['id'],999,None,'EFECTIVO',None,[{}]),lambda:crear_reserva_desde_carrito(a['admin_usuario_id'],a['id'],999,date.today(),None),lambda:crear_orden_desde_carrito(999,a['admin_usuario_id'],999,empresa_id=a['id']),lambda:cliente(a)]:
        with pytest.raises(HTTPException) as error:
            llamada()
        assert error.value.status_code==403


def test_cupo_usuarios_concurrente(empresas):
    a,_,plan,_=empresas
    consulta('UPDATE plan SET limites=jsonb_set(limites,\'{usuarios}\',\'2\') WHERE id=%s',(plan['id'],))
    def alta(_):
        try:cliente(a);return 'OK'
        except HTTPException as e:return e.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados=list(pool.map(alta,range(2)))
    assert sorted(map(str,resultados))==['409','OK']
    assert consulta('SELECT count(*) AS n FROM usuario WHERE empresa_id=%s AND activo=TRUE',(a['id'],),True)['n']==2


def test_reserva_concurrente_ultima_unidad(empresas):
    from app.modules.reservas.repositories.carrito_repository import agregar_item_carrito
    from app.modules.reservas.repositories.reserva_repository import crear_reserva_desde_carrito
    a,_,_,_=empresas
    sucursal,_,variante=mercaderia(a,1)
    clientes=[cliente(a),cliente(a)]
    for _,cid,_ in clientes:agregar_item_carrito(cid,variante,sucursal,1)
    def reservar(cl):
        try:crear_reserva_desde_carrito(cl[0],a['id'],sucursal,date.today()+timedelta(days=1),None);return 'OK'
        except ValueError:return 'SIN_STOCK'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(reservar,clientes))==['OK','SIN_STOCK']
    assert consulta('SELECT stock_reservado FROM inventario_sucursal WHERE empresa_id=%s',(a['id'],),True)['stock_reservado']==1


def test_respaldo_empresa_restauracion_y_otra_empresa_intacta(empresas,tmp_path,monkeypatch):
    a,b,_,actor=empresas
    mercaderia(a);mercaderia(b);cliente(a);cliente(b)
    monkeypatch.setenv('STYLEAR_BACKUP_DIR',str(tmp_path/'privado'))
    monkeypatch.setenv('STYLEAR_BACKUP_KEY',Fernet.generate_key().decode())
    monkeypatch.setenv('STYLEAR_BACKUP_RETENTION_DAYS','7')
    static=tmp_path/'static'
    static.mkdir()
    (static/'prenda.jpg').write_bytes(b'imagen-ficticia')
    monkeypatch.setattr(respaldos,'STATIC',static)
    consulta("INSERT INTO imagen_producto(producto_id,url,empresa_id) SELECT id,'/static/prenda.jpg',empresa_id FROM producto WHERE empresa_id=%s",(a['id'],))
    antes_b=consulta('SELECT to_jsonb(p) AS fila FROM producto p WHERE empresa_id=%s ORDER BY id',(b['id'],))
    copia=respaldos.crear_respaldo(actor,a['id']);rid=UUID(str(copia['id']))
    assert len(list((tmp_path/'privado').glob('*.fernet')))==1
    previa=respaldos.previsualizar_restauracion(rid,actor)
    (static/'prenda.jpg').unlink()
    consulta("UPDATE producto SET nombre='MODIFICADO' WHERE empresa_id=%s",(a['id'],))
    saas.cambiar_estado_empresa(a['id'],'SUSPENDIDA',actor)
    assert respaldos.restaurar_respaldo(rid,actor,previa['confirmacion'])['estado']=='RESTAURADO'
    assert consulta('SELECT nombre FROM producto WHERE empresa_id=%s',(a['id'],),True)['nombre']=='Prenda'
    assert (static/'prenda.jpg').read_bytes()==b'imagen-ficticia'
    assert consulta('SELECT to_jsonb(p) AS fila FROM producto p WHERE empresa_id=%s ORDER BY id',(b['id'],))==antes_b
    assert consulta("SELECT count(*) AS n FROM evento_plataforma WHERE accion='RESTAURAR_RESPALDO' AND empresa_id=%s",(a['id'],),True)['n']==1


def test_respaldo_global_restaurable_en_destino_vacio(empresas,tmp_path,monkeypatch):
    from psycopg2.extensions import make_dsn
    _,_,_,actor=empresas
    destino='stylear_test_restore_'+uuid4().hex[:8]
    admin=psycopg2.connect(DSN);admin.autocommit=True
    try:
        with admin.cursor() as c:c.execute('CREATE DATABASE '+destino)
        dsn_destino=make_dsn(DSN,dbname=destino)
        monkeypatch.setenv('STYLEAR_BACKUP_DIR',str(tmp_path/'privado'))
        monkeypatch.setenv('STYLEAR_BACKUP_KEY',Fernet.generate_key().decode())
        monkeypatch.setenv('STYLEAR_BACKUP_RETENTION_DAYS','7')
        monkeypatch.setenv('STYLEAR_RESTORE_DATABASE_URL',dsn_destino)
        monkeypatch.setenv('STYLEAR_RESTORE_ASSETS_DIR',str(tmp_path/'assets'))
        # Evita copiar las fotos históricas: el ensayo usa un directorio de assets ficticios.
        monkeypatch.setattr(respaldos,'STATIC',tmp_path/'static')
        copia=respaldos.crear_respaldo(actor)
        rid=UUID(str(copia['id']))
        assert respaldos.restaurar_respaldo(rid,actor,'RESTAURAR '+str(rid))['destino']=='ENSAYO'
        otro=psycopg2.connect(dsn_destino)
        try:
            with otro.cursor() as c:
                c.execute('SELECT count(*) FROM empresa')
                assert c.fetchone()[0]==consulta('SELECT count(*) AS n FROM empresa',una=True)['n']
        finally:otro.close()
    finally:
        with admin.cursor() as c:c.execute('DROP DATABASE IF EXISTS '+destino+' WITH (FORCE)')
        admin.close()


def test_api_catalogos_planes_y_separacion_saas(empresas):
    import httpx
    from app.main import app
    a,b,plan,actor=empresas
    ta=iniciar_sesion(LoginRequest(identificador=a['codigo'],password='Prueba-aislada-123',empresa_codigo=a['codigo'])).access_token
    tb=iniciar_sesion(LoginRequest(identificador=b['codigo'],password='Prueba-aislada-123',empresa_codigo=b['codigo'])).access_token
    async def verificar():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://pruebas') as c:
            ha={'Authorization':'Bearer '+ta};hb={'Authorization':'Bearer '+tb}
            ra=await c.post('/api/v1/categorias',headers=ha,json={'nombre':'Nombre repetido'})
            rb=await c.post('/api/v1/categorias',headers=hb,json={'nombre':'Nombre repetido'})
            assert ra.status_code==200,ra.text
            assert rb.status_code==200,rb.text
            assert (await c.get('/api/v1/categorias/'+str(rb.json()['id']),headers=ha)).status_code==404
            assert (await c.get('/api/v1/saas/empresas',headers=ha)).status_code==403
            assert (await c.get('/api/v1/saas/respaldos',headers=ha)).status_code==403
            consulta("UPDATE plan SET funciones=jsonb_set(funciones,'{reportes}','false') WHERE id=%s",(plan['id'],))
            r=await c.post('/api/v1/reportes/generar',headers=ha,json={'tipo':'VENTAS','fecha_desde':'2026-01-01','fecha_hasta':'2026-10-22'})
            assert r.status_code==403,r.text
    asyncio.run(verificar())


def test_migracion_conserva_registros_heredados():
    import subprocess,sys
    from psycopg2.extensions import make_dsn
    from init_db import SQL_FILES
    nombre='stylear_test_legacy_'+uuid4().hex[:8]
    admin=psycopg2.connect(DSN);admin.autocommit=True
    try:
        with admin.cursor() as c:c.execute('CREATE DATABASE '+nombre)
        dsn=make_dsn(DSN,dbname=nombre)
        conn=psycopg2.connect(dsn)
        try:
            with conn.cursor() as c:
                for rel in SQL_FILES:
                    c.execute(Path(rel).read_text(encoding='utf-8'));conn.commit()
                c.execute("INSERT INTO usuario(nombre,apellido,username,correo,password_hash) VALUES('Anterior','Prueba','anterior','anterior@example.invalid',%s) RETURNING id",(hashear_password('Prueba-heredada-123'),))
                uid=c.fetchone()[0]
                c.execute("INSERT INTO usuario_rol(usuario_id,rol_id) SELECT %s,id FROM rol WHERE nombre='ADMINISTRADOR'",(uid,))
                c.execute("INSERT INTO categoria(nombre) VALUES('Heredada') RETURNING id")
                cid=c.fetchone()[0]
                c.execute("INSERT INTO producto(categoria_id,nombre) VALUES(%s,'Producto heredado') RETURNING id",(cid,))
                pid=c.fetchone()[0]
            conn.commit()
        finally:conn.close()
        env={**os.environ,'DATABASE_URL':dsn}
        resultado=subprocess.run([sys.executable,'-B','init_db.py'],env=env,capture_output=True,text=True,timeout=60)
        assert resultado.returncode==0,resultado.stdout+resultado.stderr
        conn=psycopg2.connect(dsn)
        try:
            with conn.cursor() as c:
                c.execute("SELECT p.id,p.nombre,e.codigo FROM producto p JOIN empresa e ON e.id=p.empresa_id WHERE p.id=%s",(pid,))
                assert c.fetchone()==(pid,'Producto heredado','stylear')
                c.execute("SELECT u.id,e.codigo FROM usuario u JOIN empresa e ON e.id=u.empresa_id WHERE u.id=%s",(uid,))
                assert c.fetchone()==(uid,'stylear')
                c.execute("SELECT r.nombre FROM rol r JOIN usuario_rol ur ON ur.rol_id=r.id WHERE ur.usuario_id=%s",(uid,))
                assert c.fetchone()[0]=='ADMINISTRADOR'
        finally:conn.close()
    finally:
        with admin.cursor() as c:c.execute('DROP DATABASE IF EXISTS '+nombre+' WITH (FORCE)')
        admin.close()
