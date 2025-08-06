# app/worker.py
from celery import Celery, Task
from celery.signals import task_prerun, task_postrun, task_failure
import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import traceback

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.pdf_processor import PDFProcessor
from app.services.ai_engine import AIEngine
from app.services.table_extractor import TableExtractor
from app.services.risk_analyzer import RiskAnalyzer
from app.utils.callback_handler import CallbackHandler
from app.models import Edital

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Celery
app = Celery(
    'edital_processor',
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

# Celery configuration
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='America/Sao_Paulo',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=1800,  # 30 minutes max per task
    task_soft_time_limit=1500,  # 25 minutes soft limit
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=10,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=60,
    task_max_retries=3,
    result_expires=86400,  # Results expire after 24 hours
)

# Initialize services
pdf_processor = PDFProcessor()
ai_engine = AIEngine()
table_extractor = TableExtractor()
risk_analyzer = RiskAnalyzer()
callback_handler = CallbackHandler()

class ProcessEditalTask(Task):
    """Custom task class with progress tracking"""
    
    def __init__(self):
        self.current_progress = 0
    
    def update_progress(self, progress: float, message: str = ""):
        """Update task progress"""
        self.update_state(
            state='PROGRESS',
            meta={
                'progress': progress,
                'message': message,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        self.current_progress = progress
        logger.info(f"Progress: {progress}% - {message}")

@app.task(bind=True, base=ProcessEditalTask, name='process_edital')
def process_edital_task(
    self,
    task_id: str,
    file_path: str,
    ano: Optional[int] = None,
    uasg: Optional[str] = None,
    numero_pregao: Optional[str] = None,
    callback_url: Optional[str] = None,
    is_retry: bool = False
) -> Dict[str, Any]:
    """
    Main task for processing editais
    """
    logger.info(f"Starting processing for task {task_id}")
    db = SessionLocal()
    
    try:
        # Update task status in database
        edital = db.query(Edital).filter(Edital.id == task_id).first()
        if edital:
            edital.status = "processing"
            edital.started_at = datetime.utcnow()
            db.commit()
        
        # Step 1: Extract text from PDF (10%)
        self.update_progress(10, "Extraindo texto do PDF...")
        pdf_content = pdf_processor.extract_text(file_path)
        pdf_metadata = pdf_processor.extract_metadata(file_path)
        
        # Step 2: Extract tables (20%)
        self.update_progress(20, "Identificando e extraindo tabelas...")
        tables = table_extractor.extract_tables(file_path)
        
        # Step 3: Identify product tables (30%)
        self.update_progress(30, "Analisando tabelas de produtos...")
        product_tables = table_extractor.identify_product_tables(tables)
        
        # Step 4: Process with AI - Document understanding (50%)
        self.update_progress(50, "Processando documento com IA...")
        ai_analysis = ai_engine.analyze_document(
            text=pdf_content,
            tables=product_tables,
            metadata={
                "ano": ano,
                "uasg": uasg,
                "numero_pregao": numero_pregao,
                **pdf_metadata
            }
        )
        
        # Step 5: Extract structured data (60%)
        self.update_progress(60, "Extraindo dados estruturados...")
        structured_data = ai_engine.extract_structured_data(
            text=pdf_content,
            ai_analysis=ai_analysis
        )
        
        # Step 6: Risk analysis (70%)
        self.update_progress(70, "Analisando riscos e oportunidades...")
        risk_analysis = risk_analyzer.analyze(
            document_text=pdf_content,
            structured_data=structured_data,
            tables=product_tables
        )
        
        # Step 7: Identify opportunities (80%)
        self.update_progress(80, "Identificando oportunidades de negócio...")
        opportunities = risk_analyzer.identify_opportunities(
            structured_data=structured_data,
            risk_analysis=risk_analysis
        )
        
        # Step 8: Generate final report (90%)
        self.update_progress(90, "Gerando relatório final...")
        result = {
            "task_id": task_id,
            "filename": Path(file_path).name,
            "processed_at": datetime.utcnow().isoformat(),
            "metadata": {
                "ano": ano,
                "uasg": uasg,
                "numero_pregao": numero_pregao,
                "pdf_pages": pdf_metadata.get("pages", 0),
                "pdf_size": pdf_metadata.get("size", 0),
                "processing_time": (datetime.utcnow() - edital.started_at).total_seconds() if edital else 0
            },
            "extraction_data": structured_data,
            "products_table": format_product_tables(product_tables),
            "risk_analysis": risk_analysis,
            "opportunities": opportunities,
            "ai_insights": ai_analysis.get("insights", {}),
            "quality_score": calculate_quality_score(structured_data, product_tables)
        }
        
        # Step 9: Save results (95%)
        self.update_progress(95, "Salvando resultados...")
        save_results(task_id, result)
        
        # Step 10: Update database and send callback (100%)
        self.update_progress(100, "Finalizando processamento...")
        if edital:
            edital.status = "completed"
            edital.processed_at = datetime.utcnow()
            edital.result_path = f"{settings.PROCESSED_PATH}/{task_id}/resultado.json"
            db.commit()
        
        # Send callback if configured
        if callback_url:
            callback_handler.send_callback(
                url=callback_url,
                data={
                    "task_id": task_id,
                    "status": "completed",
                    "result": result
                }
            )
        
        logger.info(f"Processing completed successfully for task {task_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error processing task {task_id}: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Update database with error
        if edital:
            edital.status = "failed"
            edital.error_message = str(e)
            edital.failed_at = datetime.utcnow()
            db.commit()
        
        # Send error callback
        if callback_url:
            callback_handler.send_callback(
                url=callback_url,
                data={
                    "task_id": task_id,
                    "status": "failed",
                    "error": str(e)
                }
            )
        
        # Retry if not already a retry
        if not is_retry and self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
        
        raise
        
    finally:
        db.close()

@app.task(name='cleanup_old_results')
def cleanup_old_results():
    """
    Periodic task to clean up old processing results
    """
    from datetime import timedelta
    cutoff_date = datetime.utcnow() - timedelta(days=30)
    
    processed_path = Path(settings.PROCESSED_PATH)
    cleaned_count = 0
    
    for task_dir in processed_path.iterdir():
        if task_dir.is_dir():
            result_file = task_dir / "resultado.json"
            if result_file.exists():
                # Check file modification time
                mtime = datetime.fromtimestamp(result_file.stat().st_mtime)
                if mtime < cutoff_date:
                    import shutil
                    shutil.rmtree(task_dir)
                    cleaned_count += 1
    
    logger.info(f"Cleaned up {cleaned_count} old results")
    return cleaned_count

@app.task(name='health_check')
def health_check():
    """
    Health check task for monitoring
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "workers": app.control.inspect().active_queues()
    }

# Helper functions
def format_product_tables(tables: List[Dict]) -> List[Dict]:
    """Format product tables for output"""
    formatted_tables = []
    
    for table in tables:
        formatted_table = {
            "table_id": table.get("id"),
            "headers": table.get("headers", []),
            "rows": []
        }
        
        for row in table.get("data", []):
            formatted_row = {
                "item": row.get("item", ""),
                "description": row.get("description", ""),
                "quantity": row.get("quantity", 0),
                "unit": row.get("unit", ""),
                "unit_price": row.get("unit_price", 0),
                "total_price": row.get("total_price", 0),
                "specifications": row.get("specifications", {})
            }
            formatted_table["rows"].append(formatted_row)
        
        formatted_tables.append(formatted_table)
    
    return formatted_tables

def calculate_quality_score(structured_data: Dict, tables: List) -> float:
    """Calculate quality score for extraction"""
    score = 0.0
    weights = {
        "has_object": 0.2,
        "has_value": 0.2,
        "has_dates": 0.15,
        "has_tables": 0.25,
        "has_items": 0.2
    }
    
    if structured_data.get("object"):
        score += weights["has_object"]
    
    if structured_data.get("estimated_value"):
        score += weights["has_value"]
    
    if structured_data.get("dates", {}).get("opening_date"):
        score += weights["has_dates"]
    
    if tables and len(tables) > 0:
        score += weights["has_tables"]
    
    if any(table.get("data") for table in tables):
        score += weights["has_items"]
    
    return round(score * 100, 2)

def save_results(task_id: str, result: Dict):
    """Save processing results to filesystem"""
    result_dir = Path(settings.PROCESSED_PATH) / task_id
    result_dir.mkdir(parents=True, exist_ok=True)
    
    result_file = result_dir / "resultado.json"
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    # Save summary for quick access
    summary_file = result_dir / "summary.json"
    summary = {
        "task_id": task_id,
        "processed_at": result["processed_at"],
        "quality_score": result["quality_score"],
        "total_items": sum(len(t.get("rows", [])) for t in result["products_table"]),
        "total_value": sum(
            row.get("total_price", 0) 
            for table in result["products_table"] 
            for row in table.get("rows", [])
        ),
        "risks_count": len(result["risk_analysis"].get("risks", [])),
        "opportunities_count": len(result["opportunities"])
    }
    
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

# Celery beat schedule for periodic tasks
app.conf.beat_schedule = {
    'cleanup-old-results': {
        'task': 'cleanup_old_results',
        'schedule': 86400.0,  # Run daily
    },
    'health-check': {
        'task': 'health_check',
        'schedule': 60.0,  # Run every minute
    },
}

# Signal handlers for monitoring
@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, **kwargs):
    """Log task start"""
    logger.info(f"Task {task.name}[{task_id}] starting")

@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, state=None, **kwargs):
    """Log task completion"""
    logger.info(f"Task {task.name}[{task_id}] completed with state: {state}")

@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, **kwargs):
    """Log task failure"""
    logger.error(f"Task {sender.name}[{task_id}] failed: {exception}")