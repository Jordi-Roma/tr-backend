from pydantic import BaseModel

from app.modules.catalogo.schemas.catalogo_publico.catalogo_publico_response import CatalogoPrendaItemResponse


class PreferenciasIAResponse(BaseModel):
    categorias: list[int] = []
    usar_historial: bool = True


class RecomendacionPrendaResponse(CatalogoPrendaItemResponse):
    motivo: str
    score: float | None = None
