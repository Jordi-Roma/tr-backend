from fastapi import APIRouter, Depends, Request

from app.modules.administracion.schemas.catalogo.catalogo_request import (
    ActualizarCategoriaRequest,
    ActualizarColorRequest,
    ActualizarTallaRequest,
    CrearCategoriaRequest,
    CrearColorRequest,
    CrearTallaRequest,
    ActualizarMarcaRequest,
    CrearMarcaRequest,
)
from app.modules.administracion.schemas.catalogo.catalogo_response import (
    CategoriaResponse,
    ColorResponse,
    MensajeResponse,
    TallaResponse,
    MarcaResponse,
)
from app.modules.administracion.services.catalogo_service import (
    editar_categoria,
    editar_color,
    editar_talla,
    eliminar_categoria,
    eliminar_color,
    eliminar_talla,
    obtener_categoria,
    obtener_categorias,
    obtener_color,
    obtener_colores,
    obtener_talla,
    obtener_tallas,
    reactivar_categoria,
    reactivar_color,
    reactivar_talla,
    registrar_categoria,
    registrar_color,
    registrar_talla,
    editar_marca,
    eliminar_marca,
    obtener_marca,
    obtener_marcas,
    reactivar_marca,
    registrar_marca,
)
from app.modules.autenticacion.dependencies.admin_required import requerir_admin

router = APIRouter(
    prefix="/api/v1",
    tags=["Catálogo"],
)


def _ip(req: Request) -> str | None:
    fwd = req.headers.get("X-Forwarded-For")
    return fwd.split(",")[0].strip() if fwd else (req.client.host if req.client else None)


def _ua(req: Request) -> str | None:
    return req.headers.get("User-Agent")


# ── CATEGORÍAS ─────────────────────────────────────────────────────────────

