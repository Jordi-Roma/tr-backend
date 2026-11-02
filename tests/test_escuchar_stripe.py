from unittest.mock import Mock
from dotenv import dotenv_values
from scripts import escuchar_stripe as listener


def test_no_reutiliza_clave_global_ni_otra_empresa(monkeypatch, tmp_path):
    archivo = tmp_path / 'prueba.env'
    archivo.write_text('STRIPE_SECRET_KEY=sk_test_global\nSTYLEAR_PAGOS_3_STRIPE_SECRET_KEY=sk_test_otra\n')
    monkeypatch.delenv('STYLEAR_PAGOS_2_STRIPE_SECRET_KEY', raising=False)
    monkeypatch.setattr('sys.argv', ['escuchar', '--empresa', '2', '--archivo-env', str(archivo)])
    iniciar = Mock()
    monkeypatch.setattr(listener.subprocess, 'Popen', iniciar)
    assert listener.main() == 2
    iniciar.assert_not_called()


def test_guarda_firma_del_comercio_sin_imprimir_secretos(monkeypatch, tmp_path, capsys):
    archivo = tmp_path / 'prueba.env'
    archivo.write_text('STYLEAR_PAGOS_2_STRIPE_SECRET_KEY=sk_test_actual\nSTYLEAR_PAGOS_3_STRIPE_WEBHOOK_SECRET=whsec_otra\n')
    ejecutable = tmp_path / '.private/stripe-cli/stripe.exe'
    ejecutable.parent.mkdir(parents=True)
    ejecutable.touch()
    monkeypatch.setattr(listener, 'RAIZ', tmp_path)
    monkeypatch.delenv('STYLEAR_PAGOS_2_STRIPE_SECRET_KEY', raising=False)
    monkeypatch.setattr('sys.argv', ['escuchar', '--empresa', '2', '--archivo-env', str(archivo)])
    proceso = Mock()
    proceso.stdout = iter(['Ready! signing secret whsec_privada123\n', 'HTTP [200] POST local\n'])
    proceso.wait.return_value = 0
    proceso.poll.return_value = 0
    iniciar = Mock(return_value=proceso)
    monkeypatch.setattr(listener.subprocess, 'Popen', iniciar)
    assert listener.main() == 0
    config = dotenv_values(archivo)
    assert config['STYLEAR_PAGOS_2_STRIPE_WEBHOOK_SECRET'] == 'whsec_privada123'
    assert config['STYLEAR_PAGOS_3_STRIPE_WEBHOOK_SECRET'] == 'whsec_otra'
    salida = capsys.readouterr().out
    assert 'whsec_privada123' not in salida and 'sk_test_actual' not in salida
    assert 'HTTP 200' in salida
    args, kwargs = iniciar.call_args
    assert 'sk_test_actual' not in str(args)
    assert kwargs['env']['STRIPE_API_KEY'] == 'sk_test_actual'


def test_rechaza_una_clave_live(monkeypatch, tmp_path):
    archivo = tmp_path / 'prueba.env'
    archivo.write_text('STYLEAR_PAGOS_2_STRIPE_SECRET_KEY=sk_live_no_usar\n')
    monkeypatch.delenv('STYLEAR_PAGOS_2_STRIPE_SECRET_KEY', raising=False)
    monkeypatch.setattr('sys.argv', ['escuchar', '--empresa', '2', '--archivo-env', str(archivo)])
    assert listener.main() == 2
