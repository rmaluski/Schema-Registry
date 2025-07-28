from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Service configuration
    app_name: str = "Schema Registry"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # Etcd configuration
    etcd_host: str = "localhost"
    etcd_port: int = 2379
    etcd_username: Optional[str] = None
    etcd_password: Optional[str] = None
    etcd_ca_cert: Optional[str] = None
    etcd_cert_key: Optional[str] = None
    etcd_cert_cert: Optional[str] = None
    
    # API configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = ""
    
    # Security
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # GitHub OIDC (for CI bot)
    github_oidc_issuer: str = "https://token.actions.githubusercontent.com"
    github_oidc_audience: str = "schema-registry"
    
    # Metrics
    metrics_enabled: bool = True
    metrics_port: int = 9090
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    
    # Cache
    cache_ttl_seconds: int = 600  # 10 minutes
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings() 