@router.get("/categorias", response_model=list[CategoriaResponse])
def listar_categorias_endpoint(
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> list[CategoriaResponse]:
    return obtener_categorias()


@router.post("/categorias", response_model=CategoriaResponse)
def crear_categoria_endpoint(
    request: CrearCategoriaRequest,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> CategoriaResponse:
    return registrar_categoria(request, usuario_actual, _ip(http_request), _ua(http_request))


@router.get("/categorias/{categoria_id}", response_model=CategoriaResponse)
def obtener_categoria_endpoint(
    categoria_id: int,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> CategoriaResponse:
    return obtener_categoria(categoria_id)


@router.put("/categorias/{categoria_id}", response_model=CategoriaResponse)
def actualizar_categoria_endpoint(
    categoria_id: int,
    request: ActualizarCategoriaRequest,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> CategoriaResponse:
    return editar_categoria(categoria_id, request, usuario_actual, _ip(http_request), _ua(http_request))


@router.patch("/categorias/{categoria_id}/desactivar", response_model=MensajeResponse)
def desactivar_categoria_endpoint(
    categoria_id: int,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> MensajeResponse:
    return eliminar_categoria(categoria_id, usuario_actual, _ip(http_request), _ua(http_request))


@router.patch("/categorias/{categoria_id}/activar", response_model=CategoriaResponse)
def activar_categoria_endpoint(
    categoria_id: int,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> CategoriaResponse:
    return reactivar_categoria(categoria_id, usuario_actual, _ip(http_request), _ua(http_request))


# ── TALLAS ─────────────────────────────────────────────────────────────────

@router.get("/tallas", response_model=list[TallaResponse])
def listar_tallas_endpoint(
    tipo_prenda: str | None = None,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> list[TallaResponse]:
    return obtener_tallas(tipo_prenda=tipo_prenda)


@router.post("/tallas", response_model=TallaResponse)
def crear_talla_endpoint(
    request: CrearTallaRequest,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> TallaResponse:
    return registrar_talla(request, usuario_actual, _ip(http_request), _ua(http_request))


@router.get("/tallas/{talla_id}", response_model=TallaResponse)
def obtener_talla_endpoint(
    talla_id: int,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> TallaResponse:
    return obtener_talla(talla_id)


@router.put("/tallas/{talla_id}", response_model=TallaResponse)
def actualizar_talla_endpoint(
    talla_id: int,
    request: ActualizarTallaRequest,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> TallaResponse:
    return editar_talla(talla_id, request, usuario_actual, _ip(http_request), _ua(http_request))


@router.patch("/tallas/{talla_id}/desactivar", response_model=MensajeResponse)
def desactivar_talla_endpoint(
    talla_id: int,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> MensajeResponse:
    return eliminar_talla(talla_id, usuario_actual, _ip(http_request), _ua(http_request))


@router.patch("/tallas/{talla_id}/activar", response_model=TallaResponse)
def activar_talla_endpoint(
    talla_id: int,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> TallaResponse:
    return reactivar_talla(talla_id, usuario_actual, _ip(http_request), _ua(http_request))


# ── COLORES ────────────────────────────────────────────────────────────────

@router.get("/colores", response_model=list[ColorResponse])
def listar_colores_endpoint(
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> list[ColorResponse]:
    return obtener_colores()


@router.post("/colores", response_model=ColorResponse)
def crear_color_endpoint(
    request: CrearColorRequest,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> ColorResponse:
    return registrar_color(request, usuario_actual, _ip(http_request), _ua(http_request))


@router.get("/colores/{color_id}", response_model=ColorResponse)
def obtener_color_endpoint(
    color_id: int,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> ColorResponse:
    return obtener_color(color_id)


@router.put("/colores/{color_id}", response_model=ColorResponse)
def actualizar_color_endpoint(
    color_id: int,
    request: ActualizarColorRequest,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> ColorResponse:
    return editar_color(color_id, request, usuario_actual, _ip(http_request), _ua(http_request))


@router.patch("/colores/{color_id}/desactivar", response_model=MensajeResponse)
def desactivar_color_endpoint(
    color_id: int,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> MensajeResponse:
    return eliminar_color(color_id, usuario_actual, _ip(http_request), _ua(http_request))


@router.patch("/colores/{color_id}/activar", response_model=ColorResponse)
def activar_color_endpoint(
    color_id: int,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> ColorResponse:
    return reactivar_color(color_id, usuario_actual, _ip(http_request), _ua(http_request))


# ── MARCAS ─────────────────────────────────────────────────────────────────

@router.get("/marcas", response_model=list[MarcaResponse])
def listar_marcas_endpoint(
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> list[MarcaResponse]:
    return obtener_marcas()


@router.post("/marcas", response_model=MarcaResponse)
def crear_marca_endpoint(
    request: CrearMarcaRequest,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> MarcaResponse:
    return registrar_marca(request, usuario_actual, _ip(http_request), _ua(http_request))


@router.get("/marcas/{marca_id}", response_model=MarcaResponse)
def obtener_marca_endpoint(
    marca_id: int,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> MarcaResponse:
    return obtener_marca(marca_id)


@router.put("/marcas/{marca_id}", response_model=MarcaResponse)
def actualizar_marca_endpoint(
    marca_id: int,
    request: ActualizarMarcaRequest,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> MarcaResponse:
    return editar_marca(marca_id, request, usuario_actual, _ip(http_request), _ua(http_request))


@router.patch("/marcas/{marca_id}/desactivar", response_model=MensajeResponse)
def desactivar_marca_endpoint(
    marca_id: int,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> MensajeResponse:
    return eliminar_marca(marca_id, usuario_actual, _ip(http_request), _ua(http_request))


@router.patch("/marcas/{marca_id}/activar", response_model=MarcaResponse)
def activar_marca_endpoint(
    marca_id: int,
    http_request: Request,
    usuario_actual: dict[str, object] = Depends(requerir_admin),
) -> MarcaResponse:
    return reactivar_marca(marca_id, usuario_actual, _ip(http_request), _ua(http_request))
