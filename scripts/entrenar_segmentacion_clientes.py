"""Segmentación RFM local por empresa, sin publicación automática."""
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
        from app.modules.inteligencia.services.analitica_segmentacion_service import entrenar_segmentacion
    except ModuleNotFoundError as error:
        parser.error(f"Falta la dependencia {error.name}. Instala requirements-ml.txt.")
    try:
        r = entrenar_segmentacion(args.dataset, args.empresa, args.salida, semilla=args.semilla)
    except (ValueError, FileExistsError, FileNotFoundError, KeyError) as error:
        parser.error(str(error))
    print(f"Empresa: {r['empresa_id']} · Origen: {r['origen']}")
    print(f"Clientes analizados: {r['clientes_analizados']} · Grupos: {r['k_elegido']}")
    print(f"Silhouette: {r['silhouette']:.3f} · ARI medio entre semillas: {r['ari_medio']:.3f}")
    print(r["advertencia"])
    print(f"Artefactos: {args.salida.resolve()}")


if __name__ == "__main__":
    main()
