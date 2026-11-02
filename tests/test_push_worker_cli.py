from unittest.mock import Mock

from app.modules.ventas_inventario.services import push_worker as worker


def test_sin_configuracion_no_consulta_bd_ni_repite(monkeypatch):
    monkeypatch.delenv('STYLEAR_FIREBASE_PROJECT_ID', raising=False)
    monkeypatch.delenv('STYLEAR_FIREBASE_CREDENTIALS', raising=False)
    monkeypatch.setattr('sys.argv', ['push_worker', '--continuo'])
    transaccion = Mock(side_effect=AssertionError('No debe abrir la base'))
    monkeypatch.setattr(worker, '_transaccion', transaccion)
    assert worker.main() == 1
    transaccion.assert_not_called()


def test_trabajador_reintenta_fallo_transitorio_sin_exponer_detalles(monkeypatch, capsys):
    monkeypatch.setattr('sys.argv', ['push_worker', '--continuo', '--intervalo', '1'])
    procesar = Mock(side_effect=[RuntimeError('NO_MOSTRAR_DATOS_PRIVADOS'), {'estado': 'PROCESADO', 'enviados': 1}])
    monkeypatch.setattr(worker, 'procesar', procesar)
    monkeypatch.setattr('time.sleep', Mock(side_effect=[None, KeyboardInterrupt()]))
    assert worker.main() == 0
    assert procesar.call_count == 2
    assert 'NO_MOSTRAR_DATOS_PRIVADOS' not in capsys.readouterr().out


def test_modo_anterior_procesa_un_solo_lote(monkeypatch):
    monkeypatch.setattr('sys.argv', ['push_worker'])
    procesar = Mock(return_value={'estado': 'PROCESADO', 'enviados': 0})
    monkeypatch.setattr(worker, 'procesar', procesar)
    assert worker.main() == 0
    procesar.assert_called_once_with()
