from fastapi import APIRouter, HTTPException

from app.modules.catalogo.vestidor.schemas.vestidor_asset_schema import PrendaARResponse
from app.modules.catalogo.vestidor.schemas.vestidor_sesion_schema import (
    CrearSesionVestidorRequest,
    SesionVestidorResponse,
)
from app.modules.catalogo.vestidor.vestidor_service import (
    obtener_prenda_ar,
    listar_prendas_vestidor,
    guardar_sesion_vestidor,
)

router = APIRouter(
    prefix="/api/v1/catalogo/vestidor",
    tags=["CU24 - Vestidor Virtual con Realidad Aumentada"],
)


@router.get(
    "/prenda/{producto_id}",
    response_model=PrendaARResponse,
    summary="Obtener activos y dimensiones de prenda para vestidor virtual AR",
)
def get_prenda_vestidor(producto_id: int) -> PrendaARResponse:
    return obtener_prenda_ar(producto_id)


@router.get(
    "/prendas-disponibles",
    summary="Listar prendas activas disponibles para el carrusel del vestidor",
)
def get_prendas_carrusel(limite: int = 30) -> list[dict[str, object]]:
    return listar_prendas_vestidor(limite)


@router.post(
    "/sesion",
    response_model=SesionVestidorResponse,
    summary="Registrar trazabilidad de prueba virtual en vestidor",
)
def post_sesion_vestidor(request: CrearSesionVestidorRequest) -> SesionVestidorResponse:
    return guardar_sesion_vestidor(request)


@router.get(
    "/config",
    summary="Configuración dinámica del motor AR para la app móvil",
)
def get_vestidor_config() -> dict[str, str]:
    return {
        "ar_engine_url": "https://www.snapchat.com/unlock/?type=SNAPCODE&uuid=b5d99fe6e0d5428593ade7347131cd6e&metadata=01",
        "ar_engine_name": "Motor 3D AR (PantBlanco StyleAR)",
    }


try:
    import multipart  # noqa: F401
    from fastapi import File, Form, Request, UploadFile

    MULTIPART_DISPONIBLE = True
except ModuleNotFoundError:
    MULTIPART_DISPONIBLE = False


if MULTIPART_DISPONIBLE:

    @router.post(
        "/probar-ia",
        summary="Procesar prueba virtual de prenda sobre foto de usuario con IA",
    )
    async def post_probar_ia(
        request: Request,
        imagen: UploadFile = File(...),
        producto_id: int = Form(...),
        talla: str | None = Form(None),
        color: str | None = Form(None),
        cliente_id: int | None = Form(None),
    ) -> dict[str, object]:
        try:
            from app.modules.catalogo.vestidor.vestidor_ia_service import procesar_tryon_ia
        except ModuleNotFoundError as error:
            raise HTTPException(
                status_code=503,
                detail=(
                    "El motor de prueba virtual con IA no tiene sus dependencias "
                    "instaladas. Instala las dependencias del backend y reinicia el servidor."
                ),
            ) from error

        contenido = await imagen.read()
        host_base_url = str(request.base_url).rstrip("/")
        forwarded_host = request.headers.get("x-forwarded-host")
        forwarded_proto = request.headers.get("x-forwarded-proto", "https")
        if forwarded_host:
            host_base_url = f"{forwarded_proto}://{forwarded_host}"

        return procesar_tryon_ia(
            imagen_bytes=contenido,
            producto_id=producto_id,
            talla=talla,
            color=color,
            cliente_id=cliente_id,
            host_base_url=host_base_url,
        )

else:

    @router.post(
        "/probar-ia",
        summary="Procesar prueba virtual de prenda sobre foto de usuario con IA",
    )
    async def post_probar_ia_no_disponible() -> dict[str, object]:
        raise HTTPException(
            status_code=503,
            detail=(
                "El motor de prueba virtual con IA requiere python-multipart y "
                "sus dependencias de visión. Instala las dependencias del backend "
                "y reinicia el servidor."
            ),
        )

