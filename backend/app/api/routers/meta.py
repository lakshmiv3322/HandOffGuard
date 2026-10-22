"""Metadata router for product parameters and limitations."""

from fastapi import APIRouter, Depends
from app.api.deps import get_product_repo
from app.api.schemas.shipment import ProductResponse
from app.infrastructure.repositories.base import AbstractProductRepository

router = APIRouter(prefix="/api/meta", tags=["Metadata"])


@router.get("/product-limits", response_model=list[ProductResponse])
async def get_product_limits(
    product_repo: AbstractProductRepository = Depends(get_product_repo),
):
    """Returns all registered products and their safe temperature limits."""
    products = await product_repo.get_all()
    return products
