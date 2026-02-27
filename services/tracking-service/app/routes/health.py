# services/tracking-service/app/routes/health.py
# Health Check Endpoints - NO AUTHENTICATION REQUIRED
# Used for monitoring and Kubernetes probes

from fastapi import APIRouter, status, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.config import settings
from app.db.database import get_db

# Initialize router
router = APIRouter()


# ============================================================================
# ENDPOINT: HEALTH CHECK
# ============================================================================
# GET /health
# Authorization: NONE (public endpoint)
# Response: 200 OK with service status
# ============================================================================

@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Health check",
    tags=["Health"],
)
async def health_check() -> dict:
    """
    Health check endpoint - Basic service status.
    
    **No authentication required.**
    
    This endpoint returns basic information about the service:
    - Service name and version
    - Current environment (dev, staging, prod)
    - Current timestamp
    - Service status
    
    **Use Case:**
    - Monitoring dashboards (Prometheus, DataDog, etc.)
    - Docker container health checks
    - Load balancer status verification
    - CI/CD pipelines
    
    **Response (200):**
```json
    {
      "status": "healthy",
      "service": "tracking-service",
      "version": "1.0.0",
      "environment": "dev",
      "timestamp": "2026-02-25T12:00:00Z"
    }
```
    
    **Returns:**
    - status: Always "healthy" if service responds
    - service: Service name from config
    - version: API version from config
    - environment: Current environment (dev, staging, prod)
    - timestamp: Current UTC timestamp (ISO format)
    """
    
    return {
        "status": "healthy",
        "service": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# ============================================================================
# ENDPOINT: READINESS CHECK
# ============================================================================
# GET /ready
# Authorization: NONE (public endpoint)
# Response: 200 OK if ready, 503 if not ready
# ============================================================================

@router.get(
    "/ready",
    status_code=status.HTTP_200_OK,
    summary="Readiness check",
    tags=["Health"],
)
async def readiness_check(db: Session = Depends(get_db)) -> dict:
    """
    Readiness check - Verifies service is ready to accept traffic.
    
    **No authentication required.**
    
    This endpoint verifies:
    - Service is running
    - Database connection is healthy
    - All required dependencies are available
    
    **Use Case:**
    - Kubernetes readiness probe (determines if pod is ready)
    - Load balancer health checks
    - Startup verification in CI/CD
    - Service mesh health verification
    
    **Response (200) - Ready:**
```json
    {
      "status": "ready",
      "service": "tracking-service",
      "database": "connected",
      "timestamp": "2026-02-25T12:00:00Z"
    }
```
    
    **Response (503) - Not Ready:**
```json
    {
      "status": "not_ready",
      "service": "tracking-service",
      "database": "disconnected",
      "error": "Database connection failed",
      "timestamp": "2026-02-25T12:00:00Z"
    }
```
    
    **Kubernetes Usage:**
```yaml
    readinessProbe:
      httpGet:
        path: /ready
        port: 8000
      initialDelaySeconds: 10
      periodSeconds: 5
```
    
    **Returns:**
    - status: "ready" if all checks pass, "not_ready" if any fail
    - service: Service name
    - database: "connected" if database is healthy
    - timestamp: Current UTC timestamp
    """
    
    try:
        # TEST DATABASE CONNECTION
        # Execute a simple query to verify database is responsive
        db.execute("SELECT 1")
        database_status = "connected"
        
    except Exception as e:
        # Database connection failed
        return {
            "status": "not_ready",
            "service": settings.SERVICE_NAME,
            "database": "disconnected",
            "error": f"Database connection failed: {str(e)}",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }, status.HTTP_503_SERVICE_UNAVAILABLE
    
    # All checks passed
    return {
        "status": "ready",
        "service": settings.SERVICE_NAME,
        "database": database_status,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
