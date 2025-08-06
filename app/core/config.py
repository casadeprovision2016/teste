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
    
    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()

settings = get_settings()

# =====================================================
# app/core/database.py
"""
Database configuration and session management
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import logging

from app.core.config import settings
from app.models import Base

logger = logging.getLogger(__name__)

# Create engine
if "sqlite" in settings.DATABASE_URL:
    # SQLite specific settings
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=settings.DEBUG
    )
    
    # Enable foreign keys for SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()
else:
    # PostgreSQL or other databases
    engine = create_engine(
        settings.DATABASE_URL,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        echo=settings.DEBUG
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Session:
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database with tables"""
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")

# =====================================================
# app/core/security.py
"""
Security utilities for authentication and authorization
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import secrets

from app.core.config import settings
from app.core.database import get_db
from app.models import User

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash password"""
    return pwd_context.hash(password)

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    
    return encoded_jwt

def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    
    return encoded_jwt

def generate_api_key() -> str:
    """Generate secure API key"""
    return secrets.token_urlsafe(32)

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        
        if user_id is None:
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == user_id).first()
    
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

async def get_current_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current admin user"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user

# =====================================================
# scripts/deploy.sh
"""
Deployment script
"""
#!/bin/bash

set -e

echo "🚀 Starting deployment process..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ .env file not found. Creating from example..."
    cp .env.example .env
    echo "⚠️  Please update .env with your configuration"
    exit 1
fi

# Load environment variables
source .env

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo "📋 Checking prerequisites..."

if ! command_exists docker; then
    echo "❌ Docker is not installed"
    exit 1
fi

if ! command_exists docker-compose; then
    echo "❌ Docker Compose is not installed"
    exit 1
fi

echo "✅ Prerequisites check passed"

# Build images
echo "🔨 Building Docker images..."
docker-compose build --no-cache

# Pull Llama model
echo "🤖 Pulling Llama model..."
docker-compose run --rm ollama ollama pull llama3.2:3b

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p storage/editais storage/processados storage/temp
mkdir -p data logs models cache/docling

# Set permissions
echo "🔐 Setting permissions..."
chmod -R 755 storage data logs models cache

# Initialize database
echo "🗄️ Initializing database..."
docker-compose run --rm app-api python -c "from app.core.database import init_db; init_db()"

# Start services
echo "🚀 Starting services..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check health
echo "🏥 Checking service health..."
curl -f http://localhost:8000/health || echo "⚠️  API health check failed"

# Show service status
echo "📊 Service status:"
docker-compose ps

echo "✅ Deployment completed successfully!"
echo ""
echo "📌 Access points:"
echo "   - API Documentation: http://localhost:8000/docs"
echo "   - Flower Dashboard: http://localhost:5555 (admin/admin123)"
echo "   - Health Check: http://localhost:8000/health"
echo ""
echo "📝 Default credentials:"
echo "   - Flower: admin/admin123"
echo ""
echo "🔧 Useful commands:"
echo "   - View logs: docker-compose logs -f"
echo "   - Stop services: docker-compose down"
echo "   - Restart services: docker-compose restart"
echo "   - Scale workers: docker-compose up -d --scale app-worker=4"

# =====================================================
# scripts/test_upload.py
"""
Script to test edital upload
"""
import requests
import sys
import json
from pathlib import Path
import time

API_URL = "http://localhost:8000"
API_VERSION = "/api/v1"

def get_token(username: str, password: str) -> str:
    """Get authentication token"""
    response = requests.post(
        f"{API_URL}{API_VERSION}/auth/token",
        data={"username": username, "password": password}
    )
    
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        print(f"Authentication failed: {response.text}")
        sys.exit(1)

def upload_edital(token: str, file_path: str, metadata: dict) -> str:
    """Upload edital for processing"""
    headers = {"Authorization": f"Bearer {token}"}
    
    with open(file_path, 'rb') as f:
        files = {'file': (Path(file_path).name, f, 'application/pdf')}
        data = metadata
        
        response = requests.post(
            f"{API_URL}{API_VERSION}/editais/processar",
            headers=headers,
            files=files,
            data=data
        )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Upload successful! Task ID: {result['task_id']}")
        return result['task_id']
    else:
        print(f"❌ Upload failed: {response.text}")
        sys.exit(1)

def check_status(token: str, task_id: str):
    """Check processing status"""
    headers = {"Authorization": f"Bearer {token}"}
    
    while True:
        response = requests.get(
            f"{API_URL}{API_VERSION}/editais/status/{task_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            status = response.json()
            print(f"Status: {status['status']} - {status['message']}")
            
            if status['progress']:
                print(f"Progress: {status['progress']}%")
            
            if status['status'] in ['completed', 'failed']:
                return status['status']
        
        time.sleep(5)

def get_result(token: str, task_id: str):
    """Get processing result"""
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(
        f"{API_URL}{API_VERSION}/editais/resultado/{task_id}",
        headers=headers
    )
    
    if response.status_code == 200:
        result = response.json()
        print("\n📊 Processing Result:")
        print(f"  - Quality Score: {result['quality_score']}")
        print(f"  - Products Found: {len(result['products_table'])}")
        print(f"  - Risks Identified: {len(result['risk_analysis'].get('risks', []))}")
        print(f"  - Opportunities: {len(result['opportunities'])}")
        
        # Save result to file
        output_file = f"result_{task_id}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 Full result saved to: {output_file}")
    else:
        print(f"❌ Failed to get result: {response.text}")

def main():
    """Main test function"""
    if len(sys.argv) < 2:
        print("Usage: python test_upload.py <pdf_file>")
        sys.exit(1)
    
    pdf_file = sys.argv[1]
    
    if not Path(pdf_file).exists():
        print(f"File not found: {pdf_file}")
        sys.exit(1)
    
    # Test credentials (create a test user first)
    username = "test@example.com"
    password = "testpassword123"
    
    print("🔐 Authenticating...")
    token = get_token(username, password)
    
    print("📤 Uploading edital...")
    task_id = upload_edital(token, pdf_file, {
        "ano": 2025,
        "uasg": "986531",
        "numero_pregao": "PE-001-2025",
        "callback_url": "http://localhost:3000/webhook"
    })
    
    print("⏳ Monitoring processing status...")
    status = check_status(token, task_id)
    
    if status == 'completed':
        print("✅ Processing completed successfully!")
        get_result(token, task_id)
    else:
        print("❌ Processing failed")

if __name__ == "__main__":
    main()

# =====================================================
# .env.example
"""
Environment variables example
"""
# Application
APP_NAME="Sistema de Processamento de Editais"
DEBUG=False
LOG_LEVEL=INFO

# Security
SECRET_KEY=your-secret-key-change-in-production-min-32-chars
JWT_SECRET_KEY=jwt-secret-key-change-in-production-min-32-chars

# Database
DATABASE_URL=sqlite:///./data/editais.db

# Redis
REDIS_URL=redis://redis:6379/0
REDIS_PASSWORD=

# Celery
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# Storage
STORAGE_BASE_PATH=/app/storage/editais
PROCESSED_PATH=/app/storage/processados
TEMP_PATH=/app/storage/temp

# AI
MODEL_NAME=llama3.2:3b
MODEL_MAX_TOKENS=4096
OLLAMA_HOST=http://ollama:11434

# Flower
FLOWER_PASSWORD=admin123

# Monitoring (optional)
SENTRY_DSN=

# Email (optional)
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=