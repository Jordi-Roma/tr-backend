from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import CORS_ORIGINS
from app.database.connection import get_connection
from app.modules.administracion.router.ciudad_sucursal_router import (
    router as ciudad_sucursal_router,
)
from app.modules.administracion.router.catalogo_router import (
    router as catalogo_router,
)
from app.modules.catalogo.router.catalogo_publico_router import (
    router as catalogo_publico_router,
)
from app.modules.catalogo.vestidor.vestidor_router import (
    router as vestidor_router,
)
from app.modules.administracion.router.empleado_router import (
    router as empleado_router,
)
from app.modules.administracion.router.proveedor_router import (
    router as proveedor_router,
)
from app.modules.administracion.router.temporada_router import (
    router as temporada_router,
)
from app.modules.administracion.router.coleccion_router import (
    router as coleccion_router,
)
from app.modules.administracion.router.producto_router import router as producto_router
from app.modules.administracion.router.promocion_router import router as promocion_router
from app.modules.administracion.router.variante_router import router as variante_router
from app.modules.autenticacion.router.bitacora_router import router as bitacora_router
from app.modules.reservas.router.carrito_router import router as carrito_router
from app.modules.reservas.router.reserva_router import router as reserva_router
from app.modules.ventas_inventario.router.inventario_router import (
    router as ventas_inventario_router,
)
from app.modules.ventas_inventario.router.delivery_router import router as delivery_router
from app.modules.ventas_inventario.router.pago_router import router as pago_router
from app.modules.inteligencia.router.reporte_router import router as reporte_router
from app.modules.inteligencia.router.recomendacion_router import router as recomendacion_router
from app.modules.inteligencia.router.asistente_router import router as asistente_router
from app.modules.autenticacion.router.perfil_router import router as perfil_router
from app.modules.autenticacion.router.password_reset_router import (
    router as password_reset_router,
)
from app.modules.autenticacion.router.registro_router import router as registro_router
from app.modules.autenticacion.router.rol_permiso_router import (
    router as rol_permiso_router,
)
from app.modules.autenticacion.router.sesion_router import router as sesion_router
from app.modules.autenticacion.router.usuario_admin_router import (
    router as usuario_admin_router,
)


app = FastAPI(
    title="API Tienda de Ropa",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|.*\.ngrok-free\.app|.*\.ngrok\.io|.*\.onrender\.com|.*\.up\.railway\.app)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(registro_router)
app.include_router(sesion_router)
app.include_router(password_reset_router)
app.include_router(perfil_router)
app.include_router(rol_permiso_router)
app.include_router(usuario_admin_router)
app.include_router(ciudad_sucursal_router)
app.include_router(empleado_router)
app.include_router(proveedor_router)
app.include_router(catalogo_publico_router)
app.include_router(vestidor_router)
app.include_router(catalogo_router)
app.include_router(temporada_router)
app.include_router(coleccion_router)
app.include_router(producto_router)
app.include_router(promocion_router)
app.include_router(variante_router)
app.include_router(carrito_router)
app.include_router(reserva_router)
app.include_router(ventas_inventario_router)
app.include_router(pago_router)
app.include_router(delivery_router)
app.include_router(bitacora_router)
app.include_router(reporte_router)
app.include_router(recomendacion_router)
app.include_router(asistente_router)

from fastapi.staticfiles import StaticFiles
import os
os.makedirs("static/images", exist_ok=True)
os.makedirs("static/tryon", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
def run_db_migrations():
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            ALTER TABLE producto
            ADD COLUMN IF NOT EXISTS tipo_prenda VARCHAR(20) NOT NULL DEFAULT 'SUPERIOR',
            ADD COLUMN IF NOT EXISTS tipo_corte VARCHAR(30) NOT NULL DEFAULT 'REGULAR_FIT',
            ADD COLUMN IF NOT EXISTS ancho_base_cm NUMERIC(6,2) NOT NULL DEFAULT 53.0,
            ADD COLUMN IF NOT EXISTS largo_base_cm NUMERIC(6,2) NOT NULL DEFAULT 72.0,
            ADD COLUMN IF NOT EXISTS modelo_3d_url VARCHAR(500) NULL;
        """)
        conn.commit()
        conn.close()
        print("[Startup] Migraciones de base de datos verificadas con éxito.")
    except Exception as e:
        print("[Startup] Error al verificar migraciones:", e)


@app.get("/api/v1/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "backend-tr",
    }


@app.get("/api/v1/db-check")
def db_check() -> dict[str, str]:
    connection = get_connection()
    connection.close()

    return {
        "status": "ok",
        "database": "connected",
    }


@app.get("/api/v1/descargar-apk")
def descargar_apk():
    import os
    from fastapi.responses import FileResponse
    paths = [
        r"c:\MATERIAS\SI2\Presentacion\tr-mobile\build\app\outputs\flutter-apk\app-release.apk",
        r"c:\MATERIAS\SI2\PrimerParcial\mobile_tr\build\app\outputs\flutter-apk\app-release.apk",
    ]
    for apk_path in paths:
        if os.path.exists(apk_path):
            return FileResponse(
                apk_path,
                media_type="application/vnd.android.package-archive",
                filename="StyleAR-release.apk",
            )
    return {"error": "APK no encontrado o aún en compilación"}

