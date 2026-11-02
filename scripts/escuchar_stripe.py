"""Reenviar eventos Stripe TEST al backend local y guardar su firma sin mostrarla."""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess

from dotenv import dotenv_values, set_key

RAIZ = Path(__file__).resolve().parents[1]
EVENTOS = ','.join((
    'checkout.session.completed', 'checkout.session.async_payment_succeeded',
    'checkout.session.async_payment_failed', 'checkout.session.expired',
    'refund.created', 'refund.updated', 'refund.failed',
))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--empresa', type=int, required=True)
    parser.add_argument('--puerto', type=int, default=8000)
    parser.add_argument('--archivo-env', type=Path, default=RAIZ / '.env')
    args = parser.parse_args()
    if args.empresa <= 0 or not 1 <= args.puerto <= 65535:
        parser.error('Empresa o puerto no válido.')
    archivo = args.archivo_env.resolve()
    if not archivo.is_file():
        parser.error('El archivo de configuración no existe.')
    nombre = f'STYLEAR_PAGOS_{args.empresa}_STRIPE_SECRET_KEY'
    clave = os.getenv(nombre) or dotenv_values(archivo).get(nombre) or ''
    if not clave.startswith('sk_test_'):
        print('Configura una clave TEST para esta empresa. No se usan claves globales ni LIVE.', flush=True)
        return 2
    local = RAIZ / '.private' / 'stripe-cli' / 'stripe.exe'
    ejecutable = str(local) if local.is_file() else shutil.which('stripe')
    if not ejecutable:
        print('Falta instalar Stripe CLI desde su distribución oficial.', flush=True)
        return 2
    entorno = {**os.environ, 'STRIPE_API_KEY': clave}
    comando = [ejecutable, 'listen', '--events', EVENTOS, '--forward-to',
               f'http://127.0.0.1:{args.puerto}/api/v1/pagos-empresa/stripe/webhook/{args.empresa}']
    proceso = None
    try:
        proceso = subprocess.Popen(comando, env=entorno, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
        for linea in proceso.stdout:
            # El CLI anuncia el secreto en su salida: se guarda sin imprimir esa línea.
            firma = re.search(r'\bwhsec_[A-Za-z0-9]+', linea)
            if firma:
                set_key(str(archivo), f'STYLEAR_PAGOS_{args.empresa}_STRIPE_WEBHOOK_SECRET', firma.group())
                print('Receptor Stripe TEST listo; firma guardada en el archivo privado. Inicia o reinicia la API.', flush=True)
            elif re.search(r'\[\d{3}\]', linea):
                codigo = re.search(r'\[(\d{3})\]', linea).group(1)
                print(f'Evento reenviado al backend local: HTTP {codigo}.', flush=True)
            elif re.search(r'error|failed|unauthorized', linea, re.IGNORECASE):
                print('Stripe CLI informó una incidencia. Verifica conexión y credenciales de pruebas.', flush=True)
        return proceso.wait()
    except KeyboardInterrupt:
        return 0
    except OSError:
        print('No se pudo iniciar el receptor Stripe CLI.', flush=True)
        return 2
    finally:
        if proceso is not None and proceso.poll() is None:
            proceso.terminate()
            try:
                proceso.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proceso.kill()
                proceso.wait()


if __name__ == '__main__':
    raise SystemExit(main())
