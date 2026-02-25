from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings

# Create the database engine
engine = create_engine(
    settings.database_url,
    echo=False,  # Set to True to log SQL queries
    pool_pre_ping=True  # Verify connection is alive before using it
)

# Create a session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db() -> Session:
    """
    Dependency function that provides a database session.
    Used in FastAPI routes for database access.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
