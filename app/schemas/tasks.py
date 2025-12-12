"""
CronoPlan API - Tasks Schemas
Modelos Pydantic para tareas
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date


# =====================================================
# REQUEST SCHEMAS
# =====================================================

class TaskCreate(BaseModel):
    """Schema para crear una tarea"""
    title: str = Field(..., min_length=1, max_length=200, description="Título de la tarea")
    description: Optional[str] = Field(None, description="Descripción detallada")
    board_id: Optional[int] = Field(None, description="ID del tablero")
    priority: str = Field(default="Media", description="Prioridad: Alta, Media, Baja")
    status: str = Field(default="todo", description="Estado: todo, progress, done")
    status_badge: Optional[str] = Field(None, description="Badge de categoría (Diseño, Research, etc.)")
    status_badge_color: Optional[str] = Field(default="#9254DE", description="Color del badge")
    assignee_id: Optional[str] = Field(None, description="ID del usuario asignado")
    due_date: Optional[str] = Field(None, description="Fecha límite (formato: YYYY-MM-DD)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Rediseñar Landing Page",
                "description": "Actualizar el diseño de la página principal",
                "board_id": 1,
                "priority": "Alta",
                "status": "todo",
                "status_badge": "Diseño",
                "status_badge_color": "#9254DE",
                "due_date": "2024-10-12"
            }
        }


class TaskUpdate(BaseModel):
    """Schema para actualizar una tarea"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    board_id: Optional[int] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    status_badge: Optional[str] = None
    status_badge_color: Optional[str] = None
    assignee_id: Optional[str] = None
    due_date: Optional[str] = None  # Cambiado de date a str
    completed: Optional[bool] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Rediseñar Landing Page - Actualizado",
                "status": "progress",
                "priority": "Media"
            }
        }


class TaskStatusUpdate(BaseModel):
    """Schema para cambiar solo el status (para drag & drop)"""
    status: str = Field(..., description="Nuevo estado: todo, progress, done")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "progress"
            }
        }


# =====================================================
# RESPONSE SCHEMAS
# =====================================================

class AssigneeResponse(BaseModel):
    """Schema para el usuario asignado"""
    id: str
    name: str
    avatar: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "uuid-del-usuario",
                "name": "Juan Pérez",
                "avatar": "https://i.pravatar.cc/150?img=1"
            }
        }


class TaskResponse(BaseModel):
    """Schema para respuesta de una tarea"""
    id: int
    user_id: str
    board_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    priority: str
    status: str
    status_badge: Optional[str] = None
    status_badge_color: Optional[str] = None
    assignee_id: Optional[str] = None
    due_date: Optional[str] = None  # Cambiado de date a str para evitar problemas de parsing
    completed: bool
    created_at: datetime
    updated_at: datetime
    
    # Campos adicionales computados
    board: Optional[str] = None  # Nombre del board (string)
    assignee: Optional[AssigneeResponse] = None  # Datos del asignado
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "user_id": "uuid-del-usuario",
                "board_id": 1,
                "title": "Rediseñar Landing Page",
                "description": "Actualizar el diseño de la página principal",
                "priority": "Alta",
                "status": "todo",
                "status_badge": "Diseño",
                "status_badge_color": "#9254DE",
                "assignee_id": None,
                "due_date": "2024-10-12",
                "completed": False,
                "created_at": "2024-01-15T10:30:00",
                "updated_at": "2024-01-15T10:30:00",
                "board": "Lanzamiento Web",
                "assignee": {
                    "id": "uuid",
                    "name": "Juan Pérez",
                    "avatar": "https://i.pravatar.cc/150?img=1"
                }
            }
        }


class TaskListResponse(BaseModel):
    """Schema para lista de tareas con metadatos"""
    tasks: List[TaskResponse]
    total: int
    page: int = 1
    page_size: int = 50
    
    class Config:
        json_schema_extra = {
            "example": {
                "tasks": [],
                "total": 10,
                "page": 1,
                "page_size": 50
            }
        }