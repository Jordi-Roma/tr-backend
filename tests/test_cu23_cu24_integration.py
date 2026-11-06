"""Solo PostgreSQL local desechable explícito; ningún proveedor real."""
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from test_multitenant_integration import actor, empresas, consulta, cliente, mercaderia
from app.modules.inteligencia.services import asistente_service as chat, recomendacion_service as recomendaciones
from app.modules.inteligencia.repositories import asistente_repository as datos, recomendacion_repository as reco_repo
from app.modules.inteligencia.schemas.asistente.asistente_schemas import AsistenteChatRequest
from app.modules.catalogo.repositories.catalogo_publico_repository import obtener_prenda_catalogo


@pytest.fixture(autouse=True)
def sin_ia_externa(monkeypatch):
    monkeypatch.setattr(chat,'AI_ASSISTANT_PROVIDER','RULES')
    monkeypatch.setattr(recomendaciones,'AI_RECOMMENDATIONS_PROVIDER','RULES')
    import requests
    def bloquear(*args,**kwargs):
        raise AssertionError('No usar proveedores reales en las pruebas.')
    monkeypatch.setattr(requests.sessions.Session,'request',bloquear)
    monkeypatch.setattr(chat,'interpretar_asistente_con_vertex',bloquear)


def preguntar(a,mensaje,usuario=None,contexto=None):
    return chat.responder_chat_asistente(AsistenteChatRequest(mensaje=mensaje,contexto=contexto),usuario,a['id'])


def venta(a,s,c):
    return consulta('''INSERT INTO venta(empresa_id,sucursal_id,cliente_id,codigo,total,subtotal)
        VALUES(%s,%s,%s,%s,50,50) RETURNING id''',(a['id'],s,c,uuid4().hex),True)['id']


def test_chat_promocion_precio_final_variante_y_sucursal(empresas):
    a,b,_,_=empresas
    s,p,v=mercaderia(a)
    consulta("UPDATE producto SET nombre='Camisa real' WHERE id=%s",(p,))
    consulta("INSERT INTO precio_producto(empresa_id,producto_variante_id,precio,fecha_inicio) VALUES(%s,%s,100,CURRENT_DATE)",(a['id'],v))
    promo=consulta("INSERT INTO promocion(empresa_id,nombre,tipo_descuento,valor,fecha_inicio,fecha_fin) VALUES(%s,'Oferta','PORCENTAJE',20,CURRENT_DATE,CURRENT_DATE+1) RETURNING id",(a['id'],),True)['id']
    consulta('INSERT INTO promocion_producto(empresa_id,promocion_id,producto_id) VALUES(%s,%s,%s)',(a['id'],promo,p))
    consulta('INSERT INTO promocion_sucursal(empresa_id,promocion_id,sucursal_id) VALUES(%s,%s,%s)',(a['id'],promo,s))
    resultado=preguntar(a,'¿Tienen esta prenda en M y azul en Centro?',contexto={'producto_id':p})
    assert len(resultado.productos)==1
    assert resultado.productos[0].stock_real==4
    assert resultado.productos[0].variante_id==v
    assert Decimal(resultado.productos[0].precio_final_exacto)==80
    catalogo=obtener_prenda_catalogo(p,s,a['id'])
    assert catalogo['variantes'][0]['precio_final']==80
    assert catalogo['stock_total']==4  # No duplicar stock por dos precios superpuestos.
    consulta("UPDATE producto SET material='Algodón real' WHERE id=%s",(p,))
    material=preguntar(a,'¿De qué material es esta prenda?',contexto={'variante_id':v})
    assert 'Algodón real' in material.respuesta
    assert material.contexto.producto_id==p
    filtro=preguntar(a,'Camisa de menos de 85 Bs en Centro')
    assert filtro.productos and filtro.productos[0].precio_final==80
    promos=preguntar(a,'¿Qué promociones tienen?',contexto={'sucursal_id':s})
    assert promos.tipo=='promociones' and promos.productos[0].precio_final==80
    seguimiento=preguntar(a,'¿y en negro?',contexto=resultado.contexto.model_dump())
    assert not seguimiento.productos
    assert seguimiento.filtros_detectados['diagnostico']=='VARIANTE_NO_ENCONTRADA'
    assert seguimiento.contexto.talla_patrones==['m']
    consulta('UPDATE inventario_sucursal SET stock_reservado=stock_disponible WHERE sucursal_id=%s',(s,))
    agotado=preguntar(a,'¿Tienen esta prenda en M?',contexto={'producto_id':p,'sucursal_id':s})
    assert agotado.filtros_detectados['diagnostico']=='SIN_STOCK'


