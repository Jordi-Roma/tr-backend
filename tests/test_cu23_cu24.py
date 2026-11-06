from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.modules.inteligencia.services import asistente_service as chat, recomendacion_service as reco
from app.modules.inteligencia.schemas.asistente.asistente_schemas import AsistenteContexto, AsistenteChatRequest


@pytest.mark.parametrize('contexto',[
    {'recurso_id':1}, {'recurso_tipo':'VENTA'}, {'recurso_tipo':'USUARIO','recurso_id':1},
    {'producto_id':2**64}, {'terminos':['x'*61]}, {'usuario_id':15}, {'precio_max':-1},
])
def test_contexto_rechaza_campos_o_valores_no_autorizados(contexto):
    with pytest.raises(ValidationError):
        AsistenteContexto(**contexto)


def test_rules_no_usa_clave_openai_ni_vertex(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','no-utilizar')
    monkeypatch.setattr(chat,'AI_ASSISTANT_PROVIDER','RULES')
    def bloquear(*args,**kwargs):
        raise AssertionError('No se permite una llamada externa en RULES.')
    monkeypatch.setattr(chat,'interpretar_asistente_con_vertex',bloquear)
    assert chat._interpretar_consulta_asistente('Quiero una camisa azul','quiero una camisa azul',None,None,1)[0]=='catalogo'
    assert chat._redactar_con_ia('Stock',[],'Hechos verificados','catalogo')=='Hechos verificados'


def test_error_de_ia_y_filtros_administrativos_no_conceden_permisos(monkeypatch):
    monkeypatch.setattr(chat,'AI_ASSISTANT_PROVIDER','VERTEX')
    monkeypatch.setattr(chat,'listar_sucursales_para_asistente',lambda e:[])
    def fallo(*args,**kwargs):
        raise TimeoutError('No mostrar información sensible')
    monkeypatch.setattr(chat,'interpretar_asistente_con_vertex',fallo)
    tipo,filtros,_=chat._interpretar_consulta_asistente('camisa azul','camisa azul',None,None,1)
    assert tipo=='catalogo' and filtros['color_patrones']==['azul']
    monkeypatch.setattr(chat,'interpretar_asistente_con_vertex',lambda *a,**k:{
        'tipo':'USUARIOS','terminos':[],'color_patrones':[],'talla_patrones':[],'sucursal_patrones':[],'precio_max':None})
    assert chat._interpretar_consulta_asistente('camisa','camisa',None,None,1)[0]=='catalogo'


def test_sensible_no_se_envia_al_interprete(monkeypatch):
    monkeypatch.setattr(chat,'AI_ASSISTANT_PROVIDER','VERTEX')
    monkeypatch.setattr(chat,'interpretar_asistente_con_vertex',lambda *a,**k:pytest.fail('No enviar credenciales al proveedor'))
    chat._interpretar_consulta_asistente('camisa token=confidencial','camisa token=confidencial',None,None,1)


def test_vectores_incompatibles_y_no_finitos_no_se_usan(monkeypatch):
    monkeypatch.setattr(reco,'obtener_prenda_catalogo',lambda *a:{'categoria_id':1})
    monkeypatch.setattr(reco.repo,'obtener_embeddings',lambda *a:{
        1:{'embedding':[1.,0.]},2:{'embedding':[1.,0.,0.]},3:{'embedding':[float('nan'),0.]},4:{'embedding':[1.,0.]}})
    monkeypatch.setattr(reco,'_candidatos_disponibles',lambda *a:[{'producto_id':p} for p in (2,3,4)])
    monkeypatch.setattr(reco,'_validar_respuesta',lambda p,*a:{'producto_id':p})
    assert [r['producto_id'] for r in reco.recomendar_desde_producto(1,1)]==[4]


def test_indices_separan_proveedor_y_modelo(monkeypatch):
    claves=[]
    monkeypatch.setattr(reco,'AI_RECOMMENDATIONS_PROVIDER','GEMINI')
    monkeypatch.setattr(reco,'obtener_prenda_catalogo',lambda *a:{'categoria_id':1})
    monkeypatch.setattr(reco.repo,'obtener_embeddings',lambda modelo,*a:claves.append(modelo) or {})
    monkeypatch.setattr(reco,'_candidatos_disponibles',lambda *a:[])
    assert reco.recomendar_desde_producto(1,1)==[]
    assert claves==['GEMINI:'+reco.MODELO]


def test_personalizacion_desactivada_no_lee_vectores_ni_historial(monkeypatch):
    monkeypatch.setattr(reco.repo,'obtener_preferencias',lambda *a:{'usar_historial':False})
    monkeypatch.setattr(reco.repo,'obtener_embeddings',lambda *a:pytest.fail('No leer vectores'))
    monkeypatch.setattr(reco.repo,'listar_compras_confirmadas',lambda *a:pytest.fail('No leer compras'))
    assert reco.recomendar_para_cliente(1,1)==[]


def test_limite_tecnico_se_recupera_y_no_depende_del_plan(monkeypatch):
    from collections import OrderedDict
    from app.modules.inteligencia.router import asistente_router as router
    monkeypatch.setattr(router,'_solicitudes',OrderedDict())
    for _ in range(60):
        router.limitar_solicitudes('prueba',100)
    with pytest.raises(HTTPException) as error:
        router.limitar_solicitudes('prueba',101)
    assert error.value.status_code==429
    router.limitar_solicitudes('otro',101)
    router.limitar_solicitudes('prueba',161)


def test_no_se_acepta_usuario_desde_cuerpo():
    with pytest.raises(ValidationError):
        AsistenteChatRequest(mensaje='Mis compras',usuario_id=1)


def test_preguntas_normalizan_puntuacion_y_plural_de_pantalon():
    assert chat._normalizar('¿Y en azul?')=='y en azul'
    assert 'pantalon' in chat._extraer_terminos('pantalones')
