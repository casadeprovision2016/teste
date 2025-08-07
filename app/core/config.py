# app/core/config.py
"""
Configuração centralizada do sistema
"""
from pydantic_settings import BaseSettings
from typing import List, Optional
from functools import lru_cache
import os
from pathlib import Path

class Settings(BaseSettings):
    """Configurações principais da aplicação"""
    
    # Application
    APP_NAME: str = "Sistema de Processamento de Editais"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    WORKERS: int = 4
    
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Edital Processor"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "jwt-secret-key-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data/editais.db")
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD", None)
    REDIS_MAX_CONNECTIONS: int = 10
    
    # Celery
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
    CELERY_TASK_TIME_LIMIT: int = 1800  # 30 minutes
    CELERY_TASK_SOFT_TIME_LIMIT: int = 1500  # 25 minutes
    CELERY_WORKER_CONCURRENCY: int = 4
    CELERY_WORKER_MAX_TASKS_PER_CHILD: int = 10
    
    # Storage
    STORAGE_BASE_PATH: str = os.getenv("STORAGE_BASE_PATH", "/app/storage/editais")
    PROCESSED_PATH: str = os.getenv("PROCESSED_PATH", "/app/storage/processados")
    TEMP_PATH: str = os.getenv("TEMP_PATH", "/app/storage/temp")
    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100MB
    
    # AI Settings
    MODEL_NAME: str = os.getenv("MODEL_NAME", "llama3.2:3b")
    MODEL_MAX_TOKENS: int = 4096
    MODEL_TEMPERATURE: float = 0.1
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://ollama:11434")
    
    # Docling Settings
    DOCLING_OCR_ENABLED: bool = True
    DOCLING_OCR_LANGUAGES: List[str] = ["por", "eng"]
    DOCLING_TABLE_DETECTION: bool = True
    DOCLING_CACHE_ENABLED: bool = True
    
    # Processing Limits
    DAILY_PROCESSING_LIMIT: int = 50
    MAX_CONCURRENT_TASKS: int = 4
    TASK_RETRY_LIMIT: int = 3
    TASK_RETRY_DELAY: int = 60
    
    # Monitoring
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    SENTRY_DSN: Optional[str] = os.getenv("SENTRY_DSN", None)
    
    # Email (for notifications)
    SMTP_HOST: Optional[str] = os.getenv("SMTP_HOST", None)
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = os.getenv("SMTP_USER", None)
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD", None)
    SMTP_FROM: str = "noreply@editalprocessor.com"
    
    # Webhook Settings
    WEBHOOK_TIMEOUT: int = 30
    WEBHOOK_RETRY_COUNT: int = 3
    WEBHOOK_RETRY_DELAY: int = 5
    
    # Flower Dashboard
    FLOWER_PASSWORD: str = os.getenv("FLOWER_PASSWORD", "admin123")
    
    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()

settings = get_settings()
