"""
CronoPlan API - Auth Schemas
Modelos Pydantic para validación de requests/responses
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


# =====================================================
# REQUEST SCHEMAS
# =====================================================

class RegisterRequest(BaseModel):
    """Schema para registro de usuario"""
    email: EmailStr = Field(..., description="Email del usuario")
    password: str = Field(..., min_length=6, description="Contraseña (mínimo 6 caracteres)")
    full_name: Optional[str] = Field(None, description="Nombre completo del usuario")
    phone: Optional[str] = Field(None, description="Número de teléfono del usuario")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "usuario@ejemplo.com",
                "password": "miPassword123",
                "full_name": "Juan Pérez",
                "phone": "+504 9999-9999"
            }
        }


class LoginRequest(BaseModel):
    """Schema para login de usuario"""
    email: EmailStr = Field(..., description="Email del usuario")
    password: str = Field(..., description="Contraseña")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "usuario@ejemplo.com",
                "password": "miPassword123"
            }
        }


class UpdateProfileRequest(BaseModel):
    """Schema para actualizar perfil de usuario"""
    full_name: Optional[str] = Field(None, description="Nombre completo")
    phone: Optional[str] = Field(None, description="Número de teléfono")
    avatar_url: Optional[str] = Field(None, description="URL del avatar")
    
    class Config:
        json_schema_extra = {
            "example": {
                "full_name": "Juan Pérez Actualizado",
                "phone": "+504 8888-8888",
                "avatar_url": "https://ejemplo.com/avatar.jpg"
            }
        }


# =====================================================
# RESPONSE SCHEMAS
# =====================================================

class UserResponse(BaseModel):
    """Schema para información del usuario"""
    id: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    """Schema para respuesta de autenticación exitosa"""
    access_token: str = Field(..., description="JWT token de acceso")
    token_type: str = Field(default="bearer", description="Tipo de token")
    expires_in: int = Field(..., description="Segundos hasta que expire el token")
    user: UserResponse = Field(..., description="Información del usuario")
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 604800,
                "user": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "email": "usuario@ejemplo.com",
                    "full_name": "Juan Pérez",
                    "phone": "+504 9999-9999",
                    "avatar_url": None,
                    "created_at": "2024-01-15T10:30:00"
                }
            }
        }


class ErrorResponse(BaseModel):
    """Schema para respuestas de error"""
    error: str = Field(..., description="Tipo de error")
    message: str = Field(..., description="Mensaje descriptivo del error")
    details: Optional[dict] = Field(None, description="Detalles adicionales del error")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "authentication_error",
                "message": "Credenciales inválidas",
                "details": None
            }
        }


class MessageResponse(BaseModel):
    """Schema para mensajes simples"""
    message: str = Field(..., description="Mensaje de respuesta")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Operación exitosa"
            }
        }