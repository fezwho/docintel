"""
Metrics endpoint for Prometheus scraping.
"""

from fastapi import APIRouter, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

router = APIRouter(tags=["Metrics"])


@router.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.
    
    Scraped by Prometheus server every N seconds.
    Returns metrics in Prometheus text format.
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )