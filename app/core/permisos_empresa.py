"""Política de continuidad: consultar y resolver pendientes no inicia una operación nueva."""

import re


def es_operacion_nueva(metodo: str, ruta: str) -> bool:
    if metodo.upper() in {"GET", "HEAD", "OPTIONS"}:
        return False
    ruta = ruta.rstrip("/")
    if ruta == "/api/v1/usuarios" or ruta.startswith("/api/v1/usuarios/"):
        return False
    if ruta.startswith(("/api/v1/saas/", "/api/v1/perfil", "/api/v1/autenticacion/", "/api/v1/devoluciones")):
        return False
    if ruta == "/api/v1/catalogo/vestidor/pausar-realtime":
        return False
    if re.fullmatch(r"/api/v1/pagos/(qr/confirmar|stripe/confirmar-prueba)/\d+", ruta):
        return False
    if re.fullmatch(r'/api/v1/ventas-presenciales/\d+/nota/correo',ruta):
        return False
    if re.fullmatch(r"/api/v1/reservas/\d+/(cancelar|estado|anticipo/stripe|finalizar|finalizar-venta)", ruta):
        return False
    if ruta in {"/api/v1/reportes/interpretar", "/api/v1/reportes/generar", "/api/v1/reportes/exportar/pdf", "/api/v1/reportes/exportar/excel"}:
        return False
    if re.fullmatch(r"/api/v1/reportes/programados/\d+/ejecutar", ruta):
        return False
    # Permite reducir datos/uso cuando no se puede renovar el plan.
    if metodo.upper() == "DELETE" or ruta.endswith("/desactivar"):
        return False
    return True
