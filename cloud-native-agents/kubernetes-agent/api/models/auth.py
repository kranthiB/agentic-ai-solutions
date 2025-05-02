# api/models/auth.py
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime

class Token(BaseModel):
    """JWT token response model"""
    access_token: str
    token_type: str

class TokenData(BaseModel):
    """Token payload data"""
    sub: str
    username: str
    is_admin: bool = False
    exp: datetime

class UserBase(BaseModel):
    """Base user properties"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    """Properties required to create a user"""
    password: str = Field(..., min_length=8)

class UserResponse(UserBase):
    """User data returned to clients"""
    id: str
    is_admin: bool = False
    created_at: datetime