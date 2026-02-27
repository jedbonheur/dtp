"""
Database connection, session management, and initialization.

This module handles:
1. Creating SQLAlchemy engine with connection pooling
2. Session factory for database sessions
3. FastAPI dependency for injecting sessions into routes
4. Database initialization (for testing only - use Alembic in production)
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from app.core.config import settings
from app.db.base import Base

# ============================================================================
# 1. CREATE ENGINE
# ============================================================================

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=settings.DEBUG,
)

# ============================================================================
# 2. SESSION FACTORY
# ============================================================================

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# ============================================================================
# 3. DEPENDENCY INJECTION
# ============================================================================

def get_db():
    """
    FastAPI dependency that provides a database session to routes.
    
    Example usage in a route:
        @app.get("/shipments")
        def list_shipments(db: Session = Depends(get_db)):
            return db.query(Shipment).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================================================
# 4. DATABASE INITIALIZATION - For Testing ONLY
# ============================================================================

def init_db():
    """
    Create all tables from ORM models.
    
    ⚠️  USE ALEMBIC IN PRODUCTION - NOT THIS FUNCTION
    
    When to use init_db():
    - In unit tests (need fresh tables for each test)
    - In development (quick reset without migrations)
    - In local development environment
    
    When NOT to use init_db():
    - In production (use: alembic upgrade head)
    - In staging (use: alembic upgrade head)
    - When you need to track schema changes
    
    How Alembic works:
    1. Dev makes change to ORM model (e.g., add new field)
    2. Run: alembic revision --autogenerate -m "Add field"
    3. Creates migration file in alembic/versions/
    4. Run: alembic upgrade head (applies the migration)
    5. Database schema updated + version tracked
    
    This approach gives you:
    ✅ Version control for database schema
    ✅ Ability to rollback changes
    ✅ History of all schema changes
    ✅ Reproducible deployments
    
    Learning moment: Why Alembic in production?
    - Without it: You can't easily rollback a bad schema change
    - Without it: You don't know who made what change when
    - Without it: Each environment might have different schemas
    - With Alembic: All problems solved
    """
    Base.metadata.create_all(bind=engine)