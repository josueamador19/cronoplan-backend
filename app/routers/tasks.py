from fastapi import APIRouter, Depends, HTTPException, status as http_status, Query
from supabase import Client
from app.database import get_service_supabase, get_service_supabase
from app.schemas.tasks import (
    TaskCreate,
    TaskMoveRequest,
    TaskUpdate,
    TaskStatusUpdate,
    TaskResponse,
    TaskListResponse,
    AssigneeResponse
)
from app.dependencies.auth import get_current_user_id
from typing import List, Optional


router = APIRouter()


# =====================================================
# HELPER FUNCTIONS
# =====================================================

async def enrich_task_data(task: dict, supabase: Client) -> dict:
    """
    Enriquece los datos de una tarea con información adicional.
    """
    try:
        # Agregar nombre del board
        if task.get("board_id"):
            try:
                board = supabase.table("boards").select("name").eq("id", task["board_id"]).single().execute()
                task["board"] = board.data["name"] if board.data else None
            except Exception as e:
                #print(f"Error al obtener board {task.get('board_id')}: {str(e)}")
                task["board"] = None
        else:
            task["board"] = None
        
        # Agregar datos del asignado
        if task.get("assignee_id"):
            try:
                assignee = supabase.table("users").select("id, full_name, avatar_url").eq("id", task["assignee_id"]).single().execute()
                if assignee.data:
                    task["assignee"] = {
                        "id": assignee.data["id"],
                        "name": assignee.data["full_name"] or "Usuario",
                        "avatar": assignee.data["avatar_url"]
                    }
                else:
                    task["assignee"] = None
            except Exception as e:
                #print(f"Error al obtener assignee {task.get('assignee_id')}: {str(e)}")
                task["assignee"] = None
        else:
            task["assignee"] = None
        
        return task
    except Exception as e:
        #print(f"Error al enriquecer tarea: {str(e)}")
        return task


# =====================================================
# ENDPOINTS
# =====================================================
@router.get("/", response_model=TaskListResponse)
async def get_tasks(
    board_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    completed: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_service_supabase)  
):
    """
    Obtiene todas las tareas del usuario con filtros opcionales.
    """
    try:
        #print(f"GET /tasks - User ID solicitante: {user_id}")
        
        
        query = supabase.table("tasks").select("*", count="exact").eq("user_id", user_id)
        
        # Aplicar filtros
        if board_id is not None:
            query = query.eq("board_id", board_id)
        if status is not None:
            query = query.eq("status", status)
        if priority is not None:
            query = query.eq("priority", priority)
        if completed is not None:
            query = query.eq("completed", completed)
        
        # Aplicar orden y paginación
        offset = (page - 1) * page_size
        query = query.order("created_at", desc=True).range(offset, offset + page_size - 1)
        
        response = query.execute()
        
        #print(f" GET /tasks - Tasks encontradas en DB: {len(response.data)} para user {user_id}")
        
        # Enriquecer datos
        enriched_tasks = []
        for task in response.data:
            try:
                enriched_task = await enrich_task_data(task, supabase)
                enriched_tasks.append(enriched_task)
            except Exception as e:
                enriched_tasks.append(task)
        
        #print(f"GET /tasks - Retornando {len(enriched_tasks)} tasks para user {user_id}")
        
        return TaskListResponse(
            tasks=enriched_tasks,
            total=response.count if response.count else 0,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        #print(f"Error completo al obtener tareas: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener tareas: {str(e)}"
        )

