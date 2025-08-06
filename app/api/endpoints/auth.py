# app/api/endpoints/auth.py
"""
Authentication endpoints
"""
from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    get_current_user,
    generate_api_key
)
from app.models import User
from app.schemas import Token, UserCreate, UserResponse, UserUpdate

router = APIRouter(prefix="/auth", tags=["authentication"])

@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
) -> Any:
    """
    Register new user
    """
    # Check if user exists
    existing_user = db.query(User).filter(
        (User.email == user_data.email) | (User.username == user_data.username)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username already registered"
        )
    
    # Create new user
    user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        organization=user_data.organization,
        role=user_data.role,
        api_key=generate_api_key(),
        daily_quota=50
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user

@router.post("/token", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
) -> Any:
    """
    OAuth2 compatible token login
    """
    # Try to find user by email or username
    user = db.query(User).filter(
        (User.email == form_data.username) | (User.username == form_data.username)
    ).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    # Create tokens
    access_token = create_access_token(
        data={"sub": user.id, "username": user.username, "role": user.role}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str,
    db: Session = Depends(get_db)
) -> Any:
    """
    Refresh access token
    """
    try:
        payload = jwt.decode(
            refresh_token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        user_id = payload.get("sub")
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user"
            )
        
        # Create new access token
        access_token = create_access_token(
            data={"sub": user.id, "username": user.username, "role": user.role}
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
        
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Get current user information
    """
    return current_user

@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Update current user information
    """
    if user_update.full_name is not None:
        current_user.full_name = user_update.full_name
    
    if user_update.organization is not None:
        current_user.organization = user_update.organization
    
    if user_update.password is not None:
        current_user.hashed_password = get_password_hash(user_update.password)
    
    current_user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(current_user)
    
    return current_user

@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Logout user (client should discard token)
    """
    return {"message": "Successfully logged out"}

@router.get("/api-key")
async def get_api_key(
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Get user's API key
    """
    return {"api_key": current_user.api_key}

@router.post("/api-key/regenerate")
async def regenerate_api_key(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Regenerate user's API key
    """
    current_user.api_key = generate_api_key()
    db.commit()
    
    return {"api_key": current_user.api_key}

# =====================================================
# app/api/endpoints/editais.py
"""
Editais processing endpoints
"""
from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import uuid

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import User, Edital, Product, Risk, Opportunity
from app.schemas import (
    EditalUpload, EditalStatus, EditalResult, 
    EditalListResponse, SearchFilters, PaginationParams
)
from app.worker import process_edital_task
from app.utils.file_manager import FileManager

router = APIRouter(prefix="/editais", tags=["editais"])

@router.post("/processar", response_model=EditalStatus)
async def process_edital(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    ano: Optional[int] = Query(None, ge=2020, le=2030),
    uasg: Optional[str] = Query(None, max_length=20),
    numero_pregao: Optional[str] = Query(None, max_length=100),
    callback_url: Optional[str] = Query(None),
    priority: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload and process edital
    """
    # Check user quota
    if current_user.used_quota >= current_user.daily_quota:
        # Check if needs reset
        if current_user.quota_reset_at and current_user.quota_reset_at < datetime.utcnow():
            current_user.used_quota = 0
            current_user.quota_reset_at = datetime.utcnow() + timedelta(days=1)
        else:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Daily quota exceeded"
            )
    
    # Validate file
    if not file.filename.endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted"
        )
    
    # Check file size
    file_content = await file.read()
    if len(file_content) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max size: {settings.MAX_FILE_SIZE / 1024 / 1024}MB"
        )
    
    # Generate task ID
    task_id = str(uuid.uuid4())
    
    # Save file
    file_manager = FileManager(settings.STORAGE_BASE_PATH)
    file_path = file_manager.save_edital(
        content=file_content,
        filename=file.filename,
        ano=ano,
        uasg=uasg,
        numero_pregao=numero_pregao
    )
    
    # Calculate file hash for deduplication
    file_hash = hashlib.sha256(file_content).hexdigest()
    
    # Check for duplicate
    existing = db.query(Edital).filter(
        Edital.file_hash == file_hash,
        Edital.user_id == current_user.id,
        Edital.status.in_(["completed", "processing", "queued"])
    ).first()
    
    if existing:
        return EditalStatus(
            task_id=existing.id,
            status=existing.status,
            message="Duplicate file already being processed or completed",
            progress=existing.progress
        )
    
    # Create database entry
    edital = Edital(
        id=task_id,
        user_id=current_user.id,
        filename=file.filename,
        file_path=str(file_path),
        file_hash=file_hash,
        file_size=len(file_content),
        ano=ano,
        uasg=uasg,
        numero_pregao=numero_pregao,
        status="queued",
        callback_url=callback_url
    )
    
    db.add(edital)
    
    # Update user quota
    current_user.used_quota += 1
    if not current_user.quota_reset_at:
        current_user.quota_reset_at = datetime.utcnow() + timedelta(days=1)
    
    db.commit()
    
    # Queue task with priority
    task = process_edital_task.apply_async(
        args=[task_id, str(file_path)],
        task_id=task_id,
        kwargs={
            "ano": ano,
            "uasg": uasg,
            "numero_pregao": numero_pregao,
            "callback_url": callback_url
        },
        priority=9 if priority else 5  # Higher number = higher priority
    )
    
    return EditalStatus(
        task_id=task_id,
        status="queued",
        message="Edital added to processing queue",
        progress=0.0,
        position_in_queue=get_queue_position(task_id)
    )

