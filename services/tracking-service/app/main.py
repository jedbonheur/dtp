"""
FastAPI Application Entry Point

This is the main orchestrator that:
1. Initializes FastAPI
2. Sets up lifespan (startup/shutdown)
3. Registers middleware
4. Includes route routers
5. Defines error handlers
6. Configures documentation

Think of it as the "main.py" of your entire service - it ties everything together.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.routes import health_router, shipments_router

# Configure logging
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


# ============================================================================
# LIFESPAN: Application startup and shutdown
# ============================================================================
# This context manager runs code when the app starts and stops.
# Perfect for: database initialization, connection pools, resource cleanup

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages application lifespan events.
    
    STARTUP (before yield):
        - Initialize database tables
        - Log startup message
    
    SHUTDOWN (after yield):
        - Log shutdown message
        - Clean up resources (optional)
    """
    # ===== STARTUP =====
    logger.info("=" * 80)
    logger.info("🚀 TRACKING SERVICE STARTING UP")
    logger.info("=" * 80)
    
    # NOTE: Database migrations are handled via Alembic
    # See: alembic/versions/ for schema changes
    # To run migrations locally:
    #   alembic upgrade head
    #
    # To create a new migration after model changes:
    #   alembic revision --autogenerate -m "add new column"
    #   alembic upgrade head
    
    logger.info(f"🌍 Environment: {settings.environment}")
    logger.info(f"📡 Service running on port {settings.service_port}")
    logger.info("✨ Ready to accept requests!")
    logger.info("=" * 80)
    
    # Service is running - yield control to FastAPI
    yield
    
    # ===== SHUTDOWN =====
    logger.info("=" * 80)
    logger.info("🛑 TRACKING SERVICE SHUTTING DOWN")
    logger.info("=" * 80)
    # Add cleanup code here if needed (close DB connections, cleanup files, etc.)


# ============================================================================
# FASTAPI APPLICATION INITIALIZATION
# ============================================================================

app = FastAPI(
    title=settings.service_name,
    description="Event-driven shipment tracking service with real-time updates",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",  # ReDoc documentation
    openapi_url="/openapi.json",  # OpenAPI schema
    lifespan=lifespan,  # Attach our lifespan handler
)


# ============================================================================
# MIDDLEWARE: Layers that process every request/response
# ============================================================================

# 1. TrustedHost Middleware
# Purpose: Only allow requests from trusted hosts (security)
# Example: Prevent someone from accessing http://evil-domain-spoofing-us.com
if settings.trusted_hosts:
    logger.info(f"🔒 Adding TrustedHost middleware with hosts: {settings.trusted_hosts}")
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.trusted_hosts,
    )

# 2. CORS Middleware
# Purpose: Allow cross-origin requests from web apps (browser security)
# Only enable in development - production uses API Gateway
if settings.environment == "dev":
    logger.info("🔓 CORS enabled (development mode)")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins in dev
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# ============================================================================
# GLOBAL ERROR HANDLER
# ============================================================================
# Catches ALL unhandled exceptions and returns consistent JSON error format

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catches any exception that bubbles up and returns a consistent error response.
    
    This ensures that:
    1. Client always gets JSON (not HTML stack trace)
    2. Errors have consistent format: {error, error_code, detail, timestamp}
    3. We log the error for debugging
    4. We don't expose internal details in production
    """
    
    # Log the error with request context
    logger.error(
        f"❌ Unhandled exception in {request.method} {request.url.path}",
        exc_info=exc,
    )
    
    # Build error response
    error_response = {
        "error": "INTERNAL_SERVER_ERROR",
        "error_code": "500",
        "detail": "An unexpected error occurred. Please try again later.",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "request_id": request.headers.get("X-Request-ID", "unknown"),
    }
    
    # In development, include the actual error message
    if settings.environment == "dev":
        error_response["detail"] = str(exc)
        error_response["exception_type"] = type(exc).__name__
    
    return JSONResponse(
        status_code=500,
        content=error_response,
    )


# ============================================================================
# ROUTE REGISTRATION
# ============================================================================
# Include route routers - this registers all endpoints from each router

# Health check routes (GET /health, GET /ready)
# These don't require authentication and check service status
app.include_router(health_router)

# Shipment CRUD routes (POST /shipments, GET /shipments/{id}, etc.)
# All these require authentication via X-User-ID, X-User-Role headers
# Prefix: /api/v1/tracking - versioned for future backward compatibility
app.include_router(
    shipments_router,
    prefix="/api/v1/tracking",
    tags=["shipments"],
)


# ============================================================================
# ROOT ENDPOINT
# ============================================================================

@app.get("/")
async def root() -> dict[str, Any]:
    """
    Root endpoint - useful for health checks and API info.
    
    Returns basic service information without requiring authentication.
    Useful for load balancers and monitoring tools.
    """
    return {
        "message": "Welcome to Tracking Service API",
        "service": settings.service_name,
        "version": "1.0.0",
        "docs": "/docs",  # Point to Swagger UI
        "docs_url": "/redoc",  # Point to ReDoc
        "status": "running",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# ============================================================================
# STARTUP LOG
# ============================================================================

if __name__ == "__main__":
    logger.info("🔧 Running app in standalone mode (for local development)")
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.service_port,
        reload=True,
    )