@router.post("/", response_model=TaskResponse, status_code=http_status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_service_supabase)
):
    """Crea una nueva tarea con recordatorio opcional."""
    try:
        # Verificar board si existe
        if task_data.board_id:
            board_check = supabase.table("boards")\
                .select("id")\
                .eq("id", task_data.board_id)\
                .eq("user_id", user_id)\
                .execute()
            
            if not board_check.data:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail="Tablero no encontrado"
                )
        
        # Crear tarea
        new_task = {
            "user_id": user_id,
            "title": task_data.title,
            "description": task_data.description,
            "board_id": task_data.board_id,
            "priority": task_data.priority,
            "status": task_data.status,
            "status_badge": task_data.status_badge,
            "status_badge_color": task_data.status_badge_color,
            "assignee_id": task_data.assignee_id,
            "due_date": task_data.due_date,
            "due_time": task_data.due_time, 
            "completed": False
        }
        
        response = supabase.table("tasks").insert(new_task).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="No se pudo crear la tarea"
            )
        
        task = response.data[0]
        
        if task_data.create_reminder and task_data.due_date:
            try:
                auto_reminder = {
                    "user_id": user_id,
                    "task_id": task["id"],
                    "reminder_type": "before_due",
                    "days_before": task_data.reminder_days_before,
                    "reminder_time": task_data.reminder_time,
                    "is_active": True
                }
                
                reminder_result = supabase.table("reminders")\
                    .insert(auto_reminder)\
                    .execute()
                
                if reminder_result.data:
                    print(f"Recordatorio automático creado: {reminder_result.data[0]['id']}")
                
            except Exception as e:
                # No fallar la creación de tarea si falla el recordatorio
                print(f"Error al crear recordatorio automático: {e}")
        
        # Enriquecer datos
        enriched_task = await enrich_task_data(task, supabase)
        
        #print(f"Tarea creada: {task['title']}")
        return enriched_task
        
    except HTTPException:
        raise
    except Exception as e:
        #print(f"Error: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Obtener una tarea específica",
    description="Obtiene los detalles de una tarea específica"
)
async def get_task(
    task_id: int,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_service_supabase)
):
    """Obtiene una tarea específica por su ID."""
    try:
        response = supabase.table("tasks").select("*").eq("id", task_id).eq("user_id", user_id).single().execute()
        
        if not response.data:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Tarea no encontrada"
            )
        
        # Enriquecer datos
        task = await enrich_task_data(response.data, supabase)
        
        return task
        
    except HTTPException:
        raise
    except Exception as e:
        #print(f"Error al obtener tarea: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener tarea: {str(e)}"
        )


@router.put(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Actualizar una tarea",
    description="Actualiza los datos de una tarea"
)
async def update_task(
    task_id: int,
    task_data: TaskUpdate,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_service_supabase)
):
    """Actualiza una tarea existente."""
    try:
        # Verificar que la tarea existe
        task_check = supabase.table("tasks").select("id").eq("id", task_id).eq("user_id", user_id).execute()
        
        if not task_check.data:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Tarea no encontrada"
            )
        
        # Construir update
        update_data = {}
        if task_data.title is not None:
            update_data["title"] = task_data.title
        if task_data.description is not None:
            update_data["description"] = task_data.description
        if task_data.board_id is not None:
            update_data["board_id"] = task_data.board_id
        if task_data.priority is not None:
            update_data["priority"] = task_data.priority
        if task_data.status is not None:
            update_data["status"] = task_data.status
            if task_data.status == "done":
                update_data["completed"] = True
        if task_data.status_badge is not None:
            update_data["status_badge"] = task_data.status_badge
        if task_data.status_badge_color is not None:
            update_data["status_badge_color"] = task_data.status_badge_color
        if task_data.assignee_id is not None:
            update_data["assignee_id"] = task_data.assignee_id
        if task_data.due_date is not None:
            update_data["due_date"] = task_data.due_date 
        if task_data.completed is not None:
            update_data["completed"] = task_data.completed
        
        if not update_data:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Debes proporcionar al menos un campo"
            )
        
        response = supabase.table("tasks").update(update_data).eq("id", task_id).execute()
        task = await enrich_task_data(response.data[0], supabase)
        
        #print(f"Tarea actualizada: {task_id}")
        return task
        
    except HTTPException:
        raise
    except Exception as e:
        #print(f"Error: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.patch(
    "/{task_id}/status",
    response_model=TaskResponse,
    summary="Cambiar status",
    description="Cambia solo el status (drag & drop)"
)
async def update_task_status(
    task_id: int,
    status_data: TaskStatusUpdate,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_service_supabase)
):
    """Cambia solo el status."""
    try:
        task_check = supabase.table("tasks").select("id").eq("id", task_id).eq("user_id", user_id).execute()
        
        if not task_check.data:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Tarea no encontrada"
            )
        
        update_data = {"status": status_data.status}
        if status_data.status == "done":
            update_data["completed"] = True
        
        response = supabase.table("tasks").update(update_data).eq("id", task_id).execute()
        task = await enrich_task_data(response.data[0], supabase)
        
        #print(f"Status actualizado: {task_id} -> {status_data.status}")
        return task
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete(
    "/{task_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    summary="Eliminar tarea"
)
async def delete_task(
    task_id: int,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_service_supabase)
):
    """Elimina una tarea."""
    try:
        task_check = supabase.table("tasks").select("id").eq("id", task_id).eq("user_id", user_id).execute()
        
        if not task_check.data:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Tarea no encontrada"
            )
        
        supabase.table("tasks").delete().eq("id", task_id).execute()
        #print(f"Tarea eliminada: {task_id}")
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/board/{board_id}",
    response_model=List[TaskResponse],
    summary="Tareas de un board"
)
async def get_tasks_by_board(
    board_id: int,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_service_supabase)
):
    """Obtiene tareas de un board."""
    try:
        board_check = supabase.table("boards").select("id").eq("id", board_id).eq("user_id", user_id).execute()
        
        if not board_check.data:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Tablero no encontrado"
            )
        
        response = supabase.table("tasks").select("*").eq("board_id", board_id).order("created_at", desc=False).execute()
        
        enriched_tasks = []
        for task in response.data:
            enriched_task = await enrich_task_data(task, supabase)
            enriched_tasks.append(enriched_task)
        
        return enriched_tasks
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    