def test_contexto_ajeno_y_datos_inexistentes_no_se_inventan(empresas):
    a,b,_,_=empresas
    s,p,v=mercaderia(b)
    for contexto in ({'producto_id':p},{'sucursal_id':s},{'variante_id':v},{'empresa_id':b['id']}):
        with pytest.raises(HTTPException) as error:
            preguntar(a,'¿Tienen esta prenda?',contexto=contexto)
        assert error.value.status_code in (403,404)
    assert preguntar(a,'¿Tienen esta prenda en M?').aclaracion
    horario=preguntar(a,'¿A qué hora cierra Centro?')
    assert 'No hay horarios' in horario.respuesta and '18:00' not in horario.respuesta


def test_politicas_reales_y_medios_deshabilitados(empresas):
    a,b,_,_=empresas
    consulta('''INSERT INTO politica_posventa(empresa_id,cambios_habilitados,plazo_cambios,condiciones_cambios)
        VALUES(%s,TRUE,12,'Con etiquetas y revisión física')''',(a['id'],))
    respuesta=preguntar(a,'¿Puedo cambiar una prenda?')
    assert '12 días' in respuesta.respuesta and respuesta.datos[0]['cambios_habilitados']
    assert not preguntar(b,'¿Puedo cambiar una prenda?').datos[0]['cambios_habilitados']
    pagos=preguntar(a,'¿Cómo puedo pagar?')
    assert pagos.datos[0]['medios']==[] and 'No hay medios digitales' in pagos.respuesta
    reserva=preguntar(a,'¿Cómo hago una reserva?')
    assert 'gratuita' in reserva.respuesta and 'Reservar con Stripe' not in reserva.respuesta
    delivery=preguntar(a,'¿Cuánto cuesta el delivery?')
    assert delivery.tipo=='ayuda_delivery' and 'cotización' in delivery.respuesta


def test_todas_las_proyecciones_son_validas_y_privadas(empresas):
    a,b,_,_=empresas
    s,_,_=mercaderia(a)
    uid,c,_=cliente(a); uid2,c2,_=cliente(a)
    v=venta(a,s,c)
    consulta('''INSERT INTO orden_pago(empresa_id,venta_id,cliente_id,monto_total,estado)
        VALUES(%s,%s,%s,50,'PENDIENTE')''',(a['id'],v,c))
    tipos=('RESERVA','VENTA','ORDEN_PAGO','DELIVERY','DEVOLUCION','CAMBIO','REEMBOLSO_PAGO')
    for tipo in tipos:
        resultado=datos.consultar_operaciones_cliente(a['id'],uid,tipo)
        assert all('cliente_correo' not in r and 'direccion_entrega' not in r and 'observacion' not in r for r in resultado)
        assert datos.consultar_operaciones_cliente(a['id'],uid2,tipo)==[]
        assert datos.consultar_operaciones_cliente(b['id'],uid,tipo)==[]
    actor={'id':uid,'empresa_id':a['id'],'roles':['CLIENTE']}
    pago=preguntar(a,'Mis pagos',actor)
    assert pago.datos[0]['estado']=='PENDIENTE' and pago.datos[0]['importe']=='50.00'
    assert preguntar(a,'¿Dónde está mi pedido?').requiere_login
    assert preguntar(a,'Mis compras',actor).datos[0]['id']==v
    otro={'id':uid2,'empresa_id':a['id'],'roles':['CLIENTE']}
    assert not preguntar(a,'¿y ese pago?',otro,pago.contexto.model_dump()).datos


