"""Base local desechable explícita; Firebase y correo nunca reales."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4, UUID

import pytest
from fastapi import HTTPException

from test_multitenant_integration import actor, empresas, consulta, cliente, mercaderia
from test_cu26_planes_integration import programar, r2_simulado
from app.database.connection import get_connection
from app.modules.autenticacion.repositories.perfil_repository import _transaccion
from app.modules.autenticacion.repositories.sesion_repository import crear_sesion
from app.modules.inteligencia.repositories import reporte_repository as repo
from app.modules.inteligencia.services import reporte_service as reportes
from app.modules.inteligencia.schemas.reportes.reporte_request import DashboardRequest, DetalleReporteRequest
from app.modules.ventas_inventario.services import notificaciones_service as avisos, push_worker as push


@pytest.fixture(autouse=True)
def sin_proveedores(monkeypatch):
    monkeypatch.setenv('STYLEAR_FIREBASE_PROJECT_ID','')
    monkeypatch.setenv('STYLEAR_FIREBASE_CREDENTIALS','')
    def bloquear(*args,**kwargs):
        raise AssertionError('Servicio externo no permitido en estas pruebas.')
    monkeypatch.setattr(push,'enviar_fcm',bloquear)
    monkeypatch.setattr('app.core.email.enviar_correo_con_adjunto',bloquear)


def venta(e,s,c=None,total=100,tipo='PRESENCIAL',estado='COMPLETADA'):
    return consulta('''INSERT INTO venta(empresa_id,sucursal_id,cliente_id,codigo,total,subtotal,tipo,estado)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
        (e['id'],s,c,uuid4().hex,total,total,tipo,estado),True)['id']


def orden(e,v,c,monto=30,estado='PAGADO'):
    return consulta('''INSERT INTO orden_pago(empresa_id,venta_id,cliente_id,monto_total,estado,fecha_pago)
        VALUES(%s,%s,%s,%s,%s,CURRENT_TIMESTAMP) RETURNING id''',
        (e['id'],v,c,monto,estado),True)['id']


def request_dashboard(**extra):
    return DashboardRequest(fecha_desde=date.today(),fecha_hasta=date.today(),**extra)


def test_dashboard_separa_ventas_cobros_pendientes_y_reembolsos(empresas):
    a,b,_,_=empresas
    s,_,vid=mercaderia(a); sb,_,_=mercaderia(b)
    uid,c,_=cliente(a)
    pos=venta(a,s,c,100)
    web=venta(a,s,c,60,'WEB')
    venta(a,s,c,999,'WEB','ANULADA')
    pendiente=venta(a,s,c,500,'WEB','PENDIENTE_PAGO')
    orden(a,pendiente,c,500,'PENDIENTE')
    orden(a,pos,c,100)  # No sumar nuevamente la caja si hay una orden pagada.
    op=orden(a,web,c,30); orden(a,web,c,30)
    venta(b,sb,total=9000)
    consulta('''INSERT INTO venta_detalle(empresa_id,venta_id,producto_variante_id,cantidad,precio_unitario,subtotal)
        VALUES(%s,%s,%s,2,30,60)''',(a['id'],web,vid))
    consulta('''INSERT INTO reembolso_pago(empresa_id,orden_id,monto,moneda,metodo,motivo,estado,referencia)
        VALUES(%s,%s,10,'BOB','TARJETA','Prueba','CONFIRMADO','mismo_reembolso')''',(a['id'],op))
    consulta('''INSERT INTO devolucion(empresa_id,codigo,venta_id,cliente_id,sucursal_id,estado,motivo,
        monto_solicitado,monto_aprobado,moneda,referencia_reembolso,fecha_reembolso,clave_idempotencia)
        VALUES(%s,%s,%s,%s,%s,'REEMBOLSADA','Prueba',10,10,'BOB','mismo_reembolso',CURRENT_TIMESTAMP,'prueba-'||%s)''',
        (a['id'],uuid4().hex,web,c,s,uuid4().hex))
    resultado=reportes.generar_dashboard(request_dashboard(),a['id'])
    d=resultado['datos']
    assert (d['ventas'],d['ventas_presenciales'],d['ventas_digitales'])==(2,1,1)
    assert Decimal(d['importe_vendido'])==160
    flujo=d['flujos'][0]
    assert [Decimal(flujo[k]) for k in ('cobrado','reembolsado','neto')]==[160,10,150]
    assert d['productos_mas_vendidos'][0]['unidades']==2
    assert resultado['comparacion']['indicadores']['ventas']['variacion_porcentual'] is None
    digital=reportes.generar_dashboard(request_dashboard(tipo_venta='DIGITAL'),a['id'])['datos']
    assert digital['ventas']==1 and Decimal(digital['importe_vendido'])==60
    detalle=reportes.generar_detalle(DetalleReporteRequest(tipo='PRODUCTOS_MAS_VENDIDOS',fecha_desde=date.today(),fecha_hasta=date.today()),a['id'])
    assert Decimal(detalle['resumen']['importe'])==60


def test_ordenes_en_distintas_monedas_no_se_suman(empresas):
    a,_,_,_=empresas
    s,_,_=mercaderia(a)
    uid,c,_=cliente(a)
    v=venta(a,s,c,100,'WEB')
    orden(a,v,c,10)
    op=orden(a,v,c,20)
    consulta("UPDATE orden_pago SET moneda='USD' WHERE id=%s",(op,))
    r=DetalleReporteRequest(tipo='PAGOS',fecha_desde=date.today(),fecha_hasta=date.today())
    paginado=reportes.generar_detalle(r,a['id'])
    assert paginado['resumen']['importe'] is None
    assert {m['moneda']:Decimal(m['importe']) for m in paginado['resumen']['importes_por_moneda']}=={'BOB':10,'USD':20}
    normal=reportes.generar_reporte(r,a['id'])
    assert len(normal['indicadores'])==3
    dashboard=reportes.generar_dashboard(request_dashboard(),a['id'])['datos']
    assert {m['moneda']:Decimal(m['cobrado']) for m in dashboard['flujos']}=={'BOB':10,'USD':20}


@pytest.mark.parametrize('tipo',['VENTAS','PRODUCTOS_MAS_VENDIDOS','INVENTARIO','RESERVAS','MOVIMIENTOS','TRANSFERENCIAS','PAGOS','DELIVERIES','USUARIOS'])
def test_todos_los_detalles_paginados_ejecutan_sql_real(empresas,tipo):
    a,_,_,_=empresas
    s,_,_=mercaderia(a)
    venta(a,s)
    r=DetalleReporteRequest(tipo=tipo,fecha_desde=date.today(),fecha_hasta=date.today(),tamano=1)
    d=reportes.generar_detalle(r,a['id'])
    assert d['total_filas']>=len(d['filas']) and len(d['filas'])<=1


def test_mas_de_5000_filas_totales_completos_y_orden_estable(empresas):
    a,_,_,_=empresas
    s,_,_=mercaderia(a)
    consulta('''INSERT INTO venta(empresa_id,sucursal_id,codigo,subtotal,total)
        SELECT %s,%s,%s||n,2,2 FROM generate_series(1,5200) n''',(a['id'],s,uuid4().hex))
    r=DetalleReporteRequest(tipo='VENTAS',fecha_desde=date.today(),fecha_hasta=date.today(),tamano=100)
    uno=reportes.generar_detalle(r,a['id'])
    dos=reportes.generar_detalle(r.model_copy(update={'pagina':2}),a['id'])
    assert uno['total_filas']==dos['total_filas']==5200
    assert Decimal(uno['resumen']['importe'])==10400
    assert len(uno['filas'])==len(dos['filas'])==100
    assert not {f['id'] for f in uno['filas']} & {f['id'] for f in dos['filas']}
    assert uno['serie_grafico']==dos['serie_grafico']
    with pytest.raises(HTTPException):
        reportes.generar_reporte(r,a['id'])


def test_encargado_solo_su_sucursal_y_sin_usuarios(empresas):
    from test_cu11_cu15_integration import personal
    a,_,_,_=empresas
    s,_,_=mercaderia(a)
    empleado,_=personal(a,s,'ENCARGADO_SUCURSAL')
    actor={'id':empleado['admin_usuario_id'],'empresa_id':a['id'],'roles':['ENCARGADO_SUCURSAL']}
    r=request_dashboard()
    assert reportes.limitar_reporte(actor,r).sucursal_id==s
    with pytest.raises(HTTPException) as error:
        reportes.limitar_reporte(actor,r.model_copy(update={'sucursal_id':s+1000}))
    assert error.value.status_code==403
    with pytest.raises(HTTPException):
        reportes.limitar_reporte(actor,DetalleReporteRequest(tipo='USUARIOS',fecha_desde=date.today(),fecha_hasta=date.today()))


def test_editar_programacion_preserva_pausa_historia_y_revision(empresas):
    a,b,_,_=empresas
    p=programar(a,activo=False)
    p=repo.actualizar_estado_reporte_programado(p['id'],False,a['id'])
    nuevo=repo.editar_reporte_programado(p['id'],a['id'],p['revision'],{'titulo':'Nuevo título'})
    assert not nuevo['activo'] and nuevo['pausa_motivo']=='USUARIO'
    assert nuevo['revision']==p['revision']+1
    with pytest.raises(HTTPException) as error:
        repo.editar_reporte_programado(p['id'],a['id'],p['revision'],{'titulo':'Obsoleto'})
    assert error.value.status_code==409
    with pytest.raises(HTTPException) as error:
        repo.editar_reporte_programado(p['id'],b['id'],nuevo['revision'],{'titulo':'Ajeno'})
    assert error.value.status_code==404
    def editar(titulo):
        try:
            return repo.editar_reporte_programado(p['id'],a['id'],nuevo['revision'],{'titulo':titulo})['titulo']
        except HTTPException as e:
            return e.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados=list(pool.map(editar,['Uno','Dos']))
    assert resultados.count(409)==1


def instalar(a):
    uid,c,_=cliente(a)
    sesion=crear_sesion(uid,a['id'])
    actor={'id':uid,'empresa_id':a['id'],'version_acceso':0,'_sesion_id':sesion['id']}
    avisos.registrar(actor,avisos.DispositivoRequest(instalacion_id=uuid4(),token=uuid4().hex,plataforma='android'))
    return actor,c


def emitir(a,c,recurso,clave=None,categoria='COMPRA'):
    with _transaccion() as cur:
        return avisos.emitir_cliente(cur,a['id'],c,clave or uuid4().hex,'Compra','Aviso',categoria,'VENTA',recurso)


def test_instalacion_renovada_cambio_empresa_no_entrega_cola_anterior(empresas,monkeypatch):
    a,b,_,_=empresas
    actores=[]
    for empresa in (a,b):
        uid,c,_=cliente(empresa)
        sesion=crear_sesion(uid,empresa['id'])
        actores.append(({'id':uid,'empresa_id':empresa['id'],'version_acceso':0,'_sesion_id':sesion['id']},c))
    aa,ca=actores[0]; ab,cb=actores[1]
    instalacion=uuid4()
    def registrar(actor,token):
        avisos.registrar(actor,avisos.DispositivoRequest(instalacion_id=instalacion,token=token,plataforma='android'))
    sa,_,_=mercaderia(a); sb,_,_=mercaderia(b)
    va=venta(a,sa,ca); vb=venta(b,sb,cb)
    registrar(aa,uuid4().hex)
    primero=emitir(a,ca,va)
    renovado=uuid4().hex
    registrar(aa,renovado)
    monkeypatch.setenv('STYLEAR_FIREBASE_PROJECT_ID','simulado')
    monkeypatch.setenv('STYLEAR_FIREBASE_CREDENTIALS','simulado')
    llamadas=[]
    monkeypatch.setattr(push,'enviar_fcm',lambda token,nid,empresa: llamadas.append((token,nid,empresa)) or 'FCM/ensayo')
    push.procesar(100)
    assert (renovado,primero,a['id']) in llamadas
    pendiente_a=emitir(a,ca,va)
    token_b=uuid4().hex
    registrar(ab,token_b)
    # Una baja tardía de la cuenta anterior no debe desvincular la cuenta nueva.
    avisos.retirar(aa,instalacion)
    fila=consulta('SELECT * FROM dispositivo_push WHERE instalacion_id=%s',(str(instalacion),),True)
    assert fila['activo'] and fila['usuario_id']==ab['id'] and fila['empresa_id']==b['id']
    propio_b=emitir(b,cb,vb)
    push.procesar(100)
    assert consulta('SELECT estado FROM salida_push WHERE notificacion_id=%s',(pendiente_a,),True)['estado']=='OMITIDO'
    assert not any(nid==pendiente_a for _,nid,_ in llamadas)
    assert (token_b,propio_b,b['id']) in llamadas
    with pytest.raises(HTTPException) as error:
        avisos.destino(ab,primero)
    assert error.value.status_code==404
    avisos.preferencias(ab,avisos.PreferenciasRequest(categorias={'COMPRA':False}))
    silenciado=emitir(b,cb,vb)
    assert not consulta('SELECT id FROM salida_push WHERE notificacion_id=%s',(silenciado,))
    assert any(n['id']==silenciado for n in avisos.bandeja(ab)['avisos'])
    avisos.retirar(ab,instalacion)
    assert not consulta('SELECT activo FROM dispositivo_push WHERE instalacion_id=%s',(str(instalacion),),True)['activo']


def test_bandeja_transaccional_deduplicada_preferencias_y_destino(empresas):
    a,b,_,_=empresas
    s,_,_=mercaderia(a)
    actor,c=instalar(a)
    v=venta(a,s,c)
    n=emitir(a,c,v,'evento-unico')
    assert emitir(a,c,v,'evento-unico') is None
    with pytest.raises(RuntimeError):
        with _transaccion() as cur:
            avisos.emitir_cliente(cur,a['id'],c,'rollback','T','M','COMPRA','VENTA',v)
            raise RuntimeError('Revertir operación')
    assert avisos.resumen(actor)=={'total':1,'no_leidas':1}
    assert avisos.destino(actor,n)['disponible']
    avisos.preferencias(actor,avisos.PreferenciasRequest(categorias={'COMPRA':False}))
    silenciado=emitir(a,c,v)
    assert consulta('SELECT id FROM salida_push WHERE notificacion_id=%s',(silenciado,))==[]
    assert avisos.bandeja(actor,tamano=1)['no_leidas']==2
    assert avisos.bandeja(actor,pagina=2,tamano=1)['avisos'][0]['id']==n
    assert avisos.leer_todas(actor)['actualizadas']==2
    assert avisos.leer_todas(actor)['actualizadas']==0
    assert avisos.bandeja(actor,leida=False)['total']==0
    uid2,c2,_=cliente(a)
    with pytest.raises(HTTPException):
        avisos.destino({'id':uid2,'empresa_id':a['id']},n)
    # Incluso un destino manipulado no concede acceso a una venta ajena.
    ajena=venta(a,s,c2)
    falso=emitir(a,c,ajena)
    assert avisos.destino(actor,falso)=={'disponible':False,'accion':'ABRIR_BANDEJA'}
    assert avisos.trazabilidad(actor,n)['visualizacion_sistema']=='NO_ACREDITADA_POR_FCM'


def test_cola_backoff_preferencia_actual_y_aceptacion_no_entrega(empresas,monkeypatch):
    a,_,_,_=empresas
    s,_,_=mercaderia(a)
    actor,c=instalar(a); v=venta(a,s,c)
    n=emitir(a,c,v)
    monkeypatch.setenv('STYLEAR_FIREBASE_PROJECT_ID','simulado')
    monkeypatch.setenv('STYLEAR_FIREBASE_CREDENTIALS','simulado')
    llamadas=[]
    def fallar(*args):
        llamadas.append(args)
        raise RuntimeError('Proveedor temporalmente indisponible')
    monkeypatch.setattr(push,'enviar_fcm',fallar)
    push.procesar(100)
    salida=consulta('SELECT * FROM salida_push WHERE notificacion_id=%s',(n,),True)
    assert salida['estado']=='FALLIDO' and salida['intentos']==1
    push.procesar(100)
    assert sum(1 for args in llamadas if args[1]==n)==1
    consulta("UPDATE salida_push SET proximo_intento=CURRENT_TIMESTAMP-INTERVAL '1 second' WHERE notificacion_id=%s",(n,))
    monkeypatch.setattr(push,'enviar_fcm',lambda *args:'FCM/aceptado')
    push.procesar(100)
    salida=consulta('SELECT * FROM salida_push WHERE notificacion_id=%s',(n,),True)
    assert salida['estado']=='ENVIADO' and salida['aceptado_en'] is not None
    assert not avisos.trazabilidad(actor,n)['leida']
    n2=emitir(a,c,v)
    avisos.preferencias(actor,avisos.PreferenciasRequest(categorias={'COMPRA':False}))
    push.procesar(100)
    assert consulta('SELECT estado FROM salida_push WHERE notificacion_id=%s',(n2,),True)['estado']=='OMITIDO'


def test_cola_concurrente_solo_envia_una_vez_y_rechaza_sesion_cerrada(empresas,monkeypatch):
    a,_,_,_=empresas
    s,_,_=mercaderia(a)
    actor,c=instalar(a); v=venta(a,s,c)
    n=emitir(a,c,v)
    monkeypatch.setenv('STYLEAR_FIREBASE_PROJECT_ID','simulado')
    monkeypatch.setenv('STYLEAR_FIREBASE_CREDENTIALS','simulado')
    llamadas=[]
    monkeypatch.setattr(push,'enviar_fcm',lambda token,nid,e:llamadas.append(nid) or 'FCM/ok')
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _:push.procesar(100),range(2)))
    assert llamadas.count(n)==1
    n2=emitir(a,c,v)
    consulta('UPDATE sesion SET activa=FALSE WHERE id=%s',(actor['_sesion_id'],))
    push.procesar(100)
    assert n2 not in llamadas
    assert consulta('SELECT estado FROM salida_push WHERE notificacion_id=%s',(n2,),True)['estado']=='OMITIDO'


def test_restaurar_no_reenvia_avisos_y_preserva_otra_empresa(empresas,r2_simulado):
    from app.modules.administracion.services import respaldo_service as backups
    from app.modules.administracion.repositories import empresa_saas_repository as saas
    a,b,_,as_id=empresas
    s,_,_=mercaderia(a)
    actor,c=instalar(a); v=venta(a,s,c)
    n=emitir(a,c,v)
    avisos.preferencias(actor,avisos.PreferenciasRequest(categorias={'PAGO':False}))
    actor_b,cb=instalar(b)
    copia=backups.crear_respaldo(a['admin_usuario_id'],a['id'])
    saas.cambiar_estado_empresa(a['id'],'SUSPENDIDA',as_id)
    resultado=backups.restaurar_respaldo(UUID(str(copia['id'])),as_id,'RESTAURAR '+str(copia['id']),a['id'])
    assert resultado['estado']=='RESTAURADO'
    assert consulta('SELECT estado FROM salida_push WHERE notificacion_id=%s',(n,),True)['estado']=='OMITIDO'
    assert not consulta('SELECT activo FROM dispositivo_push WHERE usuario_id=%s',(actor['id'],),True)['activo']
    assert consulta('SELECT activo FROM dispositivo_push WHERE usuario_id=%s',(actor_b['id'],),True)['activo']
    assert not avisos.preferencias(actor)['categorias']['PAGO']


def test_api_alcance_sucursal_en_dashboard_detalle_y_exportacion(empresas):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.modules.autenticacion.dependencies.usuario_actual import obtener_usuario_actual
    from test_cu11_cu15_integration import personal
    a,b,_,_=empresas
    s,_,_=mercaderia(a)
    empleado,_=personal(a,s,'ENCARGADO_SUCURSAL')
    ciudad=consulta('SELECT ciudad_id FROM sucursal WHERE id=%s',(s,),True)['ciudad_id']
    otro=consulta("INSERT INTO sucursal(empresa_id,ciudad_id,nombre,direccion) VALUES(%s,%s,'Otra','Otra') RETURNING id",(a['id'],ciudad),True)['id']
    venta(a,s,total=10); venta(a,otro,total=500)
    actor={'id':empleado['admin_usuario_id'],'empresa_id':a['id'],'roles':['ENCARGADO_SUCURSAL']}
    app.dependency_overrides[obtener_usuario_actual]=lambda:actor
    api=TestClient(app)
    base={'fecha_desde':str(date.today()),'fecha_hasta':str(date.today())}
    try:
        d=api.post('/api/v1/reportes/dashboard',json=base)
        assert d.status_code==200,d.text
        assert Decimal(d.json()['datos']['importe_vendido'])==10
        catalogo=api.get('/api/v1/reportes/catalogo').json()
        assert [r['id'] for r in catalogo['sucursales']]==[s]
        assert 'USUARIOS' not in [r['id'] for r in catalogo['tipos']]
        for ruta in ('generar','detalle','exportar/pdf','exportar/excel'):
            assert api.post('/api/v1/reportes/'+ruta,json={**base,'tipo':'VENTAS','sucursal_id':otro}).status_code==403
        assert api.post('/api/v1/reportes/detalle',json={**base,'tipo':'USUARIOS'}).status_code==403
        assert api.get('/api/v1/reportes/programados').status_code==403
        actor['roles']=['CLIENTE']
        assert api.post('/api/v1/reportes/dashboard',json=base).status_code==403
    finally:
        app.dependency_overrides.pop(obtener_usuario_actual,None)
        api.close()


def test_reserva_eventos_comparten_transaccion_y_no_duplican(empresas,monkeypatch):
    from app.modules.reservas.repositories import carrito_repository as carrito, reserva_repository as reservas
    from app.modules.reservas.services.vencimiento_service import vencer_reservas
    a,_,_,_=empresas
    s,_,vid=mercaderia(a)
    actor,c=instalar(a)
    carrito.agregar_item_carrito(c,vid,s,1)
    notificar=avisos.avisar_reserva
    def error(*args):
        raise RuntimeError('Fallo simulado antes del commit')
    monkeypatch.setattr(avisos,'avisar_reserva',error)
    with pytest.raises(RuntimeError):
        reservas.crear_reserva_desde_carrito(actor['id'],a['id'],s,date.today()+timedelta(days=1),None,uuid4())
    assert avisos.resumen(actor)['total']==0
    assert consulta('SELECT id FROM reserva WHERE empresa_id=%s',(a['id'],))==[]
    assert consulta('SELECT stock_reservado FROM inventario_sucursal WHERE sucursal_id=%s',(s,),True)['stock_reservado']==0
    monkeypatch.setattr(avisos,'avisar_reserva',notificar)
    clave=uuid4()
    r=reservas.crear_reserva_desde_carrito(actor['id'],a['id'],s,date.today()+timedelta(days=1),None,clave)
    assert reservas.crear_reserva_desde_carrito(actor['id'],a['id'],s,date.today()+timedelta(days=1),None,clave)['id']==r['id']
    assert avisos.resumen(actor)['total']==1
    consulta("UPDATE reserva SET fecha_expiracion=CURRENT_TIMESTAMP-INTERVAL '1 second' WHERE id=%s",(r['id'],))
    vencer_reservas(a['id']); vencer_reservas(a['id'])
    bandeja=avisos.bandeja(actor,categoria='RESERVA')
    assert bandeja['total']==2
    assert avisos.destino(actor,bandeja['avisos'][0]['id'])['recurso_tipo']=='RESERVA'


def test_cola_caducada_token_retirado_y_limite_de_intentos(empresas,monkeypatch):
    a,_,_,_=empresas
    s,_,_=mercaderia(a)
    actor,c=instalar(a); v=venta(a,s,c)
    caducado=emitir(a,c,v)
    consulta("UPDATE salida_push SET expira_en=CURRENT_TIMESTAMP-INTERVAL '1 second' WHERE notificacion_id=%s",(caducado,))
    agotado=emitir(a,c,v)
    consulta("UPDATE salida_push SET estado='FALLIDO',intentos=5 WHERE notificacion_id=%s",(agotado,))
    retirado=emitir(a,c,v)
    monkeypatch.setenv('STYLEAR_FIREBASE_PROJECT_ID','simulado')
    monkeypatch.setenv('STYLEAR_FIREBASE_CREDENTIALS','simulado')
    llamadas=[]
    def enviar(token,nid,e):
        llamadas.append(nid)
        raise push.TokenRetirado()
    monkeypatch.setattr(push,'enviar_fcm',enviar)
    push.procesar(100)
    assert caducado not in llamadas and agotado not in llamadas and retirado in llamadas
    for nid in (caducado,retirado):
        assert consulta('SELECT estado FROM salida_push WHERE notificacion_id=%s',(nid,),True)['estado']=='OMITIDO'
    assert not consulta('SELECT activo FROM dispositivo_push WHERE usuario_id=%s',(actor['id'],),True)['activo']
