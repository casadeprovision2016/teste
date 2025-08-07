# app/models.py
"""
SQLAlchemy Models para o banco de dados SQLite
"""
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Boolean, JSON, ForeignKey, Index, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()

def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    """Modelo de usuário para autenticação"""
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    organization = Column(String(255))
    role = Column(String(50), default="user")  # user, admin, viewer
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    api_key = Column(String(255), unique=True, index=True)
    
    # Quotas and limits
    daily_quota = Column(Integer, default=50)
    used_quota = Column(Integer, default=0)
    quota_reset_at = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)
    
    # Relationships
    editais = relationship("Edital", back_populates="user", cascade="all, delete-orphan")
    api_logs = relationship("APILog", back_populates="user", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_user_email_active', 'email', 'is_active'),
    )

class Edital(Base):
    """Modelo principal de editais processados"""
    __tablename__ = "editais"
    
    id = Column(String(36), primary_key=True)  # Task ID
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    # File information
    filename = Column(String(500), nullable=False)
    file_path = Column(Text, nullable=False)
    file_hash = Column(String(64))  # SHA256 hash for deduplication
    file_size = Column(Integer)  # Size in bytes
    
    # Edital metadata
    numero_pregao = Column(String(100), index=True)
    uasg = Column(String(20), index=True)
    orgao = Column(String(500))
    ano = Column(Integer, index=True)
    modalidade = Column(String(100))
    tipo_licitacao = Column(String(100))
    
    # Processing status
    status = Column(String(50), default="queued", index=True)
    # queued, processing, completed, failed, cancelled, retrying
    progress = Column(Float, default=0.0)
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    
    # Extracted data
    objeto = Column(Text)
    valor_estimado = Column(Float)
    data_abertura = Column(DateTime)
    data_encerramento = Column(DateTime)
    
    # Results
    result_path = Column(Text)
    quality_score = Column(Float)
    total_items = Column(Integer)
    total_value = Column(Float)
    
    # Callback
    callback_url = Column(Text)
    callback_sent = Column(Boolean, default=False)
    callback_response = Column(JSON)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    started_at = Column(DateTime)
    processed_at = Column(DateTime)
    failed_at = Column(DateTime)
    
    # Processing metrics
    processing_time = Column(Float)  # Seconds
    ai_tokens_used = Column(Integer)
    
    # Relationships
    user = relationship("User", back_populates="editais")
    products = relationship("Product", back_populates="edital", cascade="all, delete-orphan")
    risks = relationship("Risk", back_populates="edital", cascade="all, delete-orphan")
    opportunities = relationship("Opportunity", back_populates="edital", cascade="all, delete-orphan")
    processing_logs = relationship("ProcessingLog", back_populates="edital", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_edital_user_status', 'user_id', 'status'),
        Index('idx_edital_uasg_ano', 'uasg', 'ano'),
        Index('idx_edital_created', 'created_at'),
        UniqueConstraint('file_hash', 'user_id', name='uq_file_hash_user'),
    )

class Product(Base):
    """Modelo para produtos extraídos dos editais"""
    __tablename__ = "products"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    edital_id = Column(String(36), ForeignKey("editais.id"), nullable=False)
    
    # Product information
    item_number = Column(String(20))
    description = Column(Text, nullable=False)
    detailed_specification = Column(Text)
    
    # Quantities and values
    quantity = Column(Float)
    unit = Column(String(50))
    unit_price = Column(Float)
    total_price = Column(Float)
    
    # Classification
    category = Column(String(200))
    catmat_code = Column(String(50))  # Brazilian material classification
    ncm_code = Column(String(20))  # Tax classification
    
    # Analysis
    complexity_score = Column(Float)  # 0-1 score
    margin_estimate = Column(Float)  # Estimated profit margin
    competition_level = Column(String(50))  # low, medium, high
    
    # Metadata
    table_source = Column(String(100))  # Which table/page it came from
    confidence_score = Column(Float)  # Extraction confidence
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    edital = relationship("Edital", back_populates="products")
    
    __table_args__ = (
        Index('idx_product_edital', 'edital_id'),
        Index('idx_product_category', 'category'),
        Index('idx_product_value', 'total_price'),
    )