@router.get("/{task_id}/status", response_model=EditalStatus)
async def get_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get processing status
    """
    edital = db.query(Edital).filter(
        Edital.id == task_id,
        Edital.user_id == current_user.id
    ).first()
    
    if not edital:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Edital not found"
        )
    
    # Get real-time status from Celery
    from celery.result import AsyncResult
    result = AsyncResult(task_id)
    
    # Update progress if available
    if hasattr(result, 'info') and isinstance(result.info, dict):
        progress = result.info.get('progress', edital.progress)
        message = result.info.get('message', '')
    else:
        progress = edital.progress
        message = ''
    
    return EditalStatus(
        task_id=task_id,
        status=edital.status,
        message=message or get_status_message(edital.status),
        progress=progress,
        started_at=edital.started_at,
        position_in_queue=get_queue_position(task_id) if edital.status == "queued" else None,
        estimated_time=estimate_processing_time(edital.status)
    )

@router.get("/{task_id}/resultado", response_model=EditalResult)
async def get_result(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get processing result
    """
    edital = db.query(Edital).filter(
        Edital.id == task_id,
        Edital.user_id == current_user.id
    ).first()
    
    if not edital:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Edital not found"
        )
    
    if edital.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Processing not completed. Status: {edital.status}"
        )
    
    # Load result from storage
    result_path = Path(settings.PROCESSED_PATH) / task_id / "resultado.json"
    
    if not result_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Result file not found"
        )
    
    with open(result_path, 'r', encoding='utf-8') as f:
        result_data = json.load(f)
    
    # Get products from database
    products = db.query(Product).filter(Product.edital_id == task_id).all()
    
    # Get risks
    risks = db.query(Risk).filter(Risk.edital_id == task_id).order_by(Risk.risk_score.desc()).all()
    
    # Get opportunities
    opportunities = db.query(Opportunity).filter(
        Opportunity.edital_id == task_id
    ).order_by(Opportunity.opportunity_score.desc()).all()
    
    return EditalResult(
        task_id=task_id,
        filename=edital.filename,
        ano=edital.ano,
        uasg=edital.uasg,
        numero_pregao=edital.numero_pregao,
        processed_at=edital.processed_at,
        quality_score=edital.quality_score,
        objeto=edital.objeto,
        valor_estimado=edital.valor_estimado,
        data_abertura=edital.data_abertura,
        orgao=edital.orgao,
        modalidade=edital.modalidade,
        extraction_data=result_data.get("extraction_data", {}),
        products_table=[
            {
                "item_number": p.item_number,
                "description": p.description,
                "quantity": p.quantity,
                "unit": p.unit,
                "unit_price": p.unit_price,
                "total_price": p.total_price,
                "category": p.category
            }
            for p in products
        ],
        risk_analysis={
            "total_risks": len(risks),
            "critical_risks": sum(1 for r in risks if r.severity == "critical"),
            "risks": [
                {
                    "type": r.risk_type,
                    "title": r.title,
                    "description": r.description,
                    "severity": r.severity,
                    "risk_score": r.risk_score,
                    "mitigation": r.mitigation_strategy
                }
                for r in risks[:10]  # Top 10 risks
            ]
        },
        opportunities=[
            {
                "type": o.opportunity_type,
                "title": o.title,
                "description": o.description,
                "score": o.opportunity_score,
                "priority": o.priority,
                "estimated_value": o.estimated_value
            }
            for o in opportunities[:10]  # Top 10 opportunities
        ],
        metadata=result_data.get("metadata", {})
    )

