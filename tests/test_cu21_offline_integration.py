from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from test_cuenta_integration import login
from test_cu11_cu15_integration import api, carrito, personal
from test_multitenant_integration import actor, cliente, consulta, empresas, mercaderia


def test_cu21_reserva_reintenta_sin_depender_del_carrito(api, empresas):
    empresa, otra, _, _ = empresas
    sucursal, _, variante = mercaderia(empresa)
    ajena, _, _ = mercaderia(otra)
    _, _, nombre = cliente(empresa)
    headers = login(api, empresa, nombre)
    carrito(api, headers, sucursal, variante)
    hoy = datetime.now(ZoneInfo('America/La_Paz')).date()
    datos = {
        'sucursal_id': sucursal,
        'fecha_cita': str(hoy + timedelta(days=1)),
        'clave_operacion': str(uuid4()),
        'items': [{'producto_variante_id': variante, 'cantidad': 2}],
    }
    assert api.get(f'/api/v1/operacion-movil/catalogo?sucursal_id={ajena}', headers=headers).status_code == 403
    catalogo = api.get(f'/api/v1/operacion-movil/catalogo?sucursal_id={sucursal}', headers=headers)
    assert catalogo.status_code == 200, catalogo.text
    assert catalogo.json()['items'][0]['precio_centavos'] == 5000
    with ThreadPoolExecutor(2) as pool:
        envios = list(pool.map(lambda _: api.post('/api/v1/reservas/offline', headers=headers, json=datos), range(2)))
    assert all(r.status_code == 200 for r in envios), [r.text for r in envios]
    assert envios[0].json()['id'] == envios[1].json()['id']
    assert envios[0].json()['detalles'][0]['cantidad'] == 2
    assert api.get('/api/v1/carrito', headers=headers).json()['items'][0]['cantidad'] == 1


def test_cu21_contado_no_duplica_ni_confirma_un_conflicto_reenviado(api, empresas):
    empresa, _, _, _ = empresas
    sucursal, _, variante = mercaderia(empresa, stock=1)
    _, nombre = personal(empresa, sucursal, 'CAJERO')
    headers = login(api, empresa, nombre)
    ruta = '/api/v1/ventas-presenciales/offline'
    datos = {
        'sucursal_id': sucursal,
        'clave_operacion': str(uuid4()),
        'metodo_pago': 'EFECTIVO',
        'efectivo_centavos': 5000,
        'items': [{'producto_variante_id': variante, 'cantidad': 1, 'precio_centavos': 5000}],
    }
    with ThreadPoolExecutor(2) as pool:
        envios = list(pool.map(lambda _: api.post(ruta, headers=headers, json=datos), range(2)))
    assert all(r.status_code == 200 for r in envios), [r.text for r in envios]
    venta = envios[0].json()['id']
    assert envios[1].json()['id'] == venta
    assert consulta("SELECT count(*) AS n FROM movimiento_inventario WHERE empresa_id=%s AND referencia_id=%s AND tipo='VENTA_PRESENCIAL'",
                    (empresa['id'], venta), True)['n'] == 1

    otra_venta = {**datos, 'clave_operacion': str(uuid4())}
    sin_stock = api.post(ruta, headers=headers, json=otra_venta)
    assert sin_stock.status_code == 400, sin_stock.text
    consulta('UPDATE inventario_sucursal SET stock_disponible=1 WHERE sucursal_id=%s AND producto_variante_id=%s',
             (sucursal, variante))
    repetida = api.post(ruta, headers=headers, json=otra_venta)
    assert repetida.status_code == 400
    assert repetida.json() == sin_stock.json()

    precio_anterior = {
        **datos, 'clave_operacion': str(uuid4()), 'efectivo_centavos': 4800,
        'items': [{**datos['items'][0], 'precio_centavos': 4800}],
    }
    conflicto = api.post(ruta, headers=headers, json=precio_anterior)
    assert conflicto.status_code == 400 and 'precio' in conflicto.text
    assert consulta('SELECT stock_disponible FROM inventario_sucursal WHERE sucursal_id=%s AND producto_variante_id=%s',
                    (sucursal, variante), True)['stock_disponible'] == 1
