
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date


# =====================================================
# REQUEST SCHEMAS
# =====================================================

class TaskCreate(BaseModel):
    """Schema para crear una tarea"""
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    board_id: Optional[int] = None
    priority: str = Field(default="Media")
    status: str = Field(default="todo")
    status_badge: Optional[str] = None
    status_badge_color: Optional[str] = Field(default="#9254DE")
    assignee_id: Optional[str] = None
    due_date: Optional[str] = None
    due_time: Optional[str] = Field(default="09:00", description="Hora de vencimiento HH:MM")
    
    # Configuración de recordatorio automático
    create_reminder: bool = Field(default=True, description="Crear recordatorio automático")
    reminder_days_before: int = Field(default=1, description="Días antes para recordatorio")
    reminder_time: str = Field(default="09:00", description="Hora del recordatorio")
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Rediseñar Landing Page",
                "description": "Actualizar diseño",
                "board_id": 1,
                "priority": "Alta",
                "status": "todo",
                "due_date": "2024-10-12",
                "due_time": "14:00",
                "create_reminder": True, 
                "reminder_days_before": 1, 
                "reminder_time": "09:00" 
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
    due_date: Optional[str] = None
    due_time: Optional[str] = None  
    completed: Optional[bool] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Rediseñar Landing Page - Actualizado",
                "status": "progress",
                "priority": "Media",
                "due_time": "15:00"  
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
    due_date: Optional[str] = None
    due_time: Optional[str] = None 
    completed: bool
    created_at: datetime
    updated_at: datetime
    
    # Campos adicionales computados
    board: Optional[str] = None
    assignee: Optional[AssigneeResponse] = None
    
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
                "due_time": "14:00", 
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