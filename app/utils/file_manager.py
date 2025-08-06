# app/utils/file_manager.py
"""
File management utilities
"""
from pathlib import Path
from typing import Optional, Dict, Any, Union
import shutil
import hashlib
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class FileManager:
    """Gerenciador de arquivos do sistema"""
    
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        
    def save_edital(self, 
                   content: Union[bytes, Any],
                   filename: str,
                   ano: Optional[int] = None,
                   uasg: Optional[str] = None,
                   numero_pregao: Optional[str] = None) -> Path:
        """
        Salva edital na estrutura organizada
        {BASE}/{ANO}/{UASG}/{NUMERO_PREGAO}/{filename}
        """
        # Default values
        ano = ano or datetime.now().year
        uasg = uasg or "sem_uasg"
        numero_pregao = numero_pregao or f"sem_numero_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Create directory structure
        file_dir = self.base_path / str(ano) / str(uasg) / str(numero_pregao)
        file_dir.mkdir(parents=True, exist_ok=True)
        
        # Save file
        file_path = file_dir / filename
        
        if isinstance(content, bytes):
            with open(file_path, 'wb') as f:
                f.write(content)
        else:
            # If content is a file object
            with open(file_path, 'wb') as f:
                shutil.copyfileobj(content, f)
        
        logger.info(f"File saved: {file_path}")
        return file_path
    
    def get_edital_path(self,
                       ano: int,
                       uasg: str,
                       numero_pregao: str,
                       filename: str) -> Optional[Path]:
        """Get path to edital file"""
        file_path = self.base_path / str(ano) / str(uasg) / str(numero_pregao) / filename
        
        if file_path.exists():
            return file_path
        return None
    
    def delete_edital(self, file_path: Union[str, Path]) -> bool:
        """Delete edital file and empty parent directories"""
        file_path = Path(file_path)
        
        if not file_path.exists():
            return False
        
        # Delete file
        file_path.unlink()
        
        # Clean up empty directories
        parent = file_path.parent
        while parent != self.base_path:
            try:
                if not any(parent.iterdir()):
                    parent.rmdir()
                    parent = parent.parent
                else:
                    break
            except:
                break
        
        return True
    
    def move_edital(self,
                   source_path: Union[str, Path],
                   ano: int,
                   uasg: str,
                   numero_pregao: str) -> Path:
        """Move edital to organized structure"""
        source_path = Path(source_path)
        
        if not source_path.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")
        
        # Create destination
        dest_dir = self.base_path / str(ano) / str(uasg) / str(numero_pregao)
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        dest_path = dest_dir / source_path.name
        
        # Move file
        shutil.move(str(source_path), str(dest_path))
        
        return dest_path
    
    def get_file_hash(self, file_path: Union[str, Path]) -> str:
        """Calculate SHA256 hash of file"""
        file_path = Path(file_path)
        
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        
        return sha256_hash.hexdigest()
    
    def get_directory_size(self, directory: Union[str, Path]) -> int:
        """Get total size of directory in bytes"""
        directory = Path(directory)
        
        total_size = 0
        for file_path in directory.rglob('*'):
            if file_path.is_file():
                total_size += file_path.stat().st_size
        
        return total_size
    
    def cleanup_old_files(self, days: int = 30) -> int:
        """Remove files older than specified days"""
        from datetime import timedelta
        
        cutoff_time = datetime.now() - timedelta(days=days)
        deleted_count = 0
        
        for file_path in self.base_path.rglob('*.pdf'):
            if file_path.is_file():
                file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                
                if file_time < cutoff_time:
                    file_path.unlink()
                    deleted_count += 1
        
        return deleted_count

# =====================================================
# app/utils/callback_handler.py
"""
Webhook callback handler
"""
import aiohttp
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import json

from app.core.config import settings

logger = logging.getLogger(__name__)

