# app/utils/callback_handler.py
"""
Basic callback handler for task processing
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class CallbackHandler:
    """Basic callback handler for processing updates"""
    
    def __init__(self, callback_url: Optional[str] = None):
        self.callback_url = callback_url
        self.callbacks = []
        logger.info("Callback handler initialized")
    
    def add_callback(self, callback_func):
        """Add a callback function"""
        self.callbacks.append(callback_func)
    
    def notify_progress(self, task_id: str, status: str, progress: int = 0, 
                       message: str = "", data: Dict[str, Any] = None):
        """Notify progress update"""
        try:
            update = {
                "task_id": task_id,
                "status": status,
                "progress": progress,
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
                "data": data or {}
            }
            
            logger.info(f"Progress update for {task_id}: {status} ({progress}%)")
            
            # Call all registered callbacks
            for callback in self.callbacks:
                try:
                    callback(update)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
                    
        except Exception as e:
            logger.error(f"Error in progress notification: {e}")
    
    def notify_completion(self, task_id: str, success: bool, result: Dict[str, Any] = None,
                         error: str = None):
        """Notify task completion"""
        try:
            status = "completed" if success else "failed"
            update = {
                "task_id": task_id,
                "status": status,
                "progress": 100 if success else 0,
                "message": error if error else "Task completed successfully",
                "timestamp": datetime.utcnow().isoformat(),
                "result": result,
                "error": error
            }
            
            logger.info(f"Task {task_id} {status}")
            
            # Call all registered callbacks
            for callback in self.callbacks:
                try:
                    callback(update)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
                    
        except Exception as e:
            logger.error(f"Error in completion notification: {e}")