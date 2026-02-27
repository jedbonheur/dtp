"""
Configuration Management

Loads settings from environment variables using Pydantic v2.

This allows the application to work in different environments:
- Development: local defaults
- Testing: test-specific config
- Production: environment variables from deployment system

Usage:
    from app.core.config import settings
    print(settings.database_url)
    print(settings.environment)
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    model_config = SettingsConfigDict(extra="ignore")
    
    # ════════════════════════════════════════════════════════════
    # SERVICE METADATA
    # ════════════════════════════════════════════════════════════
    
    service_name: str = "tracking-service"
    service_version: str = "1.0.0"
    environment: str = "dev"  # dev, staging, prod
    
    # ════════════════════════════════════════════════════════════
    # DATABASE CONFIGURATION (PostgreSQL)
    # ════════════════════════════════════════════════════════════
    
    postgres_db: str = "dtp"
    postgres_user: str = "dtp"
    postgres_password: str = "dtp"
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    
    # SQLAlchemy settings
    db_echo: bool = False  # Log all SQL queries (dev only!)
    db_pool_size: int = 10  # Connection pool size
    db_max_overflow: int = 20  # Max overflow connections
    
    # ════════════════════════════════════════════════════════════
    # AUTHENTICATION & SECURITY
    # ════════════════════════════════════════════════════════════
    
    jwt_secret: str = "dev-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    
    # ════════════════════════════════════════════════════════════
    # API SETTINGS
    # ════════════════════════════════════════════════════════════
    
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]
    trusted_hosts: list[str] = ["localhost", "127.0.0.1"]
    
    # ════════════════════════════════════════════════════════════
    # RATE LIMITING (requests per minute per role)
    # ════════════════════════════════════════════════════════════
    
    rate_limit_client: int = 100
    rate_limit_admin: int = 1000
    rate_limit_driver: int = 500
    
    # ════════════════════════════════════════════════════════════
    # LOGGING
    # ════════════════════════════════════════════════════════════
    
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # ════════════════════════════════════════════════════════════
    # PAGINATION
    # ════════════════════════════════════════════════════════════
    
    default_limit: int = 20
    max_limit: int = 100
    
    # ════════════════════════════════════════════════════════════
    # COMPUTED PROPERTIES (Built from individual settings)
    # ════════════════════════════════════════════════════════════
    
    @property
    def database_url(self) -> str:
        """Construct PostgreSQL connection URL from individual parts"""
        return (
            f"postgresql+psycopg://{self.postgres_user}:"
            f"{self.postgres_password}@{self.postgres_host}:"
            f"{self.postgres_port}/{self.postgres_db}"
        )
    
    @property
    def is_dev(self) -> bool:
        """Check if running in development mode"""
        return self.environment.lower() == "dev"
    
    @property
    def is_prod(self) -> bool:
        """Check if running in production mode"""
        return self.environment.lower() == "prod"
    
    @property
    def is_test(self) -> bool:
        """Check if running in test mode"""
        return self.environment.lower() == "test"


# ════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ════════════════════════════════════════════════════════════════

settings = Settings()

# Log configuration on startup
if __name__ == "__main__":
    print(f"Service: {settings.service_name} v{settings.service_version}")
    print(f"Environment: {settings.environment}")
    print(f"Database: {settings.database_url}")
    print(f"Log Level: {settings.log_level}")