class CallbackHandler:
    """Handler para callbacks/webhooks"""
    
    def __init__(self):
        self.timeout = settings.WEBHOOK_TIMEOUT
        self.retry_count = settings.WEBHOOK_RETRY_COUNT
        self.retry_delay = settings.WEBHOOK_RETRY_DELAY
        
    async def send_callback(self,
                           url: str,
                           data: Dict[str, Any],
                           headers: Optional[Dict[str, str]] = None) -> bool:
        """
        Send callback to webhook URL with retry logic
        """
        headers = headers or {}
        headers['Content-Type'] = 'application/json'
        
        for attempt in range(self.retry_count):
            try:
                logger.info(f"Sending callback to {url} (attempt {attempt + 1})")
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url,
                        json=data,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=self.timeout)
                    ) as response:
                        if response.status == 200:
                            logger.info(f"Callback successful: {url}")
                            return True
                        else:
                            logger.warning(
                                f"Callback failed with status {response.status}: {url}"
                            )
                            
            except aiohttp.ClientError as e:
                logger.error(f"Callback error: {str(e)}")
            except Exception as e:
                logger.error(f"Unexpected callback error: {str(e)}")
            
            # Wait before retry
            if attempt < self.retry_count - 1:
                await asyncio.sleep(self.retry_delay * (attempt + 1))
        
        logger.error(f"Callback failed after {self.retry_count} attempts: {url}")
        return False
    
    def prepare_callback_data(self,
                             task_id: str,
                             status: str,
                             result: Optional[Dict] = None,
                             error: Optional[str] = None) -> Dict[str, Any]:
        """
        Prepare callback data payload
        """
        data = {
            "task_id": task_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "webhook_version": "1.0"
        }
        
        if result:
            data["result"] = {
                "quality_score": result.get("quality_score"),
                "total_items": result.get("total_items"),
                "total_value": result.get("total_value"),
                "risks_count": len(result.get("risks", [])),
                "opportunities_count": len(result.get("opportunities", [])),
                "processing_time": result.get("processing_time")
            }
            
        if error:
            data["error"] = {
                "message": error,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        return data

# =====================================================
# app/utils/monitoring.py
"""
System monitoring utilities
"""
import psutil
import logging
from datetime import datetime
from typing import Dict, Any
import asyncio

from app.core.database import SessionLocal
from app.models import SystemMetric

logger = logging.getLogger(__name__)

class SystemMonitor:
    """Monitor system resources and performance"""
    
    def __init__(self):
        self.monitoring = False
        
    async def start_monitoring(self, interval: int = 60):
        """Start monitoring loop"""
        self.monitoring = True
        
        while self.monitoring:
            try:
                metrics = self.collect_metrics()
                self.save_metrics(metrics)
            except Exception as e:
                logger.error(f"Monitoring error: {str(e)}")
            
            await asyncio.sleep(interval)
    
    def stop_monitoring(self):
        """Stop monitoring loop"""
        self.monitoring = False
    
    def collect_metrics(self) -> Dict[str, Any]:
        """Collect system metrics"""
        metrics = {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent,
            "network_io": psutil.net_io_counters()._asdict() if psutil.net_io_counters() else {},
            "process_count": len(psutil.pids()),
            "timestamp": datetime.utcnow()
        }
        
        # Get Celery metrics
        try:
            from app.worker import app as celery_app
            inspect = celery_app.control.inspect()
            
            active = inspect.active()
            reserved = inspect.reserved()
            
            metrics["active_tasks"] = sum(len(tasks) for tasks in active.values()) if active else 0
            metrics["pending_tasks"] = sum(len(tasks) for tasks in reserved.values()) if reserved else 0
            
        except Exception as e:
            logger.error(f"Error collecting Celery metrics: {str(e)}")
            metrics["active_tasks"] = 0
            metrics["pending_tasks"] = 0
        
        return metrics
    
    def save_metrics(self, metrics: Dict[str, Any]):
        """Save metrics to database"""
        db = SessionLocal()
        
        try:
            metric = SystemMetric(
                metric_type="system_snapshot",
                metric_value=metrics["cpu_percent"],
                metric_unit="percent",
                cpu_percent=metrics["cpu_percent"],
                memory_percent=metrics["memory_percent"],
                disk_usage=metrics["disk_usage"],
                active_tasks=metrics["active_tasks"],
                pending_tasks=metrics["pending_tasks"],
                created_at=metrics["timestamp"]
            )
            
            db.add(metric)
            db.commit()
            
        except Exception as e:
            logger.error(f"Error saving metrics: {str(e)}")
            db.rollback()
        finally:
            db.close()
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get system health status"""
        metrics = self.collect_metrics()
        
        # Define health thresholds
        health_status = {
            "healthy": True,
            "warnings": [],
            "metrics": metrics
        }
        
        # Check CPU
        if metrics["cpu_percent"] > 80:
            health_status["warnings"].append(f"High CPU usage: {metrics['cpu_percent']}%")
            health_status["healthy"] = False
        
        # Check Memory
        if metrics["memory_percent"] > 85:
            health_status["warnings"].append(f"High memory usage: {metrics['memory_percent']}%")
            health_status["healthy"] = False
        
        # Check Disk
        if metrics["disk_usage"] > 90:
            health_status["warnings"].append(f"Low disk space: {metrics['disk_usage']}% used")
            health_status["healthy"] = False
        
        # Check task queue
        if metrics["pending_tasks"] > 50:
            health_status["warnings"].append(f"Large task queue: {metrics['pending_tasks']} pending")
        
        return health_status

# =====================================================
# app/utils/validators.py
"""
Input validation utilities
"""
import re
from typing import Optional
from datetime import datetime

def validate_uasg(uasg: str) -> bool:
    """Validate UASG code format"""
    if not uasg:
        return True  # Optional field
    
    # UASG should be numeric with 6 digits
    pattern = r'^\d{6}$'
    return bool(re.match(pattern, uasg))

def validate_pregao_number(numero: str) -> bool:
    """Validate pregao number format"""
    if not numero:
        return True  # Optional field
    
    # Common formats: PE-001-2025, 001/2025, etc
    patterns = [
        r'^PE-\d{3}-\d{4}$',
        r'^\d{3}/\d{4}$',
        r'^\d{6}/\d{4}$'
    ]
    
    return any(re.match(pattern, numero) for pattern in patterns)

def validate_year(ano: int) -> bool:
    """Validate year range"""
    current_year = datetime.now().year
    return 2020 <= ano <= current_year + 1

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage"""
    # Remove path components
    filename = filename.split('/')[-1].split('\\')[-1]
    
    # Remove special characters
    filename = re.sub(r'[^\w\s.-]', '_', filename)
    
    # Limit length
    name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
    if len(name) > 100:
        name = name[:100]
    
    return f"{name}.{ext}" if ext else name

def validate_cpf_cnpj(document: str) -> bool:
    """Validate CPF or CNPJ format"""
    # Remove non-numeric characters
    document = re.sub(r'\D', '', document)
    
    if len(document) == 11:
        # CPF validation
        return validate_cpf(document)
    elif len(document) == 14:
        # CNPJ validation
        return validate_cnpj(document)
    
    return False

def validate_cpf(cpf: str) -> bool:
    """Validate CPF number"""
    if len(cpf) != 11:
        return False
    
    # Check for known invalid patterns
    if cpf in ['00000000000', '11111111111', '22222222222', '33333333333',
               '44444444444', '55555555555', '66666666666', '77777777777',
               '88888888888', '99999999999']:
        return False
    
    # Validate check digits
    for i in range(9, 11):
        value = sum((int(cpf[num]) * ((i+1) - num) for num in range(0, i)))
        digit = ((value * 10) % 11) % 10
        if digit != int(cpf[i]):
            return False
    
    return True

def validate_cnpj(cnpj: str) -> bool:
    """Validate CNPJ number"""
    if len(cnpj) != 14:
        return False
    
    # Validate check digits
    def calculate_digit(cnpj, digit):
        if digit == 1:
            multipliers = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        else:
            multipliers = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        
        total = sum(int(cnpj[i]) * multipliers[i] for i in range(len(multipliers)))
        remainder = total % 11
        
        return '0' if remainder < 2 else str(11 - remainder)
    
    return (calculate_digit(cnpj, 1) == cnpj[12] and 
            calculate_digit(cnpj, 2) == cnpj[13])

# =====================================================
# app/utils/audit.py
"""
Audit logging utilities
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models import ProcessingLog, APILog

logger = logging.getLogger(__name__)

class AuditLogger:
    """Audit trail logger"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def log_processing(self,
                      edital_id: str,
                      stage: str,
                      status: str,
                      message: str,
                      duration: Optional[float] = None,
                      metadata: Optional[Dict] = None):
        """Log processing event"""
        try:
            log = ProcessingLog(
                edital_id=edital_id,
                stage=stage,
                status=status,
                message=message,
                duration=duration,
                metadata=metadata or {},
                created_at=datetime.utcnow()
            )
            
            self.db.add(log)
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to log processing event: {str(e)}")
            self.db.rollback()
    
    def log_api_request(self,
                       user_id: Optional[str],
                       method: str,
                       endpoint: str,
                       ip_address: str,
                       user_agent: str,
                       request_body: Optional[Dict] = None,
                       response_status: int = 200,
                       response_time: float = 0,
                       error_message: Optional[str] = None):
        """Log API request"""
        try:
            log = APILog(
                user_id=user_id,
                method=method,
                endpoint=endpoint,
                ip_address=ip_address,
                user_agent=user_agent,
                request_body=request_body,
                response_status=response_status,
                response_time=response_time,
                error_message=error_message,
                created_at=datetime.utcnow()
            )
            
            self.db.add(log)
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to log API request: {str(e)}")
            self.db.rollback()
    
    def log_error(self,
                 edital_id: str,
                 stage: str,
                 error_type: str,
                 error_message: str,
                 error_traceback: Optional[str] = None):
        """Log processing error"""
        try:
            log = ProcessingLog(
                edital_id=edital_id,
                stage=stage,
                status="failed",
                message=f"Error in {stage}",
                error_type=error_type,
                error_message=error_message,
                error_traceback=error_traceback,
                created_at=datetime.utcnow()
            )
            
            self.db.add(log)
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to log error: {str(e)}")
            self.db.rollback()

