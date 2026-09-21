from app.modules.inteligencia.services import recomendacion_service as service


def test_coseno_identifica_similitud_y_descarta_dimensiones_distintas():
    assert service._coseno([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert service._coseno([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert service._coseno([1.0], [1.0, 0.0]) == -1.0


def test_perfil_para_ti_utiliza_compras_y_favoritos_sin_repetirlos(monkeypatch):
    monkeypatch.setattr(service.repo, 'obtener_preferencias', lambda cliente_id: {'categorias': [], 'usar_historial': True})
    monkeypatch.setattr(service.repo, 'obtener_embeddings', lambda modelo: {
        1: {'embedding': [1.0, 0.0]}, 2: {'embedding': [0.8, 0.2]},
        3: {'embedding': [0.0, 1.0]}, 4: {'embedding': [0.7, 0.3]},
    })
    monkeypatch.setattr(service.repo, 'listar_favoritos', lambda cliente_id: [1])
    monkeypatch.setattr(service.repo, 'listar_compras_confirmadas', lambda cliente_id: [
        {'producto_id': 2, 'peso': 2},
    ])
    monkeypatch.setattr(service, '_candidatos_disponibles', lambda sucursal, talla: [
        {'producto_id': id_} for id_ in (1, 2, 3, 4)
    ])
    monkeypatch.setattr(service, '_validar_respuesta', lambda id_, sucursal, talla: {'producto_id': id_})

    assert [item['producto_id'] for item in service.recomendar_para_cliente(7)] == [4, 3]
    assert all('motivo' in item for item in service.recomendar_para_cliente(7))


def test_cliente_puede_dejar_de_usar_historial(monkeypatch):
    monkeypatch.setattr(service.repo, 'obtener_embeddings', lambda modelo: {})
    monkeypatch.setattr(service.repo, 'obtener_preferencias', lambda cliente_id: {'categorias': [], 'usar_historial': False})
    assert service.recomendar_para_cliente(7) == []


def test_recomendacion_contextual_excluye_producto_origen(monkeypatch):
    monkeypatch.setattr(service, 'obtener_prenda_catalogo', lambda id_, sucursal_id=None: {'producto_id': id_})
    monkeypatch.setattr(service.repo, 'obtener_embeddings', lambda modelo: {
        1: {'embedding': [1.0, 0.0]}, 2: {'embedding': [0.9, 0.1]},
    })
    monkeypatch.setattr(service, '_candidatos_disponibles', lambda sucursal, talla: [
        {'producto_id': 1}, {'producto_id': 2},
    ])
    monkeypatch.setattr(service, '_validar_respuesta', lambda id_, sucursal, talla: {'producto_id': id_})

    assert [item['producto_id'] for item in service.recomendar_desde_producto(1)] == [2]
    assert service.recomendar_desde_producto(1)[0]['motivo'] == 'Parecido a la prenda que estás viendo.'


def test_recomendacion_contextual_tiene_fallback_si_no_hay_embedding(monkeypatch):
    monkeypatch.setattr(service, 'obtener_prenda_catalogo', lambda id_, sucursal_id=None: {
        'producto_id': id_, 'categoria_id': 5,
    })
    monkeypatch.setattr(service.repo, 'obtener_embeddings', lambda modelo: {})
    monkeypatch.setattr(service, '_candidatos_disponibles', lambda sucursal, talla: [
        {'producto_id': 1, 'categoria_id': 5, 'stock_total': 3, 'nombre': 'Origen'},
        {'producto_id': 2, 'categoria_id': 5, 'stock_total': 2, 'nombre': 'Similar'},
        {'producto_id': 3, 'categoria_id': 8, 'stock_total': 9, 'nombre': 'Otra'},
    ])
    monkeypatch.setattr(service, '_validar_respuesta', lambda id_, sucursal, talla: {'producto_id': id_})

    resultado = service.recomendar_desde_producto(1)

    assert [item['producto_id'] for item in resultado] == [2, 3]
    assert resultado[0]['motivo'] == 'Sugerencia inicial mientras se actualizan las recomendaciones con IA.'


def test_para_ti_cliente_nuevo_devuelve_sugerencias_iniciales(monkeypatch):
    monkeypatch.setattr(service.repo, 'obtener_embeddings', lambda modelo: {})
    monkeypatch.setattr(service.repo, 'obtener_preferencias', lambda cliente_id: {'categorias': [], 'usar_historial': True})
    monkeypatch.setattr(service.repo, 'listar_favoritos', lambda cliente_id: [])
    monkeypatch.setattr(service.repo, 'listar_compras_confirmadas', lambda cliente_id: [])
    monkeypatch.setattr(service, '_candidatos_disponibles', lambda sucursal, talla: [
        {'producto_id': 10, 'categoria_id': 2, 'stock_total': 5, 'nombre': 'Inicial'},
    ])
    monkeypatch.setattr(service, '_validar_respuesta', lambda id_, sucursal, talla: {'producto_id': id_})

    resultado = service.recomendar_para_cliente(9)

    assert [item['producto_id'] for item in resultado] == [10]
    assert resultado[0]['motivo'] == 'Recomendación inicial con prendas disponibles mientras conocemos tus gustos.'
