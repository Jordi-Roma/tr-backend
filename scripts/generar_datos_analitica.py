"""Uso desde tr-backend: python scripts/generar_datos_analitica.py --help."""
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.modules.inteligencia.services.analitica_datos_service import (  # noqa: E402
    ConfiguracionDatos, generar_dataset,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generar datos académicos de analítica sin usar PostgreSQL.")
    parser.add_argument("--salida", type=Path, default=Path(".private/analitica/dataset_v1"))
    parser.add_argument("--semilla", type=int, default=20261108)
    parser.add_argument("--dias", type=int, default=420)
    parser.add_argument("--fecha-inicio", type=date.fromisoformat, default=date(2025, 1, 1))
    args = parser.parse_args()
    try:
        m = generar_dataset(args.salida, ConfiguracionDatos(
            semilla=args.semilla, dias=args.dias, fecha_inicio=args.fecha_inicio))
    except (ValueError, FileExistsError) as error:
        parser.error(str(error))
    print(f"Dataset {m['dataset_id']} generado en {args.salida.resolve()}")
    for nombre, info in m["archivos"].items():
        print(f"  {nombre}: {info['filas']} filas")
    print(m["advertencia"])


if __name__ == "__main__":
    main()
