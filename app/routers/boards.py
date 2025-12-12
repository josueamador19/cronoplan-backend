"""
CronoPlan API - Boards Router
Endpoints para gestión de tableros
"""

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client
from app.database import get_supabase
from app.schemas.boards import (
    BoardCreate,
    BoardUpdate,
    BoardResponse,
    BoardWithTaskCount
)
from app.dependencies.auth import get_current_user_id
from typing import List


router = APIRouter()


# =====================================================
# ENDPOINTS
# =====================================================

@router.get(
    "/",
    response_model=List[BoardWithTaskCount],
    summary="Listar todos los boards del usuario",
    description="Obtiene todos los tableros del usuario autenticado con el contador de tareas"
)
async def get_boards(
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Obtiene todos los boards del usuario con contador de tareas.
    """
    try:
        # Obtener boards del usuario
        boards_response = supabase.table("boards").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        
        boards_with_count = []
        
        for board in boards_response.data:
            # Contar tareas de cada board
            tasks_count = supabase.table("tasks").select("id", count="exact").eq("board_id", board["id"]).execute()
            
            board_data = {
                **board,
                "task_count": tasks_count.count if tasks_count.count else 0
            }
            boards_with_count.append(board_data)
        
        return boards_with_count
        
    except Exception as e:
        print(f"❌ Error al obtener boards: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener tableros: {str(e)}"
        )


@router.post(
    "/",
    response_model=BoardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un nuevo board",
    description="Crea un nuevo tablero para el usuario autenticado"
)
async def create_board(
    board_data: BoardCreate,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Crea un nuevo board.
    
    - **name**: Nombre del tablero (requerido)
    - **color**: Color en formato hex (default: #1890FF)
    - **icon**: Emoji o icono (default: 📊)
    - **type**: Tipo de tablero (default: personal)
    """
    try:
        new_board = {
            "user_id": user_id,
            "name": board_data.name,
            "color": board_data.color,
            "icon": board_data.icon,
            "type": board_data.type
        }
        
        response = supabase.table("boards").insert(new_board).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pudo crear el tablero"
            )
        
        print(f"✅ Board creado: {response.data[0]['name']}")
        return response.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al crear board: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear tablero: {str(e)}"
        )


@router.get(
    "/{board_id}",
    response_model=BoardWithTaskCount,
    summary="Obtener un board específico",
    description="Obtiene los detalles de un tablero específico"
)
async def get_board(
    board_id: int,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Obtiene un board específico por su ID.
    """
    try:
        # Obtener board
        board_response = supabase.table("boards").select("*").eq("id", board_id).eq("user_id", user_id).single().execute()
        
        if not board_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tablero no encontrado"
            )
        
        # Contar tareas
        tasks_count = supabase.table("tasks").select("id", count="exact").eq("board_id", board_id).execute()
        
        board_data = {
            **board_response.data,
            "task_count": tasks_count.count if tasks_count.count else 0
        }
        
        return board_data
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al obtener board: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener tablero: {str(e)}"
        )


@router.put(
    "/{board_id}",
    response_model=BoardResponse,
    summary="Actualizar un board",
    description="Actualiza los datos de un tablero"
)
async def update_board(
    board_id: int,
    board_data: BoardUpdate,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Actualiza un board existente.
    """
    try:
        # Verificar que el board existe y pertenece al usuario
        board_check = supabase.table("boards").select("id").eq("id", board_id).eq("user_id", user_id).execute()
        
        if not board_check.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tablero no encontrado"
            )
        
        # Construir objeto de actualización
        update_data = {}
        if board_data.name is not None:
            update_data["name"] = board_data.name
        if board_data.color is not None:
            update_data["color"] = board_data.color
        if board_data.icon is not None:
            update_data["icon"] = board_data.icon
        if board_data.type is not None:
            update_data["type"] = board_data.type
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debes proporcionar al menos un campo para actualizar"
            )
        
        # Actualizar
        response = supabase.table("boards").update(update_data).eq("id", board_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pudo actualizar el tablero"
            )
        
        print(f"✅ Board actualizado: {board_id}")
        return response.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al actualizar board: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar tablero: {str(e)}"
        )


@router.delete(
    "/{board_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un board",
    description="Elimina un tablero (las tareas asociadas quedarán sin board)"
)
async def delete_board(
    board_id: int,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Elimina un board.
    Las tareas asociadas quedarán con board_id = null.
    """
    try:
        # Verificar que el board existe y pertenece al usuario
        board_check = supabase.table("boards").select("id").eq("id", board_id).eq("user_id", user_id).execute()
        
        if not board_check.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tablero no encontrado"
            )
        
        # Eliminar board (las tareas quedarán con board_id null por ON DELETE SET NULL)
        supabase.table("boards").delete().eq("id", board_id).execute()
        
        print(f"✅ Board eliminado: {board_id}")
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error al eliminar board: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al eliminar tablero: {str(e)}"
        )