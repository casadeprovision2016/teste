    # app/main.py
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import uuid
from datetime import datetime
import os
import shutil
from pathlib import Path

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.worker import process_edital_task
from app.schemas import EditalUpload, EditalStatus, EditalResult
from app.models import Edital
from app.utils.file_manager import FileManager

# Initialize FastAPI app
app = FastAPI(
    title="Sistema de Processamento de Editais",
    version="1.0.0",
    description="API para processamento assíncrono de editais com IA"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}

# Upload and process edital
@app.post("/api/v1/editais/processar", response_model=EditalStatus)
async def upload_edital(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    ano: int = None,
    uasg: str = None,
    numero_pregao: str = None,
    callback_url: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Endpoint para upload e processamento assíncrono de editais
    """
    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Apenas arquivos PDF são aceitos")
    
    # Generate task ID
    task_id = str(uuid.uuid4())
    
    try:
        # Create file manager instance
        file_manager = FileManager(settings.STORAGE_BASE_PATH)
        
        # Save file to organized structure
        file_path = file_manager.save_edital(
            file=file.file,
            filename=file.filename,
            ano=ano,
            uasg=uasg,
            numero_pregao=numero_pregao
        )
        
        # Create database entry
        edital = Edital(
            id=task_id,
            filename=file.filename,
            file_path=str(file_path),
            ano=ano,
            uasg=uasg,
            numero_pregao=numero_pregao,
            status="queued",
            user_id=current_user["id"],
            callback_url=callback_url,
            created_at=datetime.utcnow()
        )
        db.add(edital)
        db.commit()
        
        # Queue processing task
        task = process_edital_task.apply_async(
            args=[task_id, str(file_path)],
            task_id=task_id,
            kwargs={
                "ano": ano,
                "uasg": uasg,
                "numero_pregao": numero_pregao,
                "callback_url": callback_url
            }
        )
        
        return EditalStatus(
            task_id=task_id,
            status="queued",
            message="Edital adicionado à fila de processamento",
            position_in_queue=get_queue_position(task_id)
        )
        
    except Exception as e:
        # Rollback on error
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao processar upload: {str(e)}")

# Check processing status
@app.get("/api/v1/editais/status/{task_id}", response_model=EditalStatus)
async def get_edital_status(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Consulta o status do processamento de um edital
    """
    edital = db.query(Edital).filter(
        Edital.id == task_id,
        Edital.user_id == current_user["id"]
    ).first()
    
    if not edital:
        raise HTTPException(status_code=404, detail="Edital não encontrado")
    
    # Get task status from Celery
    from celery.result import AsyncResult
    result = AsyncResult(task_id)
    
    status_map = {
        "PENDING": "queued",
        "STARTED": "processing",
        "SUCCESS": "completed",
        "FAILURE": "failed",
        "RETRY": "retrying"
    }
    
    celery_status = status_map.get(result.state, result.state.lower())
    
    # Update database status if different
    if edital.status != celery_status:
        edital.status = celery_status
        db.commit()
    
    return EditalStatus(
        task_id=task_id,
        status=celery_status,
        message=get_status_message(celery_status),
        progress=get_task_progress(result),
        estimated_time=get_estimated_time(celery_status)
    )

# Get processing result
@app.get("/api/v1/editais/resultado/{task_id}", response_model=EditalResult)
async def get_edital_result(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Obtém o resultado do processamento de um edital
    """
    edital = db.query(Edital).filter(
        Edital.id == task_id,
        Edital.user_id == current_user["id"]
    ).first()
    
    if not edital:
        raise HTTPException(status_code=404, detail="Edital não encontrado")
    
    if edital.status != "completed":
        raise HTTPException(
            status_code=400, 
            detail=f"Processamento ainda não concluído. Status atual: {edital.status}"
        )
    
    # Load result from storage
    result_path = Path(settings.PROCESSED_PATH) / f"{task_id}" / "resultado.json"
    
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="Resultado não encontrado")
    
    import json
    with open(result_path, 'r', encoding='utf-8') as f:
        result_data = json.load(f)
    
    return EditalResult(
        task_id=task_id,
        filename=edital.filename,
        ano=edital.ano,
        uasg=edital.uasg,
        numero_pregao=edital.numero_pregao,
        processed_at=edital.processed_at,
        extraction_data=result_data.get("extraction_data", {}),
        products_table=result_data.get("products_table", []),
        risk_analysis=result_data.get("risk_analysis", {}),
        opportunities=result_data.get("opportunities", []),
        metadata=result_data.get("metadata", {})
    )

# List user's editais
@app.get("/api/v1/editais")
async def list_editais(
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Lista todos os editais do usuário com paginação
    """
    query = db.query(Edital).filter(Edital.user_id == current_user["id"])
    
    if status:
        query = query.filter(Edital.status == status)
    
    total = query.count()
    editais = query.offset(skip).limit(limit).all()
    
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "data": [
            {
                "task_id": e.id,
                "filename": e.filename,
                "status": e.status,
                "created_at": e.created_at,
                "processed_at": e.processed_at,
                "ano": e.ano,
                "uasg": e.uasg,
                "numero_pregao": e.numero_pregao
            }
            for e in editais
        ]
    }

# Cancel processing
@app.delete("/api/v1/editais/{task_id}/cancelar")
async def cancel_processing(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Cancela o processamento de um edital
    """
    edital = db.query(Edital).filter(
        Edital.id == task_id,
        Edital.user_id == current_user["id"]
    ).first()
    
    if not edital:
        raise HTTPException(status_code=404, detail="Edital não encontrado")
    
    if edital.status in ["completed", "failed"]:
        raise HTTPException(
            status_code=400, 
            detail=f"Não é possível cancelar. Status: {edital.status}"
        )
    
    # Cancel Celery task
    from app.worker import app as celery_app
    celery_app.control.revoke(task_id, terminate=True)
    
    # Update database
    edital.status = "cancelled"
    db.commit()
    
    return {"message": "Processamento cancelado com sucesso"}

# Retry failed processing
@app.post("/api/v1/editais/{task_id}/reprocessar")
async def retry_processing(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Reprocessa um edital que falhou
    """
    edital = db.query(Edital).filter(
        Edital.id == task_id,
        Edital.user_id == current_user["id"]
    ).first()
    
    if not edital:
        raise HTTPException(status_code=404, detail="Edital não encontrado")
    
    if edital.status not in ["failed", "cancelled"]:
        raise HTTPException(
            status_code=400,
            detail=f"Apenas editais com falha podem ser reprocessados. Status atual: {edital.status}"
        )
    
    # Reset status
    edital.status = "queued"
    edital.error_message = None
    db.commit()
    
    # Queue new task
    task = process_edital_task.apply_async(
        args=[task_id, edital.file_path],
        task_id=f"{task_id}-retry-{datetime.utcnow().timestamp()}",
        kwargs={
            "ano": edital.ano,
            "uasg": edital.uasg,
            "numero_pregao": edital.numero_pregao,
            "callback_url": edital.callback_url,
            "is_retry": True
        }
    )
    
    return {
        "message": "Edital adicionado à fila para reprocessamento",
        "new_task_id": task.id
    }

# Helper functions
def get_queue_position(task_id: str) -> int:
    """Get position in processing queue"""
    from app.worker import app as celery_app
    inspect = celery_app.control.inspect()
    active = inspect.active()
    reserved = inspect.reserved()
    
    position = 1
    for worker_tasks in list(active.values()) + list(reserved.values()):
        for task in worker_tasks:
            if task['id'] == task_id:
                return position
            position += 1
    return position

def get_status_message(status: str) -> str:
    """Get user-friendly status message"""
    messages = {
        "queued": "Aguardando processamento na fila",
        "processing": "Processamento em andamento",
        "completed": "Processamento concluído com sucesso",
        "failed": "Falha no processamento",
        "retrying": "Tentando processar novamente",
        "cancelled": "Processamento cancelado"
    }
    return messages.get(status, "Status desconhecido")

def get_task_progress(result) -> Optional[float]:
    """Get task progress percentage"""
    if hasattr(result, 'info') and isinstance(result.info, dict):
        return result.info.get('progress', 0.0)
    return None

def get_estimated_time(status: str) -> Optional[int]:
    """Get estimated time remaining in seconds"""
    if status == "queued":
        return 480  # 8 minutes average
    elif status == "processing":
        return 240  # 4 minutes remaining average
    return None

# Application startup
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    # Create directories if not exist
    for path in [settings.STORAGE_BASE_PATH, settings.PROCESSED_PATH, settings.TEMP_PATH]:
        Path(path).mkdir(parents=True, exist_ok=True)
    
    # Initialize database
    from app.core.database import engine
    from app.models import Base
    Base.metadata.create_all(bind=engine)
    
    # Download AI models if not present
    from app.services.ai_engine import AIEngine
    ai_engine = AIEngine()
    await ai_engine.initialize_models()
    
    print("✅ Application initialized successfully")

# Application shutdown
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown"""
    # Close database connections
    from app.core.database import engine
    engine.dispose()
    
    # Clear temporary files
    temp_path = Path(settings.TEMP_PATH)
    if temp_path.exists():
        shutil.rmtree(temp_path)
        temp_path.mkdir()
    
    print("👋 Application shutdown complete")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        workers=settings.WORKERS
    )