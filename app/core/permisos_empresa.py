"""Política de continuidad: consultar y resolver pendientes no inicia una operación nueva."""

import re


def es_operacion_nueva(metodo: str, ruta: str) -> bool:
    if metodo.upper() in {"GET", "HEAD", "OPTIONS"}:
        return False
    ruta = ruta.rstrip("/")
    if ruta == '/api/v1/asistente/chat':
        return False
    if ruta == "/api/v1/usuarios" or ruta.startswith("/api/v1/usuarios/"):
        return False
    if ruta.startswith(("/api/v1/saas/", "/api/v1/perfil", "/api/v1/autenticacion/", "/api/v1/devoluciones")):
        return False
    if re.fullmatch(r"/api/v1/respaldos/[0-9a-fA-F-]+/(previsualizar|restaurar)", ruta):
        return False
    if ruta.startswith(("/api/v1/pagos-empresa", "/api/v1/notificaciones", "/api/v1/posventa")):
        return False
    if ruta == "/api/v1/catalogo/vestidor/pausar-realtime":
        return False
    if re.fullmatch(r"/api/v1/pagos/(qr/confirmar|stripe/confirmar-prueba)/\d+", ruta):
        return False
    if re.fullmatch(r'/api/v1/ventas-presenciales/\d+/nota/correo',ruta):
        return False
    if re.fullmatch(r"/api/v1/delivery/\d+/(estado|incidencias)", ruta):
        return False
    if re.fullmatch(r"/api/v1/reservas/\d+/(cancelar|estado|anticipo/stripe|finalizar|finalizar-venta)", ruta):
        return False
    if ruta in {"/api/v1/reportes/interpretar", "/api/v1/reportes/generar", "/api/v1/reportes/exportar/pdf", "/api/v1/reportes/exportar/excel"}:
        return False
    if ruta in {'/api/v1/reportes/detalle','/api/v1/reportes/dashboard'}:
        return False
    if ruta in {'/api/v1/reportes/analitica/interpretar', '/api/v1/reportes/analitica/exportar/pdf',
                '/api/v1/reportes/analitica/exportar/excel'}:
        return False
    if re.fullmatch(r"/api/v1/reportes/programados/\d+/ejecutar", ruta):
        return False
    if metodo.upper()=='PATCH' and re.fullmatch(r"/api/v1/reportes/programados/\d+/estado", ruta):
        # Pausar sigue permitido; el repositorio valida vigencia al reactivar.
        return False
    # Permite reducir datos/uso cuando no se puede renovar el plan.
    if metodo.upper() == "DELETE" or ruta.endswith("/desactivar"):
        return False
    return True