# =====================================================
# app/middleware/logging.py
"""
Request/Response logging middleware
"""
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import time
import logging

from app.core.database import SessionLocal
from app.utils.audit import AuditLogger

logger = logging.getLogger(__name__)

class LoggingMiddleware(BaseHTTPMiddleware):
    """Log all API requests and responses"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Get request info
        ip_address = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "")
        
        # Get user ID from token if authenticated
        user_id = None
        if hasattr(request.state, "user"):
            user_id = request.state.user.id
        
        # Process request
        response = await call_next(request)
        
        # Calculate response time
        response_time = (time.time() - start_time) * 1000  # milliseconds
        
        # Log to database
        db = SessionLocal()
        audit = AuditLogger(db)
        
        try:
            audit.log_api_request(
                user_id=user_id,
                method=request.method,
                endpoint=str(request.url.path),
                ip_address=ip_address,
                user_agent=user_agent,
                response_status=response.status_code,
                response_time=response_time
            )
        finally:
            db.close()
        
        # Add response headers
        response.headers["X-Response-Time"] = f"{response_time:.2f}ms"
        
        return response

# =====================================================
# app/middleware/rate_limit.py
"""
Rate limiting middleware
"""
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
import time
from collections import defaultdict
from typing import Dict, Tuple

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware"""
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, list] = defaultdict(list)
    
    async def dispatch(self, request: Request, call_next):
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Skip rate limiting for health checks
        if request.url.path == "/health":
            return await call_next(request)
        
        # Clean old requests
        current_time = time.time()
        self.requests[client_ip] = [
            req_time for req_time in self.requests[client_ip]
            if current_time - req_time < 60
        ]
        
        # Check rate limit
        if len(self.requests[client_ip]) >= self.requests_per_minute:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded"
            )
        
        # Add current request
        self.requests[client_ip].append(current_time)
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(
            self.requests_per_minute - len(self.requests[client_ip])
        )
        
        return response