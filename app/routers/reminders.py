
from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client
from app.database import get_supabase
from app.schemas.reminders import (
    ReminderCreate,
    ReminderUpdate,
    ReminderResponse,
    NotificationResponse
)
from app.dependencies.auth import get_current_user_id
from typing import List
from datetime import datetime


router = APIRouter()


# =====================================================
# HELPER FUNCTIONS
# =====================================================

def calculate_days_until_due(due_date_str: str) -> int:
    """Calcula días hasta vencimiento"""
    if not due_date_str:
        return None
    try:
        due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
        today = datetime.now()
        delta = due_date.date() - today.date()
        return delta.days
    except:
        return None


async def enrich_reminder_data(reminder: dict, supabase: Client) -> dict:
    """Enriquece recordatorio con datos de tarea"""
    try:
        task = supabase.table("tasks").select("title, due_date").eq("id", reminder["task_id"]).single().execute()
        
        if task.data:
            reminder["task_title"] = task.data.get("title")
            reminder["task_due_date"] = task.data.get("due_date")
            
            if task.data.get("due_date"):
                reminder["days_until_due"] = calculate_days_until_due(task.data["due_date"])
        
        return reminder
    except Exception as e:
        print(f"Error enriqueciendo: {e}")
        return reminder


# =====================================================
# ENDPOINTS - RECORDATORIOS
# =====================================================

@router.get("/", response_model=List[ReminderResponse])
async def get_reminders(
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """Obtiene todos los recordatorios del usuario"""
    try:
        response = supabase.table("reminders")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("created_at", desc=True)\
            .execute()
        
        enriched = []
        for reminder in response.data:
            enriched_reminder = await enrich_reminder_data(reminder, supabase)
            enriched.append(enriched_reminder)
        
        return enriched
        
    except Exception as e:
        #print(f"Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/", response_model=ReminderResponse, status_code=status.HTTP_201_CREATED)
async def create_reminder(
    reminder_data: ReminderCreate,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """Crea un nuevo recordatorio"""
    try:
        # Verificar tarea
        task_check = supabase.table("tasks")\
            .select("id")\
            .eq("id", reminder_data.task_id)\
            .eq("user_id", user_id)\
            .execute()
        
        if not task_check.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tarea no encontrada"
            )
        
        # Validar tipo
        valid_types = ["daily", "before_due", "on_due"]
        if reminder_data.reminder_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo inválido. Usar: {', '.join(valid_types)}"
            )
        
        # Validar days_before
        if reminder_data.reminder_type == "before_due" and not reminder_data.days_before:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="days_before requerido para 'before_due'"
            )
        
        # Crear
        new_reminder = {
            "user_id": user_id,
            "task_id": reminder_data.task_id,
            "reminder_type": reminder_data.reminder_type,
            "days_before": reminder_data.days_before,
            "reminder_time": reminder_data.time,
            "is_active": reminder_data.is_active
        }
        
        response = supabase.table("reminders").insert(new_reminder).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pudo crear"
            )
        
        enriched = await enrich_reminder_data(response.data[0], supabase)
        #print(f"Recordatorio creado: {enriched['id']}")
        return enriched
        
    except HTTPException:
        raise
    except Exception as e:
        #print(f"Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{reminder_id}", response_model=ReminderResponse)
async def get_reminder(
    reminder_id: int,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """Obtiene un recordatorio"""
    try:
        response = supabase.table("reminders")\
            .select("*")\
            .eq("id", reminder_id)\
            .eq("user_id", user_id)\
            .single()\
            .execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recordatorio no encontrado"
            )
        
        enriched = await enrich_reminder_data(response.data, supabase)
        return enriched
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put("/{reminder_id}", response_model=ReminderResponse)
async def update_reminder(
    reminder_id: int,
    reminder_data: ReminderUpdate,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """Actualiza un recordatorio"""
    try:
        check = supabase.table("reminders")\
            .select("id")\
            .eq("id", reminder_id)\
            .eq("user_id", user_id)\
            .execute()
        
        if not check.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recordatorio no encontrado"
            )
        
        update_data = {}
        if reminder_data.reminder_type is not None:
            update_data["reminder_type"] = reminder_data.reminder_type
        if reminder_data.days_before is not None:
            update_data["days_before"] = reminder_data.days_before
        if reminder_data.time is not None:
            update_data["reminder_time"] = reminder_data.time
        if reminder_data.is_active is not None:
            update_data["is_active"] = reminder_data.is_active
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Proporciona al menos un campo"
            )
        
        response = supabase.table("reminders")\
            .update(update_data)\
            .eq("id", reminder_id)\
            .execute()
        
        enriched = await enrich_reminder_data(response.data[0], supabase)
        #print(f"Actualizado: {reminder_id}")
        return enriched
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reminder(
    reminder_id: int,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """Elimina un recordatorio"""
    try:
        check = supabase.table("reminders")\
            .select("id")\
            .eq("id", reminder_id)\
            .eq("user_id", user_id)\
            .execute()
        
        if not check.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recordatorio no encontrado"
            )
        
        supabase.table("reminders").delete().eq("id", reminder_id).execute()
        #print(f"Eliminado: {reminder_id}")
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# =====================================================
# ENDPOINTS - NOTIFICACIONES
# =====================================================

@router.get("/notifications/all", response_model=List[NotificationResponse])
async def get_notifications(
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """Obtiene todas las notificaciones"""
    try:
        response = supabase.table("notifications")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("created_at", desc=True)\
            .limit(50)\
            .execute()
        
        return response.data
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/notifications/unread", response_model=List[NotificationResponse])
async def get_unread_notifications(
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """Obtiene notificaciones no leídas"""
    try:
        response = supabase.table("notifications")\
            .select("*")\
            .eq("user_id", user_id)\
            .eq("is_read", False)\
            .order("created_at", desc=True)\
            .execute()
        
        return response.data
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.patch("/notifications/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_as_read(
    notification_id: int,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """Marca como leída"""
    try:
        response = supabase.table("notifications")\
            .update({"is_read": True})\
            .eq("id", notification_id)\
            .eq("user_id", user_id)\
            .execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notificación no encontrada"
            )
        
        return response.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/notifications/mark-all-read")
async def mark_all_notifications_as_read(
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """Marca todas como leídas"""
    try:
        supabase.table("notifications")\
            .update({"is_read": True})\
            .eq("user_id", user_id)\
            .eq("is_read", False)\
            .execute()
        
        return {"message": "Todas marcadas como leídas"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )