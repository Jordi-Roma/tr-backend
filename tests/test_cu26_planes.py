from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.core.plan_empresa import normalizar_politica, validar_politica, seleccionar_pausas_reportes
from app.modules.administracion.repositories.empresa_saas_repository import _configurar_plan, _token_impacto
from app.modules.administracion.services.respaldo_service import respaldo_vencido
from app.modules.inteligencia.services.programacion_reporte import proxima_ejecucion, periodo_reporte
from app.modules.inteligencia.schemas.reportes.reporte_request import CrearReporteProgramadoRequest


def test_renombrar_plan_no_cambia_condiciones_y_edicion_parcial_conserva_valores():
    actual={'codigo':'PREMIUM','nombre':'Premium','funciones':{'reportes_pdf':False},'limites':{'usuarios':15}}
    nuevo=_configurar_plan(actual,{'nombre':'Profesional','precio':Decimal('15.50')})
    assert nuevo['limites']['usuarios']==15
    assert nuevo['funciones']['reportes_pdf'] is False
    assert nuevo['precio']==Decimal('15.50')


@pytest.mark.parametrize('cambio',[
    {'limites':{'usuarios':0}}, {'limites':{'sucursales':0}}, {'limites':{'empleados':-1}},
    {'limites':{'modulo_inventado':5}}, {'funciones':{'reportes_pdf':1}},
    {'funciones':{'vestidor':False}}, {'funciones':{'reportes_interpretacion':False,'reportes_voz':True}},
    {'funciones':{'reportes_pdf':False,'reportes_excel':False,'reportes_programacion':True}},
    {'precio':'NaN'}, {'moneda':'BOBS'}, {'publico':None}, {'limites':None},
    {'limites':{'retencion_respaldos_dias':3651}},
])
def test_rechaza_configuraciones_incoherentes(cambio):
    with pytest.raises(ValueError):
        _configurar_plan({'codigo':'PRUEBA','nombre':'Prueba'},cambio)


def test_cuando_baja_cupo_o_formato_pausa_deterministicamente_sin_reactivar():
    politica=normalizar_politica({'limites':{'reportes_programados':1},'funciones':{'reportes_excel':False}})
    filas=[{'id':4,'formato':'PDF','activo':True},{'id':1,'formato':'EXCEL','activo':True},
           {'id':3,'formato':'PDF','activo':True},{'id':2,'formato':'PDF','activo':False}]
    assert seleccionar_pausas_reportes(filas,politica)==[1,4]


def test_token_cambia_si_uso_o_condiciones_cambian():
    token=_token_impacto({'revision':1},{'nombre':'Plan'},{'uso':2})
    assert token!=_token_impacto({'revision':1},{'nombre':'Plan'},{'uso':3})
    assert token!=_token_impacto({'revision':2},{'nombre':'Plan'},{'uso':2})


def test_calendario_mensual_dia31_y_periodo_del_mes_anterior():
    item={'frecuencia':'MENSUAL','dia':'31','hora':'08:00','zona_horaria':'America/La_Paz'}
    proxima=proxima_ejecucion(item,datetime(2026,2,1,tzinfo=timezone.utc))
    assert proxima==datetime(2026,2,28,12,tzinfo=timezone.utc)
    desde,hasta=periodo_reporte(item,datetime(2026,3,31,12,tzinfo=timezone.utc))
    assert str(desde)=='2026-02-01' and str(hasta)=='2026-02-28'


def test_periodo_semanal_no_es_ultimos30dias():
    item={'frecuencia':'SEMANAL','dia':'LUNES','hora':'08:00'}
    desde,hasta=periodo_reporte(item,datetime(2026,11,9,12,tzinfo=timezone.utc))
    assert str(desde)=='2026-11-02' and str(hasta)=='2026-11-08'


@pytest.mark.parametrize('cambio',[{'hora':'25:00'},{'dia':None},{'zona_horaria':'No/Existe'},
    {'destinatario_email':'a@example.com\r\nBcc: otro@example.com'}, {'filtros':{'empresa_id':99}}])
def test_validacion_programaciones(cambio):
    with pytest.raises(ValidationError):
        CrearReporteProgramadoRequest(**{'titulo':'Ventas','tipo':'VENTAS','frecuencia':'SEMANAL',
            'dia':'LUNES','destinatario_email':'gerencia@example.invalid',**cambio})


def test_reduccion_de_plan_ignora_horario_premium_guardado():
    politica={'frecuencia_dias':1,'horario_editable':False}
    programacion={'activa':True,'hora_local':'01:00','zona_horaria':'Pacific/Auckland'}
    assert respaldo_vencido(programacion,politica,datetime(2026,11,5,5,30,tzinfo=timezone.utc)) is False
    assert respaldo_vencido(programacion,politica,datetime(2026,11,5,6,0,tzinfo=timezone.utc)) is True
