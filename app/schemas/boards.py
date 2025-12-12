"""
CronoPlan API - Board Schemas
Modelos Pydantic para tableros
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# =====================================================
# REQUEST SCHEMAS
# =====================================================

class BoardCreate(BaseModel):
    """Schema para crear un board"""
    name: str = Field(..., min_length=1, max_length=255, description="Nombre del tablero")
    color: str = Field(default="#1890FF", description="Color del tablero (hex)")
    icon: str = Field(default="📊", description="Icono del tablero (emoji)")
    type: str = Field(default="personal", description="Tipo: personal o team")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Lanzamiento Web",
                "color": "#52C41A",
                "icon": "🌐",
                "type": "personal"
            }
        }


class BoardUpdate(BaseModel):
    """Schema para actualizar un board"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    color: Optional[str] = None
    icon: Optional[str] = None
    type: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Lanzamiento Web - Actualizado",
                "color": "#9254DE"
            }
        }


# =====================================================
# RESPONSE SCHEMAS
# =====================================================

class BoardResponse(BaseModel):
    """Schema para respuesta de board"""
    id: int
    user_id: str
    name: str
    color: str
    icon: str
    type: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Lanzamiento Web",
                "color": "#52C41A",
                "icon": "🌐",
                "type": "personal",
                "created_at": "2024-01-15T10:30:00",
                "updated_at": "2024-01-15T10:30:00"
            }
        }


class BoardWithTaskCount(BoardResponse):
    """Board con conteo de tareas"""
    task_count: int = Field(default=0, description="Número de tareas en el tablero")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Lanzamiento Web",
                "color": "#52C41A",
                "icon": "🌐",
                "type": "personal",
                "task_count": 5,
                "created_at": "2024-01-15T10:30:00",
                "updated_at": "2024-01-15T10:30:00"
            }
        }