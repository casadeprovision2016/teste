# app/utils/file_manager.py
"""
File management utilities
"""
import os
import shutil
from pathlib import Path
from typing import Dict, Any, Optional
import hashlib
import uuid
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class FileManager:
    """File management utilities"""
    
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"FileManager initialized with base_path: {self.base_path}")
    
    def save_edital(self, file, filename: str, ano: Optional[int] = None, 
                   uasg: Optional[str] = None, numero_pregao: Optional[str] = None) -> str:
        """Save edital file with organized structure"""
        try:
            # Create directory structure
            file_id = str(uuid.uuid4())
            
            if ano and uasg:
                save_dir = self.base_path / str(ano) / uasg
            else:
                save_dir = self.base_path / "general"
            
            save_dir.mkdir(parents=True, exist_ok=True)
            
            # Create filename
            safe_filename = self._sanitize_filename(filename)
            file_path = save_dir / f"{file_id}_{safe_filename}"
            
            # Save file
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file, buffer)
            
            logger.info(f"File saved: {file_path}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"Error saving file: {e}")
            raise
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe storage"""
        import re
        # Remove or replace unsafe characters
        safe_name = re.sub(r'[^\w\s\-\.]', '_', filename)
        return safe_name.strip()
    
    def get_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of file"""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    def cleanup_temp_files(self, older_than_hours: int = 24):
        """Clean up temporary files older than specified hours"""
        import time
        cutoff_time = time.time() - (older_than_hours * 3600)
        
        temp_dir = self.base_path / "temp"
        if not temp_dir.exists():
            return
        
        for file_path in temp_dir.iterdir():
            if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                try:
                    file_path.unlink()
                    logger.info(f"Cleaned up temp file: {file_path}")
                except Exception as e:
                    logger.error(f"Error cleaning up {file_path}: {e}")

class SystemMetrics:
    """System metrics collection"""
    
    def collect_metrics(self) -> Dict[str, Any]:
        """Collect basic system metrics"""
        import psutil
        
        return {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get system health status"""
        metrics = self.collect_metrics()
        
        status = "healthy"
        if metrics["cpu_percent"] > 90 or metrics["memory_percent"] > 90:
            status = "warning"
        if metrics["disk_usage"] > 95:
            status = "critical"
        
        return {
            "status": status,
            "metrics": metrics
        }

# Simple logging middleware
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import time

class LoggingMiddleware(BaseHTTPMiddleware):
    """Simple logging middleware"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Calculate response time
        response_time = (time.time() - start_time) * 1000
        
        # Simple logging
        logger.info(f"{request.method} {request.url.path} - {response.status_code} ({response_time:.2f}ms)")
        
        # Add response headers
        response.headers["X-Response-Time"] = f"{response_time:.2f}ms"
        
        return response