@router.get("", response_model=EditalListResponse)
async def list_editais(
    filters: SearchFilters = Depends(),
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List user's editais with filters
    """
    query = db.query(Edital).filter(Edital.user_id == current_user.id)
    
    # Apply filters
    if filters.uasg:
        query = query.filter(Edital.uasg == filters.uasg)
    
    if filters.ano:
        query = query.filter(Edital.ano == filters.ano)
    
    if filters.status:
        query = query.filter(Edital.status == filters.status)
    
    if filters.date_from:
        query = query.filter(Edital.created_at >= filters.date_from)
    
    if filters.date_to:
        query = query.filter(Edital.created_at <= filters.date_to)
    
    if filters.min_value:
        query = query.filter(Edital.valor_estimado >= filters.min_value)
    
    if filters.max_value:
        query = query.filter(Edital.valor_estimado <= filters.max_value)
    
    if filters.text_search:
        search_term = f"%{filters.text_search}%"
        query = query.filter(
            or_(
                Edital.objeto.ilike(search_term),
                Edital.orgao.ilike(search_term),
                Edital.filename.ilike(search_term)
            )
        )
    
    # Count total
    total = query.count()
    
    # Apply sorting
    if pagination.sort_order == "desc":
        query = query.order_by(getattr(Edital, pagination.sort_by).desc())
    else:
        query = query.order_by(getattr(Edital, pagination.sort_by))
    
    # Apply pagination
    editais = query.offset(pagination.skip).limit(pagination.limit).all()
    
    return EditalListResponse(
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
        data=[
            {
                "task_id": e.id,
                "filename": e.filename,
                "status": e.status,
                "created_at": e.created_at.isoformat(),
                "processed_at": e.processed_at.isoformat() if e.processed_at else None,
                "ano": e.ano,
                "uasg": e.uasg,
                "numero_pregao": e.numero_pregao,
                "objeto": e.objeto,
                "valor_estimado": e.valor_estimado,
                "quality_score": e.quality_score
            }
            for e in editais
        ]
    )

@router.delete("/{task_id}")
async def delete_edital(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete edital and its results
    """
    edital = db.query(Edital).filter(
        Edital.id == task_id,
        Edital.user_id == current_user.id
    ).first()
    
    if not edital:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Edital not found"
        )
    
    # Cancel if processing
    if edital.status in ["queued", "processing"]:
        from app.worker import app as celery_app
        celery_app.control.revoke(task_id, terminate=True)
    
    # Delete files
    file_manager = FileManager(settings.STORAGE_BASE_PATH)
    file_manager.delete_edital(edital.file_path)
    
    # Delete result files
    result_path = Path(settings.PROCESSED_PATH) / task_id
    if result_path.exists():
        import shutil
        shutil.rmtree(result_path)
    
    # Delete from database (cascade will delete related records)
    db.delete(edital)
    db.commit()
    
    return {"message": "Edital deleted successfully"}

