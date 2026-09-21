from app.main import app


def test_existe_endpoint_crear_usuario() -> None:
    rutas = app.openapi()["paths"]
    assert "post" in rutas["/api/v1/usuarios"]


def test_existen_endpoints_salud() -> None:
    rutas = app.openapi()["paths"]
    assert "/api/v1/health" in rutas
    assert "/api/v1/db-check" in rutas