def test_reserva_chat_no_ejecuta_vencimientos_y_contexto_se_revalida(empresas):
    from app.modules.reservas.repositories.carrito_repository import agregar_item_carrito
    from app.modules.reservas.repositories.reserva_repository import crear_reserva_desde_carrito
    a,_,_,_=empresas
    s,_,v=mercaderia(a)
    uid,c,_=cliente(a)
    agregar_item_carrito(c,v,s,1)
    r=crear_reserva_desde_carrito(uid,a['id'],s,date.today()+timedelta(days=1),None)
    consulta("UPDATE reserva SET fecha_expiracion=CURRENT_TIMESTAMP-INTERVAL '1 hour' WHERE id=%s",(r['id'],))
    usuario={'id':uid,'empresa_id':a['id']}
    antes=consulta('SELECT estado FROM reserva WHERE id=%s',(r['id'],),True)
    respuesta=preguntar(a,'Mi reserva numero '+str(r['id']),usuario)
    assert respuesta.datos[0]['estado']==antes['estado']
    assert respuesta.datos[0]['fecha_expiracion']
    seguimiento=preguntar(a,'¿Cuándo vence esa reserva?',usuario,respuesta.contexto.model_dump())
    assert seguimiento.datos[0]['id']==r['id']
    assert 'vencimiento' in seguimiento.respuesta and str(r['fecha_cita']) in seguimiento.respuesta
    assert consulta('SELECT estado FROM reserva WHERE id=%s',(r['id'],),True)==antes
    assert consulta('SELECT stock_reservado FROM inventario_sucursal WHERE sucursal_id=%s',(s,),True)['stock_reservado']==1


def test_recomendaciones_precio_de_variante_disponible_y_fallback_sin_semillas(empresas):
    a,_,_,_=empresas
    s,p,v=mercaderia(a)
    consulta('UPDATE inventario_sucursal SET stock_reservado=stock_disponible WHERE sucursal_id=%s',(s,))
    assert recomendaciones._validar_respuesta(p,s,None,a['id']) is None
    consulta('UPDATE inventario_sucursal SET stock_reservado=0 WHERE sucursal_id=%s',(s,))
    assert recomendaciones._validar_respuesta(p,s,None,a['id'])['precio_final']==50
    uid,c,_=cliente(a)
    reco_repo.guardar_favorito(c,p,a['id'])
    assert recomendaciones.recomendar_para_cliente(c,a['id'])==[]  # Sin vectores no devolver la propia semilla.
    reco_repo.guardar_preferencias(c,[],False,a['id'])
    chat_usuario={'id':uid,'empresa_id':a['id']}
    assert preguntar(a,'Mis recomendaciones',chat_usuario).tipo=='personalizacion_desactivada'
    assert preguntar(a,'Mis favoritos',chat_usuario).productos


def test_api_token_invalido_revocado_y_continuidad_plan(empresas):
    from app.main import app
    from test_cuenta_integration import login
    a,b,_,_=empresas
    uid,c,nombre=cliente(a)
    api=TestClient(app)
    try:
        body={'mensaje':'Mis pagos'}
        publicas={'X-Empresa-Codigo':a['codigo']}
        assert api.post('/api/v1/asistente/chat',json=body,headers=publicas).json()['requiere_login']
        assert api.post('/api/v1/asistente/chat',json=body,headers={**publicas,'Authorization':'Bearer invalido'}).status_code==401
        assert api.post('/api/v1/asistente/chat',json=body,headers={**publicas,'Authorization':'Basic abc'}).status_code==401
        h=login(api,a,nombre)
        assert api.post('/api/v1/asistente/chat',json=body,headers={**h,'X-Empresa-Codigo':b['codigo']}).status_code==403
        consulta("UPDATE empresa SET estado='SUSPENDIDA' WHERE id=%s",(a['id'],))
        assert api.post('/api/v1/asistente/chat',json=body,headers=h).status_code==200
        consulta('UPDATE usuario SET version_acceso=version_acceso+1 WHERE id=%s',(uid,))
        assert api.post('/api/v1/asistente/chat',json=body,headers=h).status_code==401
    finally:
        api.close()


