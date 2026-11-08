"""Asocia artefactos sintéticos a una empresa autorizada del servidor local."""
import argparse
import hashlib
import json
from pathlib import Path
from tempfile import NamedTemporaryFile


def registrar(registro, empresa_codigo, empresa_id, empresa_dataset, sucursales,
              prediccion, segmentacion, estado_oficial=None, actualizar=False):
    registro = Path(registro).resolve()
    raiz = registro.parent
    if empresa_id <= 0 or not empresa_codigo or not sucursales or any(int(k) <= 0 for k in sucursales):
        raise ValueError("Se requieren empresa y sucursales válidas.")
    if len(set(sucursales.values())) != len(sucursales):
        raise ValueError("Cada sucursal debe asociarse a una sucursal sintética diferente.")

    def referencia(ruta):
        ruta = Path(ruta).resolve()
        if not ruta.is_relative_to(raiz):
            raise ValueError("Los artefactos deben estar dentro de la carpeta del registro.")
        return {"ruta": ruta.relative_to(raiz).as_posix(), "sha256": hashlib.sha256(ruta.read_bytes()).hexdigest()}

    artefactos = {}
    for tipo, carpeta, nombre_csv in (("predicciones", prediccion, "predicciones_prueba.csv"),
                                      ("segmentos", segmentacion, "asignaciones.csv")):
        carpeta = Path(carpeta)
        evaluacion = json.loads((carpeta / "evaluacion.json").read_text(encoding="utf-8"))
        if evaluacion["origen"] != "SINTETICO" or evaluacion["empresa_id"] != empresa_dataset:
            raise ValueError("Los artefactos no corresponden a la empresa sintética seleccionada.")
        artefactos[tipo] = {"evaluacion": referencia(carpeta / "evaluacion.json"),
                           "filas": referencia(carpeta / nombre_csv)}
    entrada = {"empresa_id": empresa_id, "demostracion": {
        "estado": "DISPONIBLE", "fuente_datos": "SINTETICO", "empresa_dataset": empresa_dataset,
        "sucursales": sucursales, **artefactos}, "oficial": {"estado": "NO_CONFIGURADO"}}
    if estado_oficial:
        e = json.loads(Path(estado_oficial).read_text(encoding="utf-8"))
        if e["empresa_codigo"] != empresa_codigo or e["empresa_id"] != empresa_id:
            raise ValueError("La auditoría oficial no corresponde a la empresa seleccionada.")
        if e["prediccion_oficial"] != "HISTORIAL_INSUFICIENTE":
            raise ValueError("Este registro solo admite la auditoría de historial insuficiente; no publica modelos oficiales.")
        entrada["oficial"] = {"estado": "HISTORIAL_INSUFICIENTE", "evaluado_en": e["verificado_en"],
                               "fuente_datos": "AUDITORIA_RAILWAY", "resumen_historial": {
            "ventas_completadas": e["ventas_completadas"],
            "dias_con_ventas": e["candidatas_sin_prueba_identificable"]["dias_con_ventas"],
            "clientes_compradores": e["candidatas_sin_prueba_identificable"]["clientes"],
            "ventas_con_senal_prueba": e["ventas_con_pago_prueba_identificable"],
            "ventas_sin_detalle": e["ventas_completadas_sin_detalle"]}}
    contenido = json.loads(registro.read_text(encoding="utf-8")) if registro.exists() else {"version": 1, "empresas": {}}
    if empresa_codigo in contenido["empresas"] and not actualizar:
        raise FileExistsError("La empresa ya tiene registro; usa --actualizar para sustituir su configuración.")
    contenido["empresas"][empresa_codigo] = entrada
    raiz.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=raiz, suffix=".json", delete=False) as archivo:
        json.dump(contenido, archivo, indent=2, ensure_ascii=False)
        temporal = Path(archivo.name)
    try:
        temporal.replace(registro)
    finally:
        temporal.unlink(missing_ok=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--registro", type=Path, default=Path(".private/analitica/registro_api.json"))
    p.add_argument("--empresa-codigo", required=True)
    p.add_argument("--empresa-id", type=int, required=True)
    p.add_argument("--empresa-dataset", default="SYN-E01")
    p.add_argument("--sucursal", action="append", required=True, help="ID_REAL=ID_SINTETICO; se puede repetir")
    p.add_argument("--prediccion", type=Path, required=True)
    p.add_argument("--segmentacion", type=Path, required=True)
    p.add_argument("--estado-oficial", type=Path)
    p.add_argument("--actualizar", action="store_true")
    a = p.parse_args()
    try:
        pares = [r.split("=", 1) for r in a.sucursal]
        mapa = dict(pares)
        if len(mapa) != len(pares):
            raise ValueError("Hay sucursales duplicadas.")
        registrar(a.registro, a.empresa_codigo, a.empresa_id, a.empresa_dataset, mapa,
                  a.prediccion, a.segmentacion, a.estado_oficial, a.actualizar)
    except (ValueError, FileExistsError, FileNotFoundError, KeyError) as error:
        p.error(str(error))
    print("Registro local de analítica guardado. No se publicaron datos en Railway.")


if __name__ == "__main__":
    main()
