from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from supabase import Client
from app.database import get_service_supabase
from app.dependencies.auth import get_current_user_id
from pydantic import BaseModel, Field
from typing import Optional
import uuid
import os


router = APIRouter()


# =====================================================
# SCHEMAS
# =====================================================
class UpdateProfileRequest(BaseModel):
    """Schema para actualizar nombre de usuario"""
    full_name: str = Field(..., min_length=1, max_length=100, description="Nombre completo del usuario")


class ProfileResponse(BaseModel):
    """Schema de respuesta del perfil"""
    id: str
    email: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    message: str


class MessageResponse(BaseModel):
    """Schema para mensajes simples"""
    message: str


# =====================================================
# CONFIGURACIÓN
# =====================================================
BUCKET_NAME = "avatars"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


# =====================================================
# HELPER FUNCTIONS
# =====================================================
def get_file_extension(filename: str) -> str:
    """Obtiene la extensión del archivo"""
    return os.path.splitext(filename)[1].lower()


def validate_image(file: UploadFile) -> None:
    """Valida que el archivo sea una imagen válida"""
    # Validar extensión
    ext = get_file_extension(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato de archivo no permitido. Usa: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Validar content type
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo debe ser una imagen"
        )


async def delete_old_avatar(supabase: Client, user_id: str, old_avatar_url: str) -> None:
    """Elimina el avatar anterior del storage de Supabase"""
    if not old_avatar_url:
        return
    
    try:
        # Extraer el path del avatar desde la URL
        # Formato esperado: https://[proyecto].supabase.co/storage/v1/object/public/avatars/[user_id]/[filename]
        if "/avatars/" in old_avatar_url:
            path = old_avatar_url.split("/avatars/")[1]
            supabase.storage.from_(BUCKET_NAME).remove([path])
            print(f"Avatar anterior eliminado: {path}")
    except Exception as e:
        print(f"Error al eliminar avatar anterior: {e}")
        # No lanzamos excepción, solo logueamos


# =====================================================
# ENDPOINTS
# =====================================================

@router.put(
    "/name",
    response_model=ProfileResponse,
    summary="Actualizar nombre de usuario",
    description="Actualiza el nombre completo del usuario autenticado",
    responses={
        200: {"description": "Nombre actualizado exitosamente"},
        401: {"description": "No autenticado"},
        400: {"description": "Datos inválidos"}
    }
)
async def update_name(
    data: UpdateProfileRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_service_supabase)
):
    """Actualiza el nombre del usuario"""
    try:
        # Actualizar en la base de datos
        response = supabase.table("users").update({
            "full_name": data.full_name
        }).eq("id", user_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        
        updated_user = response.data[0]
        
        return ProfileResponse(
            id=updated_user["id"],
            email=updated_user.get("email", ""),
            full_name=updated_user.get("full_name"),
            avatar_url=updated_user.get("avatar_url"),
            message="Nombre actualizado exitosamente"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar nombre: {str(e)}"
        )


@router.post(
    "/avatar",
    response_model=ProfileResponse,
    summary="Subir/Actualizar foto de perfil",
    description="Sube o actualiza la foto de perfil del usuario. Acepta JPG, PNG, WEBP (máx 5MB)",
    responses={
        200: {"description": "Avatar actualizado exitosamente"},
        401: {"description": "No autenticado"},
        400: {"description": "Archivo inválido"}
    }
)
async def upload_avatar(
    file: UploadFile = File(..., description="Imagen de perfil (JPG, PNG, WEBP)"),
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_service_supabase)
):
    """Sube o actualiza el avatar del usuario"""
    try:
        # Validar imagen
        validate_image(file)
        
        # Leer contenido del archivo
        contents = await file.read()
        
        # Validar tamaño
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El archivo es demasiado grande. Máximo: {MAX_FILE_SIZE / (1024*1024):.1f}MB"
            )
        
        # Obtener usuario actual para eliminar avatar anterior
        user_response = supabase.table("users").select("avatar_url").eq("id", user_id).single().execute()
        old_avatar_url = user_response.data.get("avatar_url") if user_response.data else None
        
        # Generar nombre único para el archivo
        file_ext = get_file_extension(file.filename)
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = f"{user_id}/{unique_filename}"
        
        # Subir archivo a Supabase Storage
        upload_response = supabase.storage.from_(BUCKET_NAME).upload(
            path=file_path,
            file=contents,
            file_options={
                "content-type": file.content_type,
                "upsert": "false"
            }
        )
        
        # Obtener URL pública del archivo
        public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(file_path)
        
        # Actualizar avatar_url en la base de datos
        update_response = supabase.table("users").update({
            "avatar_url": public_url
        }).eq("id", user_id).execute()
        
        if not update_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        
        # Eliminar avatar anterior si existe
        if old_avatar_url:
            await delete_old_avatar(supabase, user_id, old_avatar_url)
        
        updated_user = update_response.data[0]
        
        return ProfileResponse(
            id=updated_user["id"],
            email=updated_user.get("email", ""),
            full_name=updated_user.get("full_name"),
            avatar_url=updated_user.get("avatar_url"),
            message="Avatar actualizado exitosamente"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error al subir avatar: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al subir avatar: {str(e)}"
        )


@router.delete(
    "/avatar",
    response_model=MessageResponse,
    summary="Eliminar foto de perfil",
    description="Elimina la foto de perfil del usuario",
    responses={
        200: {"description": "Avatar eliminado exitosamente"},
        401: {"description": "No autenticado"}
    }
)
async def delete_avatar(
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_service_supabase)
):
    """Elimina el avatar del usuario"""
    try:
        # Obtener URL del avatar actual
        user_response = supabase.table("users").select("avatar_url").eq("id", user_id).single().execute()
        
        if not user_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        
        avatar_url = user_response.data.get("avatar_url")
        
        if not avatar_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El usuario no tiene avatar para eliminar"
            )
        
        # Eliminar del storage
        await delete_old_avatar(supabase, user_id, avatar_url)
        
        # Actualizar base de datos
        supabase.table("users").update({
            "avatar_url": None
        }).eq("id", user_id).execute()
        
        return MessageResponse(
            message="Avatar eliminado exitosamente"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al eliminar avatar: {str(e)}"
        )