@router.patch(
    "/{task_id}/move",
    response_model=TaskResponse,
    summary="Mover tarea a otro tablero",
    description="Mueve una tarea a otro tablero o a 'sin tablero' (board_id=null)"
)
async def move_task_to_board(
    task_id: int,
    move_data: TaskMoveRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_service_supabase)
):
    """
    Mueve una tarea a otro tablero o a 'sin tablero'.
    
    - **task_id**: ID de la tarea a mover
    - **board_id**: ID del tablero destino (null para mover a 'sin tablero')
    
    Validaciones:
    - La tarea debe pertenecer al usuario
    - Si se especifica board_id, el tablero debe existir y pertenecer al usuario
    """
    try:
        # 1. Verificar que la tarea existe y pertenece al usuario
        task_check = supabase.table("tasks")\
            .select("id, title, board_id")\
            .eq("id", task_id)\
            .eq("user_id", user_id)\
            .execute()
        
        if not task_check.data:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Tarea no encontrada"
            )
        
        current_task = task_check.data[0]
        old_board_id = current_task.get("board_id")
        new_board_id = move_data.board_id
        
        # 2. Si el board_id es el mismo, no hacer nada
        if old_board_id == new_board_id:
            enriched_task = await enrich_task_data(current_task, supabase)
            return enriched_task
        
        # 3. Si se especifica un nuevo board_id, verificar que existe y pertenece al usuario
        if new_board_id is not None:
            board_check = supabase.table("boards")\
                .select("id, name")\
                .eq("id", new_board_id)\
                .eq("user_id", user_id)\
                .execute()
            
            if not board_check.data:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail="Tablero destino no encontrado"
                )
            
            new_board_name = board_check.data[0]["name"]
        else:
            new_board_name = "sin tablero"
        
        # 4. Actualizar el board_id de la tarea
        update_data = {"board_id": new_board_id}
        
        response = supabase.table("tasks")\
            .update(update_data)\
            .eq("id", task_id)\
            .execute()
        
        if not response.data:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="No se pudo mover la tarea"
            )
        
        # 5. Enriquecer datos de la tarea actualizada
        updated_task = await enrich_task_data(response.data[0], supabase)
        
        # Log para debugging (opcional)
        old_board_text = f"tablero {old_board_id}" if old_board_id else "sin tablero"
        print(f"Tarea '{current_task['title']}' movida de {old_board_text} a {new_board_name}")
        
        return updated_task
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error al mover tarea: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al mover tarea: {str(e)}"
        )