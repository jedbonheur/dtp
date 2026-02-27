"""
Routes Package - Exports all API route routers

This file centralizes route imports, making it easier to:
1. See all routes at a glance
2. Add/remove routes in one place
3. Avoid circular imports
"""

from app.routes.health import router as health_router
from app.routes.shipments import router as shipments_router

__all__ = [
    "health_router",
    "shipments_router",
]