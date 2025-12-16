from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# =====================================================
# REQUEST SCHEMAS
# =====================================================

class ReminderCreate(BaseModel):
    """Schema para crear un recordatorio"""
    task_id: int = Field(..., description="ID de la tarea")
    reminder_type: str = Field(..., description="daily, before_due, on_due")
    days_before: Optional[int] = Field(None, description="Días antes (before_due)")
    time: Optional[str] = Field(None, description="Hora HH:MM")
    is_active: bool = Field(default=True)
    
    class Config:
        json_schema_extra = {
            "example": {
                "task_id": 1,
                "reminder_type": "before_due",
                "days_before": 1,
                "time": "09:00",
                "is_active": True
            }
        }


class ReminderUpdate(BaseModel):
    """Schema para actualizar recordatorio"""
    reminder_type: Optional[str] = None
    days_before: Optional[int] = None
    time: Optional[str] = None
    is_active: Optional[bool] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "is_active": False
            }
        }


# =====================================================
# RESPONSE SCHEMAS
# =====================================================

class ReminderResponse(BaseModel):
    """Schema de respuesta de recordatorio"""
    id: int
    user_id: str
    task_id: int
    reminder_type: str
    days_before: Optional[int] = None
    reminder_time: Optional[str] = None
    is_active: bool
    last_sent: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    # Datos enriquecidos
    task_title: Optional[str] = None
    task_due_date: Optional[str] = None
    days_until_due: Optional[int] = None
    
    class Config:
        from_attributes = True


class NotificationResponse(BaseModel):
    """Schema de notificación"""
    id: int
    user_id: str
    task_id: Optional[int] = None
    reminder_id: Optional[int] = None
    title: str
    message: str
    notification_type: str
    is_read: bool
    created_at: datetime
    
    class Config:
        from_attributes = True