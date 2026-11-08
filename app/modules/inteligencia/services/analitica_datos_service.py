"""Datos académicos reproducibles. No importa conexión, modelos ni servicios externos."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

VERSION_DATOS = "1"
ORIGEN = "SINTETICO"


@dataclass(frozen=True)
class ConfiguracionDatos:
    semilla: int = 20261108
    fecha_inicio: date = date(2025, 1, 1)
    dias: int = 420
    empresas: int = 2
    sucursales: int = 3  # Por empresa.
    productos: int = 12  # Por empresa.
    clientes: int = 150  # Por empresa.

    def validar(self) -> None:
        limites = {"dias": (140, 1095), "empresas": (1, 5), "sucursales": (1, 5),
                   "productos": (2, 50), "clientes": (10, 1000)}
        for nombre, (minimo, maximo) in limites.items():
            valor = getattr(self, nombre)
            if type(valor) is not int or not minimo <= valor <= maximo:
                raise ValueError(f"{nombre} debe estar entre {minimo} y {maximo}.")
        if type(self.semilla) is not int or type(self.fecha_inicio) is not date:
            raise ValueError("Semilla o fecha de inicio no válidas.")
        if self.empresas * self.sucursales * self.productos * self.dias > 500_000:
            raise ValueError("El conjunto supera el límite de 500000 registros diarios.")


def _guardar_csv(directorio: Path, nombre: str, campos: list[str], filas: list[dict]) -> dict:
    archivo = directorio / nombre
    with archivo.open("w", encoding="utf-8", newline="") as salida:
        escritor = csv.DictWriter(salida, fieldnames=campos, lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(filas)
    return {"filas": len(filas), "sha256": hashlib.sha256(archivo.read_bytes()).hexdigest(),
            "columnas": campos}


def generar_dataset(destino: Path, config: ConfiguracionDatos = ConfiguracionDatos()) -> dict:
    """Crea CSV + manifiesto nuevos; nunca escribe en PostgreSQL ni reemplaza una salida."""
    config.validar()
    destino = Path(destino).resolve()
    if destino.exists():
        raise FileExistsError(f"La salida ya existe: {destino}. Usa otra carpeta.")
    rng = random.Random(config.semilla)
    diarios, ventas, catalogo, clientes = [], [], [], []
    series = {}
    por_cliente = defaultdict(list)
    for empresa in range(1, config.empresas + 1):
        eid = f"SYN-E{empresa:02d}"
        ids_clientes = [f"{eid}-C{n:04d}" for n in range(1, config.clientes + 1)]
        # Pesos continuos, sin clases ni segmentos predeterminados exportados.
        pesos = [rng.lognormvariate(0, 1.1) for _ in ids_clientes]
        clientes.extend({"origen": ORIGEN, "empresa_id": eid, "cliente_id": cid}
                        for cid in ids_clientes)
        for producto in range(1, config.productos + 1):
            pid = f"{eid}-P{producto:03d}"
            categoria = ("ABRIGO", "CAMISETA", "PANTALON", "VESTIDO")[(producto - 1) % 4]
            base_centavos = rng.randrange(6000, 40001, 100)
            popularidad = rng.uniform(0.6, 2.5)
            catalogo.append({"origen": ORIGEN, "empresa_id": eid, "producto_id": pid,
                             "categoria": categoria, "precio_base_centavos": base_centavos})
            for sucursal in range(1, config.sucursales + 1):
                sid = f"{eid}-S{sucursal:02d}"
                serie = []
                stock = rng.randint(20, 65)
                for dia in range(config.dias):
                    fecha = config.fecha_inicio + timedelta(days=dia)
                    if dia % 7 == 0:
                        stock += rng.randint(12, 38)
                    stock_inicial = stock
                    descuento = rng.choice((0, 0, 0, 0, 10, 15, 20))
                    precio = base_centavos * (100 - descuento) // 100
                    invierno = math.cos(2 * math.pi * (fecha.timetuple().tm_yday - 180) / 365)
                    temporada = 1 + (0.30 if categoria == "ABRIGO" else -0.15) * invierno
                    media = popularidad * (1 + sucursal * 0.15) * temporada
                    media *= (1.35 if fecha.weekday() >= 5 else 1) * (1 + descuento / 50)
                    # Ruido y ceros: el objetivo no es una fórmula exacta sin variación.
                    demanda = max(0, round(rng.gauss(media, max(1, media * 0.65))))
                    unidades = min(stock, demanda)
                    stock -= unidades
                    registro = {"origen": ORIGEN, "empresa_id": eid, "sucursal_id": sid,
                                "producto_id": pid, "fecha": fecha.isoformat(),
                                "precio_centavos": precio, "descuento_pct": descuento,
                                "stock_inicio": stock_inicial, "unidades": unidades,
                                "importe_centavos": unidades * precio}
                    diarios.append(registro)
                    serie.append(registro)
                    pendientes = unidades
                    while pendientes:
                        cantidad = min(pendientes, rng.randint(1, 3))
                        cid = rng.choices(ids_clientes, weights=pesos, k=1)[0]
                        venta = {"origen": ORIGEN, "empresa_id": eid,
                                 "venta_id": f"SYN-V{len(ventas) + 1:09d}",
                                 "cliente_id": cid, "sucursal_id": sid, "producto_id": pid,
                                 "fecha": fecha.isoformat(), "cantidad": cantidad,
                                 "importe_centavos": cantidad * precio}
                        ventas.append(venta)
                        por_cliente[(eid, cid)].append(venta)
                        pendientes -= cantidad
                series[(eid, sid, pid)] = (categoria, serie)

    # Semanas objetivo disjuntas. Cada fila conoce únicamente hasta su fecha de corte.
    cortes = list(range(27, config.dias - 7, 7))
    limite_train, limite_val = int(len(cortes) * 0.70), int(len(cortes) * 0.85)
    particiones = {corte: "ENTRENAMIENTO" if i < limite_train else
                   "VALIDACION" if i < limite_val else "PRUEBA"
                   for i, corte in enumerate(cortes)}
    muestras = []
    for (eid, sid, pid), (categoria, serie) in series.items():
        for corte in cortes:
            anteriores = serie[corte - 27:corte + 1]
            semana = anteriores[-7:]
            objetivo = serie[corte + 1:corte + 8]
            fecha = date.fromisoformat(serie[corte]["fecha"])
            muestras.append({"origen": ORIGEN, "empresa_id": eid, "sucursal_id": sid,
                             "producto_id": pid, "categoria": categoria,
                             "fecha_corte": fecha.isoformat(),
                             "objetivo_desde": objetivo[0]["fecha"],
                             "objetivo_hasta": objetivo[-1]["fecha"],
                             "particion": particiones[corte], "mes": fecha.month,
                             "precio_corte_centavos": serie[corte]["precio_centavos"],
                             "descuento_corte_pct": serie[corte]["descuento_pct"],
                             "stock_corte": serie[corte]["stock_inicio"] - serie[corte]["unidades"],
                             "unidades_7d": sum(r["unidades"] for r in semana),
                             "unidades_28d": sum(r["unidades"] for r in anteriores),
                             "dias_sin_stock_28d": sum(r["stock_inicio"] == 0 for r in anteriores),
                             "objetivo_unidades_7d": sum(r["unidades"] for r in objetivo)})

    rfm = []
    fin = config.fecha_inicio + timedelta(days=config.dias - 1)
    desde = fin - timedelta(days=179)
    for cliente in clientes:
        compras = [v for v in por_cliente[(cliente["empresa_id"], cliente["cliente_id"])]
                   if desde.isoformat() <= v["fecha"] <= fin.isoformat()]
        # Un cliente sin compras no se fuerza dentro de un cluster comercial.
        if not compras:
            continue
        rfm.append({**cliente, "fecha_corte": fin.isoformat(), "ventana_dias": 180,
                    "recencia_dias": (fin - date.fromisoformat(max(v["fecha"] for v in compras))).days,
                    "frecuencia_compras": len({v["venta_id"] for v in compras}),
                    "gasto_centavos": sum(v["importe_centavos"] for v in compras)})

    archivos = {
        "productos.csv": (list(catalogo[0]), catalogo),
        "clientes.csv": (list(clientes[0]), clientes),
        "ventas.csv": (list(ventas[0]) if ventas else ["origen", "empresa_id", "venta_id", "cliente_id", "sucursal_id", "producto_id", "fecha", "cantidad", "importe_centavos"], ventas),
        "ventas_diarias.csv": (list(diarios[0]), diarios),
        "prediccion_semanal.csv": (list(muestras[0]), muestras),
        "clientes_rfm.csv": (["origen", "empresa_id", "cliente_id", "fecha_corte", "ventana_dias", "recencia_dias", "frecuencia_compras", "gasto_centavos"], rfm),
    }
    parametros = {**asdict(config), "fecha_inicio": config.fecha_inicio.isoformat()}
    identidad = json.dumps({"version": VERSION_DATOS, "configuracion": parametros}, sort_keys=True)
    manifiesto = {"version_datos": VERSION_DATOS, "origen": ORIGEN,
                  "dataset_id": hashlib.sha256(identidad.encode()).hexdigest()[:16],
                  "configuracion": parametros, "moneda": "BOB", "importes": "CENTAVOS_ENTEROS",
                  "horizonte_dias": 7, "ventana_rfm_dias": 180,
                  "advertencia": "Simulación académica; sus métricas no demuestran precisión sobre ventas reales.",
                  "particiones": {}, "archivos": {}}
    for particion in ("ENTRENAMIENTO", "VALIDACION", "PRUEBA"):
        filas = [r for r in muestras if r["particion"] == particion]
        manifiesto["particiones"][particion] = {
            "filas": len(filas), "corte_desde": min(r["fecha_corte"] for r in filas),
            "corte_hasta": max(r["fecha_corte"] for r in filas),
            "objetivo_hasta": max(r["objetivo_hasta"] for r in filas)}
    destino.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".analitica-", dir=destino.parent) as temporal:
        carpeta = Path(temporal) / "dataset"
        carpeta.mkdir()
        for nombre, (campos, filas) in archivos.items():
            manifiesto["archivos"][nombre] = _guardar_csv(carpeta, nombre, campos, filas)
        (carpeta / "manifiesto.json").write_text(
            json.dumps(manifiesto, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        carpeta.rename(destino)
    return manifiesto
