import csv
import hashlib
from collections import defaultdict
from datetime import date, timedelta

import pytest

from app.modules.inteligencia.services.analitica_datos_service import (
    ConfiguracionDatos, generar_dataset,
)


def leer(carpeta, nombre):
    with (carpeta / nombre).open(encoding="utf-8", newline="") as archivo:
        return list(csv.DictReader(archivo))


@pytest.fixture
def dataset(tmp_path):
    carpeta = tmp_path / "datos"
    config = ConfiguracionDatos(dias=140, empresas=2, sucursales=1, productos=2, clientes=20)
    return carpeta, generar_dataset(carpeta, config), config


def test_reproducible_y_manifiesto_verificable(dataset, tmp_path):
    carpeta, manifiesto, config = dataset
    otra = tmp_path / "repeticion"
    assert generar_dataset(otra, config) == manifiesto
    for nombre, info in manifiesto["archivos"].items():
        assert (carpeta / nombre).read_bytes() == (otra / nombre).read_bytes()
        assert hashlib.sha256((carpeta / nombre).read_bytes()).hexdigest() == info["sha256"]
        assert len(leer(carpeta, nombre)) == info["filas"]
    assert manifiesto["origen"] == "SINTETICO"


def test_variables_solo_pasado_objetivo_solo_futuro_y_particiones_disjuntas(dataset):
    carpeta, manifiesto, _ = dataset
    diarios = defaultdict(dict)
    for fila in leer(carpeta, "ventas_diarias.csv"):
        clave = tuple(fila[k] for k in ("empresa_id", "sucursal_id", "producto_id"))
        diarios[clave][date.fromisoformat(fila["fecha"])] = int(fila["unidades"])
    periodos = defaultdict(set)
    for fila in leer(carpeta, "prediccion_semanal.csv"):
        serie = diarios[tuple(fila[k] for k in ("empresa_id", "sucursal_id", "producto_id"))]
        corte = date.fromisoformat(fila["fecha_corte"])
        assert int(fila["unidades_7d"]) == sum(serie[corte - timedelta(days=i)] for i in range(7))
        assert int(fila["unidades_28d"]) == sum(serie[corte - timedelta(days=i)] for i in range(28))
        assert int(fila["objetivo_unidades_7d"]) == sum(serie[corte + timedelta(days=i)] for i in range(1, 8))
        assert fila["objetivo_desde"] > fila["fecha_corte"]
        periodos[fila["particion"]].update(corte + timedelta(days=i) for i in range(1, 8))
    nombres = ["ENTRENAMIENTO", "VALIDACION", "PRUEBA"]
    for previo, siguiente in zip(nombres, nombres[1:]):
        assert max(periodos[previo]) < min(periodos[siguiente])
        assert manifiesto["particiones"][previo]["objetivo_hasta"] <= manifiesto["particiones"][siguiente]["corte_desde"]


def test_ventas_referencias_stock_y_rfm_coherentes_por_empresa(dataset):
    carpeta, _, config = dataset
    productos = {(r["empresa_id"], r["producto_id"]) for r in leer(carpeta, "productos.csv")}
    clientes = {(r["empresa_id"], r["cliente_id"]) for r in leer(carpeta, "clientes.csv")}
    agregado = defaultdict(lambda: [0, 0])
    compras = defaultdict(list)
    for v in leer(carpeta, "ventas.csv"):
        assert v["origen"] == "SINTETICO"
        assert (v["empresa_id"], v["producto_id"]) in productos
        assert (v["empresa_id"], v["cliente_id"]) in clientes
        clave = tuple(v[k] for k in ("empresa_id", "sucursal_id", "producto_id", "fecha"))
        agregado[clave][0] += int(v["cantidad"])
        agregado[clave][1] += int(v["importe_centavos"])
        compras[(v["empresa_id"], v["cliente_id"])].append(v)
    for fila in leer(carpeta, "ventas_diarias.csv"):
        clave = tuple(fila[k] for k in ("empresa_id", "sucursal_id", "producto_id", "fecha"))
        assert agregado[clave] == [int(fila["unidades"]), int(fila["importe_centavos"])]
        assert 0 <= int(fila["unidades"]) <= int(fila["stock_inicio"])
    fin = config.fecha_inicio + timedelta(days=config.dias - 1)
    for fila in leer(carpeta, "clientes_rfm.csv"):
        desde = fin - timedelta(days=179)
        vs = [v for v in compras[(fila["empresa_id"], fila["cliente_id"])] if v["fecha"] >= desde.isoformat()]
        assert int(fila["frecuencia_compras"]) == len(vs)
        assert int(fila["gasto_centavos"]) == sum(int(v["importe_centavos"]) for v in vs)
        assert int(fila["recencia_dias"]) == (fin - date.fromisoformat(max(v["fecha"] for v in vs))).days
        assert "segmento" not in fila  # El modelo deberá descubrir los grupos.


def test_no_sobrescribe_datos_ni_crea_salida_con_configuracion_invalida(dataset, tmp_path):
    carpeta, _, config = dataset
    original = (carpeta / "manifiesto.json").read_bytes()
    with pytest.raises(FileExistsError):
        generar_dataset(carpeta, config)
    assert (carpeta / "manifiesto.json").read_bytes() == original
    salida = tmp_path / "invalida"
    with pytest.raises(ValueError):
        generar_dataset(salida, ConfiguracionDatos(dias=30))
    assert not salida.exists()
