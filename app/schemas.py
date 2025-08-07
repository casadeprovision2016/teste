# app/schemas.py
"""
Basic Pydantic schemas for API requests and responses
"""
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

# Edital Status Enum
class EditalStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed" 
    FAILED = "failed"

# Request Schemas
class EditalUpload(BaseModel):
    """Schema for edital file upload"""
    filename: str
    file_size: Optional[int] = None
    description: Optional[str] = None
    callback_url: Optional[str] = None

class EditalResult(BaseModel):
    """Schema for edital processing result"""
    id: int
    filename: str
    status: EditalStatus
    progress: int = 0
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool = True

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Authentication Schemas
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    email: Optional[str] = None

# API Response Schemas
class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime

class MessageResponse(BaseModel):
    message: str
    success: bool = True