class Risk(Base):
    """Modelo para riscos identificados"""
    __tablename__ = "risks"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    edital_id = Column(String(36), ForeignKey("editais.id"), nullable=False)
    
    # Risk information
    risk_type = Column(String(100))  # technical, legal, commercial, operational
    category = Column(String(200))
    title = Column(String(500))
    description = Column(Text)
    
    # Risk assessment
    probability = Column(Float)  # 0-1
    impact = Column(Float)  # 0-1
    risk_score = Column(Float)  # probability * impact
    severity = Column(String(20))  # low, medium, high, critical
    
    # Mitigation
    mitigation_strategy = Column(Text)
    mitigation_cost = Column(Float)
    
    # Source
    source_text = Column(Text)  # Text excerpt that triggered the risk
    source_section = Column(String(200))
    confidence = Column(Float)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    edital = relationship("Edital", back_populates="risks")
    
    __table_args__ = (
        Index('idx_risk_edital', 'edital_id'),
        Index('idx_risk_severity', 'severity'),
        Index('idx_risk_score', 'risk_score'),
    )

class Opportunity(Base):
    """Modelo para oportunidades identificadas"""
    __tablename__ = "opportunities"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    edital_id = Column(String(36), ForeignKey("editais.id"), nullable=False)
    
    # Opportunity information
    opportunity_type = Column(String(100))  # volume, value, strategic, recurring
    title = Column(String(500))
    description = Column(Text)
    
    # Business value
    estimated_value = Column(Float)
    profit_potential = Column(Float)
    success_probability = Column(Float)
    roi_estimate = Column(Float)  # Return on investment
    
    # Strategic information
    competitive_advantage = Column(Text)
    required_capabilities = Column(Text)
    investment_required = Column(Float)
    
    # Scoring
    opportunity_score = Column(Float)  # 0-100
    priority = Column(String(20))  # low, medium, high, critical
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)  # When the opportunity expires
    
    # Relationships
    edital = relationship("Edital", back_populates="opportunities")
    
    __table_args__ = (
        Index('idx_opportunity_edital', 'edital_id'),
        Index('idx_opportunity_score', 'opportunity_score'),
        Index('idx_opportunity_priority', 'priority'),
    )

class ProcessingLog(Base):
    """Modelo para logs detalhados de processamento"""
    __tablename__ = "processing_logs"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    edital_id = Column(String(36), ForeignKey("editais.id"), nullable=False)
    
    # Log information
    stage = Column(String(100))  # Processing stage
    status = Column(String(50))  # started, completed, failed
    message = Column(Text)
    
    # Performance metrics
    duration = Column(Float)  # Seconds
    memory_used = Column(Integer)  # MB
    cpu_percent = Column(Float)
    
    # Error handling
    error_type = Column(String(200))
    error_message = Column(Text)
    error_traceback = Column(Text)
    
    # Processing metadata
    processing_metadata = Column(JSON)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    edital = relationship("Edital", back_populates="processing_logs")
    
    __table_args__ = (
        Index('idx_processing_log_edital', 'edital_id'),
        Index('idx_processing_log_stage', 'stage'),
        Index('idx_processing_log_created', 'created_at'),
    )

class APILog(Base):
    """Modelo para logs de API"""
    __tablename__ = "api_logs"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"))
    
    # Request information
    method = Column(String(10))
    endpoint = Column(String(500))
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    
    # Request/Response
    request_body = Column(JSON)
    response_status = Column(Integer)
    response_time = Column(Float)  # Milliseconds
    
    # Error tracking
    error_message = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = relationship("User", back_populates="api_logs")
    
    __table_args__ = (
        Index('idx_api_log_user', 'user_id'),
        Index('idx_api_log_endpoint', 'endpoint'),
        Index('idx_api_log_created', 'created_at'),
    )

class SystemMetric(Base):
    """Modelo para métricas do sistema"""
    __tablename__ = "system_metrics"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    
    # Metric information
    metric_type = Column(String(100))  # queue_size, processing_rate, etc
    metric_value = Column(Float)
    metric_unit = Column(String(50))
    
    # System information
    worker_id = Column(String(100))
    queue_name = Column(String(100))
    
    # Resource usage
    cpu_percent = Column(Float)
    memory_percent = Column(Float)
    disk_usage = Column(Float)
    
    # Processing metrics
    active_tasks = Column(Integer)
    pending_tasks = Column(Integer)
    failed_tasks = Column(Integer)
    completed_tasks = Column(Integer)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    __table_args__ = (
        Index('idx_metric_type', 'metric_type'),
        Index('idx_metric_created', 'created_at'),
    )

# =====================================================
# Pydantic Schemas for API
# =====================================================

# app/schemas.py
"""
Pydantic schemas for request/response validation
"""
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"
    VIEWER = "viewer"

class ProcessingStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"

# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: Optional[str] = None
    organization: Optional[str] = None
    role: UserRole = UserRole.USER

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    organization: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)

class UserResponse(UserBase):
    id: str
    is_active: bool
    is_verified: bool
    daily_quota: int
    used_quota: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# Auth Schemas
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class TokenData(BaseModel):
    user_id: str
    username: str
    role: str

# Edital Schemas
class EditalUpload(BaseModel):
    ano: Optional[int] = Field(None, ge=2020, le=2030)
    uasg: Optional[str] = Field(None, max_length=20)
    numero_pregao: Optional[str] = Field(None, max_length=100)
    callback_url: Optional[str] = None
    priority: bool = False

class EditalStatus(BaseModel):
    task_id: str
    status: ProcessingStatus
    message: str
    progress: Optional[float] = Field(None, ge=0, le=100)
    position_in_queue: Optional[int] = None
    estimated_time: Optional[int] = None  # Seconds
    started_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

class EditalResult(BaseModel):
    task_id: str
    filename: str
    ano: Optional[int]
    uasg: Optional[str]
    numero_pregao: Optional[str]
    processed_at: datetime
    quality_score: float
    
    # Extracted data
    objeto: Optional[str]
    valor_estimado: Optional[float]
    data_abertura: Optional[datetime]
    orgao: Optional[str]
    modalidade: Optional[str]
    
    # Results
    extraction_data: Dict[str, Any]
    products_table: List[Dict[str, Any]]
    risk_analysis: Dict[str, Any]
    opportunities: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    
    model_config = ConfigDict(from_attributes=True)

class EditalListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    data: List[Dict[str, Any]]

# Product Schemas
class ProductBase(BaseModel):
    item_number: Optional[str]
    description: str
    quantity: Optional[float]
    unit: Optional[str]
    unit_price: Optional[float]
    total_price: Optional[float]

class ProductExtracted(ProductBase):
    detailed_specification: Optional[str]
    category: Optional[str]
    confidence_score: float

class ProductAnalysis(ProductExtracted):
    complexity_score: Optional[float]
    margin_estimate: Optional[float]
    competition_level: Optional[str]

# Risk Schemas
class RiskBase(BaseModel):
    risk_type: str
    category: str
    title: str
    description: str

class RiskAssessment(RiskBase):
    probability: float = Field(..., ge=0, le=1)
    impact: float = Field(..., ge=0, le=1)
    risk_score: float = Field(..., ge=0, le=1)
    severity: str
    mitigation_strategy: Optional[str]
    confidence: float = Field(..., ge=0, le=1)

# Opportunity Schemas
class OpportunityBase(BaseModel):
    opportunity_type: str
    title: str
    description: str

class OpportunityAnalysis(OpportunityBase):
    estimated_value: Optional[float]
    profit_potential: Optional[float]
    success_probability: float = Field(..., ge=0, le=1)
    opportunity_score: float = Field(..., ge=0, le=100)
    priority: str
    competitive_advantage: Optional[str]

# Callback Schemas
class CallbackRequest(BaseModel):
    task_id: str
    status: ProcessingStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: datetime

# Metrics Schemas
class SystemMetrics(BaseModel):
    queue_size: int
    active_workers: int
    processing_rate: float  # editais/hour
    average_processing_time: float  # seconds
    success_rate: float  # percentage
    cpu_usage: float
    memory_usage: float
    disk_usage: float

class UserMetrics(BaseModel):
    total_processed: int
    total_in_queue: int
    total_failed: int
    average_quality_score: float
    quota_used: int
    quota_remaining: int

# Search/Filter Schemas
class SearchFilters(BaseModel):
    uasg: Optional[str] = None
    ano: Optional[int] = None
    status: Optional[ProcessingStatus] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    text_search: Optional[str] = None

class PaginationParams(BaseModel):
    skip: int = Field(0, ge=0)
    limit: int = Field(50, ge=1, le=100)
    sort_by: str = "created_at"
    sort_order: str = Field("desc", pattern="^(asc|desc)$")

# Webhook Configuration
class WebhookConfig(BaseModel):
    url: str
    events: List[str] = ["completed", "failed"]
    headers: Optional[Dict[str, str]] = None
    retry_count: int = Field(3, ge=0, le=10)
    timeout: int = Field(30, ge=5, le=120)

# Export Schemas
class ExportRequest(BaseModel):
    task_ids: List[str]
    format: str = Field("json", pattern="^(json|csv|excel)$")
    include_products: bool = True
    include_risks: bool = True
    include_opportunities: bool = True