def test_reembolso_real_no_confunde_aprobacion_ni_pago_distinto(empresas):
    a,_,_,_=empresas
    s,_,_=mercaderia(a)
    uid,c,_=cliente(a); uid2,c2,_=cliente(a)
    v=venta(a,s,c)
    op=consulta('''INSERT INTO orden_pago(empresa_id,venta_id,cliente_id,monto_total,estado)
        VALUES(%s,%s,%s,50,'REEMBOLSADO') RETURNING id''',(a['id'],v,c),True)['id']
    rid=consulta('''INSERT INTO reembolso_pago(empresa_id,orden_id,monto,moneda,metodo,motivo,estado)
        VALUES(%s,%s,50,'BOB','QR','Prueba','PENDIENTE') RETURNING id''',(a['id'],op),True)['id']
    usuario={'id':uid,'empresa_id':a['id']}
    contexto={'empresa_id':a['id'],'recurso_tipo':'ORDEN_PAGO','recurso_id':op}
    pendiente=preguntar(a,'¿Y ya me devolvieron el dinero?',usuario,contexto)
    assert pendiente.datos[0]['id']==rid and not pendiente.datos[0]['reembolso_confirmado']
    consulta("UPDATE reembolso_pago SET estado='CONFIRMADO' WHERE id=%s",(rid,))
    confirmado=preguntar(a,'¿Y ya me devolvieron el dinero?',usuario,contexto)
    assert confirmado.datos[0]['reembolso_confirmado']
    assert not preguntar(a,'Mis reembolsos',{'id':uid2,'empresa_id':a['id']}).datos
    did=consulta('''INSERT INTO devolucion(empresa_id,codigo,venta_id,cliente_id,sucursal_id,estado,motivo,
        monto_solicitado,monto_aprobado,clave_idempotencia,politica_snapshot)
        VALUES(%s,%s,%s,%s,%s,'APROBADA','Prueba',10,10,%s,
        '{"plazo_devoluciones":21,"condiciones_devoluciones":"Condiciones anteriores"}') RETURNING id''',
        (a['id'],uuid4().hex,v,c,s,uuid4().hex),True)['id']
    devolucion=preguntar(a,'¿Cuáles son las condiciones?',usuario,{'recurso_tipo':'DEVOLUCION','recurso_id':did})
    assert devolucion.datos[0]['politica_aplicada']['plazo_devoluciones']==21
    assert 'Condiciones anteriores' in devolucion.respuesta


def test_candidatos_mas_alla_de_500_no_materializan_todo_catalogo(empresas,monkeypatch):
    a,_,_,_=empresas
    s,p,v=mercaderia(a)
    producto=consulta('SELECT categoria_id FROM producto WHERE id=%s',(p,),True)
    tags=consulta('SELECT talla_id,color_id FROM producto_variante WHERE id=%s',(v,),True)
    nuevos=consulta('''INSERT INTO producto(empresa_id,categoria_id,nombre)
        SELECT %s,%s,'Producto '||n FROM generate_series(1,510) n RETURNING id''',(a['id'],producto['categoria_id']))
    ids=[r['id'] for r in nuevos]
    consulta('''INSERT INTO producto_variante(empresa_id,producto_id,talla_id,color_id,sku)
        SELECT %s,p.id,%s,%s,'SKU-'||p.id FROM producto p WHERE p.id=ANY(%s)''',(a['id'],tags['talla_id'],tags['color_id'],ids))
    consulta('''INSERT INTO precio_producto(empresa_id,producto_variante_id,precio,fecha_inicio)
        SELECT %s,id,50,CURRENT_DATE FROM producto_variante WHERE producto_id=ANY(%s)''',(a['id'],ids))
    consulta('''INSERT INTO inventario_sucursal(empresa_id,sucursal_id,producto_variante_id,stock_disponible)
        SELECT %s,%s,id,4 FROM producto_variante WHERE producto_id=ANY(%s)''',(a['id'],s,ids))
    candidatos=recomendaciones._candidatos_disponibles(s,None,a['id'])
    assert len(candidatos)==511 and ids[-1] in {r['producto_id'] for r in candidatos}
    assert all('variantes' not in r for r in candidatos)
    monkeypatch.setattr(reco_repo,'obtener_embeddings',lambda *args:{p:{'embedding':[1.,0.]},ids[-1]:{'embedding':[1.,0.]}})
    assert recomendaciones.recomendar_desde_producto(p,a['id'],s)[0]['producto_id']==ids[-1]