@router.post("/{task_id}/retry")
async def retry_edital(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retry failed processing
    """
    edital = db.query(Edital).filter(
        Edital.id == task_id,
        Edital.user_id == current_user.id
    ).first()
    
    if not edital:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Edital not found"
        )
    
    if edital.status not in ["failed", "cancelled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot retry. Current status: {edital.status}"
        )
    
    # Check retry limit
    if edital.retry_count >= settings.TASK_RETRY_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Retry limit exceeded"
        )
    
    # Reset status
    edital.status = "queued"
    edital.error_message = None
    edital.retry_count += 1
    db.commit()
    
    # Queue new task
    task = process_edital_task.apply_async(
        args=[task_id, edital.file_path],
        task_id=f"{task_id}-retry-{edital.retry_count}",
        kwargs={
            "ano": edital.ano,
            "uasg": edital.uasg,
            "numero_pregao": edital.numero_pregao,
            "callback_url": edital.callback_url,
            "is_retry": True
        }
    )
    
    return {
        "message": "Processing retry initiated",
        "retry_count": edital.retry_count
    }

@router.get("/{task_id}/download")
async def download_original(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Download original PDF file
    """
    from fastapi.responses import FileResponse
    
    edital = db.query(Edital).filter(
        Edital.id == task_id,
        Edital.user_id == current_user.id
    ).first()
    
    if not edital:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Edital not found"
        )
    
    file_path = Path(edital.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    return FileResponse(
        path=file_path,
        filename=edital.filename,
        media_type="application/pdf"
    )

# Helper functions
def get_queue_position(task_id: str) -> int:
    """Get position in processing queue"""
    from app.worker import app as celery_app
    inspect = celery_app.control.inspect()
    
    position = 0
    
    # Check active tasks
    active = inspect.active()
    if active:
        for worker_tasks in active.values():
            for task in worker_tasks:
                if task['id'] == task_id:
                    return 0  # Already processing
    
    # Check reserved tasks
    reserved = inspect.reserved()
    if reserved:
        for worker_tasks in reserved.values():
            for task in worker_tasks:
                position += 1
                if task['id'] == task_id:
                    return position
    
    return position

def get_status_message(status: str) -> str:
    """Get user-friendly status message"""
    messages = {
        "queued": "Aguardando processamento",
        "processing": "Processamento em andamento",
        "completed": "Processamento concluído",
        "failed": "Falha no processamento",
        "cancelled": "Processamento cancelado",
        "retrying": "Tentando processar novamente"
    }
    return messages.get(status, "Status desconhecido")

def estimate_processing_time(status: str) -> Optional[int]:
    """Estimate remaining time in seconds"""
    if status == "queued":
        return 480  # 8 minutes average
    elif status == "processing":
        return 240  # 4 minutes remaining
    return None

# =====================================================
# app/api/endpoints/admin.py
"""
Admin endpoints
"""
from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.security import get_current_admin_user
from app.models import User, Edital, SystemMetric
from app.schemas import SystemMetrics, UserMetrics

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/metrics/system", response_model=SystemMetrics)
async def get_system_metrics(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get system-wide metrics
    """
    # Get queue metrics
    from app.worker import app as celery_app
    inspect = celery_app.control.inspect()
    
    stats = inspect.stats()
    active = inspect.active()
    reserved = inspect.reserved()
    
    queue_size = sum(len(tasks) for tasks in reserved.values()) if reserved else 0
    active_workers = len(stats) if stats else 0
    
    # Calculate processing rate (last hour)
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    processed_last_hour = db.query(Edital).filter(
        Edital.processed_at >= one_hour_ago,
        Edital.status == "completed"
    ).count()
    
    # Calculate average processing time
    avg_time_result = db.query(func.avg(Edital.processing_time)).filter(
        Edital.status == "completed",
        Edital.processed_at >= one_hour_ago
    ).scalar()
    
    avg_processing_time = avg_time_result or 0
    
    # Calculate success rate
    total_processed = db.query(Edital).filter(
        Edital.processed_at >= one_hour_ago
    ).count()
    
    success_rate = (processed_last_hour / total_processed * 100) if total_processed > 0 else 0
    
    # Get latest system metrics
    latest_metric = db.query(SystemMetric).order_by(
        SystemMetric.created_at.desc()
    ).first()
    
    return SystemMetrics(
        queue_size=queue_size,
        active_workers=active_workers,
        processing_rate=processed_last_hour,
        average_processing_time=avg_processing_time,
        success_rate=success_rate,
        cpu_usage=latest_metric.cpu_percent if latest_metric else 0,
        memory_usage=latest_metric.memory_percent if latest_metric else 0,
        disk_usage=latest_metric.disk_usage if latest_metric else 0
    )

@router.get("/metrics/users")
async def get_users_metrics(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get metrics for all users
    """
    users = db.query(User).all()
    
    metrics = []
    for user in users:
        total_processed = db.query(Edital).filter(
            Edital.user_id == user.id,
            Edital.status == "completed"
        ).count()
        
        total_in_queue = db.query(Edital).filter(
            Edital.user_id == user.id,
            Edital.status.in_(["queued", "processing"])
        ).count()
        
        total_failed = db.query(Edital).filter(
            Edital.user_id == user.id,
            Edital.status == "failed"
        ).count()
        
        avg_quality = db.query(func.avg(Edital.quality_score)).filter(
            Edital.user_id == user.id,
            Edital.status == "completed"
        ).scalar() or 0
        
        metrics.append({
            "user_id": user.id,
            "email": user.email,
            "organization": user.organization,
            "total_processed": total_processed,
            "total_in_queue": total_in_queue,
            "total_failed": total_failed,
            "average_quality_score": round(avg_quality, 2),
            "quota_used": user.used_quota,
            "quota_remaining": user.daily_quota - user.used_quota
        })
    
    return metrics

@router.get("/users")
async def list_users(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    List all users
    """
    users = db.query(User).offset(skip).limit(limit).all()
    total = db.query(User).count()
    
    return {
        "total": total,
        "data": [
            {
                "id": u.id,
                "email": u.email,
                "username": u.username,
                "full_name": u.full_name,
                "organization": u.organization,
                "role": u.role,
                "is_active": u.is_active,
                "created_at": u.created_at,
                "last_login": u.last_login
            }
            for u in users
        ]
    }

@router.put("/users/{user_id}/activate")
async def activate_user(
    user_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Activate user account
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.is_active = True
    db.commit()
    
    return {"message": "User activated successfully"}

@router.put("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Deactivate user account
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )
    
    user.is_active = False
    db.commit()
    
    return {"message": "User deactivated successfully"}

@router.put("/users/{user_id}/quota")
async def update_user_quota(
    user_id: str,
    daily_quota: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Update user's daily quota
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.daily_quota = daily_quota
    db.commit()
    
    return {"message": f"Quota updated to {daily_quota}"}

@router.post("/queue/purge")
async def purge_queue(
    current_user: User = Depends(get_current_admin_user)
):
    """
    Purge all tasks from queue
    """
    from app.worker import app as celery_app
    celery_app.control.purge()
    
    return {"message": "Queue purged successfully"}

@router.post("/cache/clear")
async def clear_cache(
    current_user: User = Depends(get_current_admin_user)
):
    """
    Clear all caches
    """
    import redis
    r = redis.from_url(settings.REDIS_URL)
    r.flushdb()
    
    # Clear file cache
    cache_dir = Path(settings.TEMP_PATH) / "cache"
    if cache_dir.exists():
        import shutil
        shutil.rmtree(cache_dir)
        cache_dir.mkdir()
    
    return {"message": "Cache cleared successfully"}

@router.get("/logs/recent")
async def get_recent_logs(
    limit: int = 100,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get recent processing logs
    """
    from app.models import ProcessingLog
    
    logs = db.query(ProcessingLog).order_by(
        ProcessingLog.created_at.desc()
    ).limit(limit).all()
    
    return [
        {
            "id": log.id,
            "edital_id": log.edital_id,
            "stage": log.stage,
            "status": log.status,
            "message": log.message,
            "duration": log.duration,
            "error_type": log.error_type,
            "created_at": log.created_at
        }
        for log in logs
    ]