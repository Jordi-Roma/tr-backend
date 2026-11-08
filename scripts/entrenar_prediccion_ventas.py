"""Entrenamiento local, por empresa y sin publicación automática en producción."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--empresa", required=True)
    parser.add_argument("--salida", type=Path, required=True)
    parser.add_argument("--semilla", type=int, default=20261108)
    args = parser.parse_args()
    try:
        from app.modules.inteligencia.services.analitica_entrenamiento_service import entrenar_prediccion
    except ModuleNotFoundError as error:
        parser.error(f"Falta una dependencia de entrenamiento ({error.name}). Instala requirements-ml.txt.")
    try:
        reporte = entrenar_prediccion(args.dataset, args.empresa, args.salida, semilla=args.semilla)
    except (ValueError, FileExistsError, FileNotFoundError, KeyError) as error:
        parser.error(str(error))
    print(f"Empresa: {reporte['empresa_id']} · Origen: {reporte['origen']}")
    print(f"MAE modelo: {reporte['prueba']['modelo']['mae']:.3f}")
    print(f"MAE referencia: {reporte['prueba']['referencia_semana_anterior']['mae']:.3f}")
    print(reporte["advertencia"])
    print(f"Artefactos: {args.salida.resolve()}")


if __name__ == "__main__":
    main()
