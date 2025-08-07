# app/utils/audit.py
"""
Basic audit logging for system events
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)

class AuditEventType(str, Enum):
    """Audit event types"""
    FILE_UPLOAD = "file_upload"
    FILE_PROCESS = "file_process" 
    USER_ACTION = "user_action"
    SYSTEM_EVENT = "system_event"
    ERROR_EVENT = "error_event"
    SECURITY_EVENT = "security_event"

class AuditLogger:
    """Basic audit logger"""
    
    def __init__(self):
        self.logger = logging.getLogger("audit")
        
    def log_event(
        self,
        event_type: AuditEventType,
        message: str,
        user_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log an audit event"""
        try:
            event_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "event_type": event_type,
                "message": message,
                "user_id": user_id,
                "resource_id": resource_id,
                "metadata": metadata or {}
            }
            
            self.logger.info(f"AUDIT: {event_data}")
            
        except Exception as e:
            logger.error(f"Error logging audit event: {e}")
    
    def log_file_upload(self, filename: str, user_id: str, file_size: int):
        """Log file upload event"""
        self.log_event(
            AuditEventType.FILE_UPLOAD,
            f"File uploaded: {filename}",
            user_id=user_id,
            metadata={"filename": filename, "size": file_size}
        )
    
    def log_file_process(self, task_id: str, filename: str, status: str):
        """Log file processing event"""
        self.log_event(
            AuditEventType.FILE_PROCESS,
            f"File processing {status}: {filename}",
            resource_id=task_id,
            metadata={"filename": filename, "status": status}
        )
    
    def log_user_action(self, action: str, user_id: str, details: Dict[str, Any] = None):
        """Log user action"""
        self.log_event(
            AuditEventType.USER_ACTION,
            f"User action: {action}",
            user_id=user_id,
            metadata=details
        )
    
    def log_error(self, error_message: str, context: Dict[str, Any] = None):
        """Log error event"""
        self.log_event(
            AuditEventType.ERROR_EVENT,
            f"Error: {error_message}",
            metadata=context
        )

# Global audit logger instance
audit_logger = AuditLogger()