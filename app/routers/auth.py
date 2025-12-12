"""
CronoPlan API - Auth Router
Endpoints para registro, login y gestión de autenticación
"""

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client
from app.database import get_supabase
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    AuthResponse,
    UserResponse,
    ErrorResponse,
    MessageResponse,
    UpdateProfileRequest
)
from app.dependencies.auth import get_current_user, get_current_user_id
from typing import Dict
import jwt
from datetime import datetime, timedelta
from app.config import settings


router = APIRouter()


# =====================================================
# HELPER FUNCTIONS
# =====================================================

def create_access_token(user_id: str, email: str) -> tuple[str, int]:
    """
    Crea un JWT token de acceso.
    
    Returns:
        tuple: (token, expires_in_seconds)
    """
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60  # convertir a segundos
    
    to_encode = {
        "sub": user_id,
        "email": email,
        "exp": expire,
        "iat": datetime.utcnow()
    }
    
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.SECRET_KEY, 
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt, expires_in


async def create_user_profile(supabase: Client, user_id: str, email: str, full_name: str = None, phone: str = None) -> Dict:
    """
    Crea el perfil del usuario en la tabla users.
    """
    try:
        user_data = {
            "id": user_id,
            "full_name": full_name,
            "phone": phone,
            "avatar_url": None
        }
        
        response = supabase.table("users").insert(user_data).execute()
        
        if response.data:
            return response.data[0]
        else:
            # Si falla, retornar datos básicos
            return {**user_data, "email": email, "created_at": datetime.utcnow().isoformat()}
    except Exception as e:
        print(f"Error creando perfil de usuario: {e}")
        # Si falla, retornar datos básicos
        return {
            "id": user_id,
            "email": email,
            "full_name": full_name,
            "phone": phone,
            "avatar_url": None,
            "created_at": datetime.utcnow().isoformat()
        }


# =====================================================
# ENDPOINTS
# =====================================================

@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar nuevo usuario",
    description="Crea una nueva cuenta de usuario con email y contraseña",
    responses={
        201: {"description": "Usuario registrado exitosamente"},
        400: {"model": ErrorResponse, "description": "Email ya existe o datos inválidos"},
        500: {"model": ErrorResponse, "description": "Error interno del servidor"}
    }
)
async def register(
    data: RegisterRequest,
    supabase: Client = Depends(get_supabase)
):
    """
    Registra un nuevo usuario.
    
    - **email**: Email del usuario (debe ser único)
    - **password**: Contraseña (mínimo 6 caracteres)
    - **full_name**: Nombre completo del usuario (opcional)
    - **phone**: Número de teléfono del usuario (opcional)
    """
    try:
        print(f"📧 Intentando registrar usuario: {data.email}")
        
        # Registrar usuario en Supabase Auth
        auth_response = supabase.auth.sign_up({
            "email": data.email,
            "password": data.password,
            "options": {
                "data": {
                    "full_name": data.full_name,
                    "phone": data.phone
                }
            }
        })
        
        print(f"✅ Respuesta de Supabase: {auth_response}")
        
        if not auth_response.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pudo crear el usuario. Verifica que el email sea válido y no esté ya registrado."
            )
        
        user_id = auth_response.user.id
        user_email = auth_response.user.email
        
        print(f"👤 Usuario creado con ID: {user_id}")
        
        # Crear perfil en la tabla users
        user_profile = await create_user_profile(
            supabase=supabase,
            user_id=user_id,
            email=user_email,
            full_name=data.full_name,
            phone=data.phone
        )
        
        # Generar token de acceso
        access_token, expires_in = create_access_token(
            user_id=user_id,
            email=user_email
        )
        
        # Construir respuesta
        user_response = UserResponse(
            id=user_id,
            email=user_email,
            full_name=data.full_name,
            phone=data.phone,
            avatar_url=None,
            created_at=user_profile.get("created_at")
        )
        
        return AuthResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=expires_in,
            user=user_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_message = str(e)
        print(f"❌ Error completo: {error_message}")
        
        # Detectar diferentes tipos de errores
        if "already registered" in error_message.lower() or "already been registered" in error_message.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El email ya está registrado"
            )
        
        if "invalid" in error_message.lower() and "email" in error_message.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El formato del email es inválido o Supabase no permite este email. Verifica la configuración de autenticación en Supabase (Settings > Authentication > Email Auth Settings)"
            )
        
        if "email" in error_message.lower() and "confirmation" in error_message.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El usuario fue creado pero requiere confirmación por email. Revisa tu bandeja de entrada."
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al registrar usuario: {error_message}"
        )


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Iniciar sesión",
    description="Autentica un usuario con email y contraseña",
    responses={
        200: {"description": "Login exitoso"},
        401: {"model": ErrorResponse, "description": "Credenciales inválidas"},
        500: {"model": ErrorResponse, "description": "Error interno del servidor"}
    }
)
async def login(
    data: LoginRequest,
    supabase: Client = Depends(get_supabase)
):
    """
    Inicia sesión con email y contraseña.
    
    - **email**: Email del usuario
    - **password**: Contraseña
    """
    try:
        print(f"🔐 Intento de login: {data.email}")
        
        # Autenticar con Supabase
        auth_response = supabase.auth.sign_in_with_password({
            "email": data.email,
            "password": data.password
        })
        
        if not auth_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales inválidas"
            )
        
        user_id = auth_response.user.id
        user_email = auth_response.user.email
        
        print(f"✅ Login exitoso para: {user_email}")
        
        # Obtener perfil del usuario
        try:
            profile_response = supabase.table("users").select("*").eq("id", user_id).single().execute()
            user_profile = profile_response.data if profile_response.data else {}
        except:
            # Si no existe perfil, crearlo
            print(f"⚠️ Perfil no encontrado, creando uno nuevo...")
            user_profile = await create_user_profile(supabase, user_id, user_email)
        
        # Generar token de acceso
        access_token, expires_in = create_access_token(
            user_id=user_id,
            email=user_email
        )
        
        # Construir respuesta
        user_response = UserResponse(
            id=user_id,
            email=user_email,
            full_name=user_profile.get("full_name"),
            phone=user_profile.get("phone"),
            avatar_url=user_profile.get("avatar_url"),
            created_at=user_profile.get("created_at")
        )
        
        return AuthResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=expires_in,
            user=user_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_message = str(e)
        print(f"❌ Error en login: {error_message}")
        
        # Detectar errores de credenciales
        if "invalid" in error_message.lower() or "credentials" in error_message.lower() or "password" in error_message.lower():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales inválidas"
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al iniciar sesión: {error_message}"
        )


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Cerrar sesión",
    description="Cierra la sesión del usuario actual (requiere autenticación)",
    responses={
        200: {"description": "Sesión cerrada exitosamente"},
        401: {"model": ErrorResponse, "description": "No autenticado"}
    }
)
async def logout(
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Cierra la sesión del usuario actual.
    
    **Requiere autenticación** (enviar token en header: `Authorization: Bearer <token>`)
    """
    try:
        # Cerrar sesión en Supabase
        supabase.auth.sign_out()
        
        return MessageResponse(
            message="Sesión cerrada exitosamente"
        )
    except Exception as e:
        # Incluso si falla, consideramos que se cerró la sesión
        return MessageResponse(
            message="Sesión cerrada exitosamente"
        )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Obtener usuario actual",
    description="Retorna la información del usuario autenticado",
    responses={
        200: {"description": "Información del usuario"},
        401: {"model": ErrorResponse, "description": "No autenticado"},
        404: {"model": ErrorResponse, "description": "Usuario no encontrado"}
    }
)
async def get_me(
    current_user: Dict = Depends(get_current_user)
):
    """
    Obtiene la información del usuario autenticado.
    
    **Requiere autenticación** (enviar token en header: `Authorization: Bearer <token>`)
    """
    return UserResponse(
        id=current_user.get("id"),
        email=current_user.get("email"),
        full_name=current_user.get("full_name"),
        phone=current_user.get("phone"),
        avatar_url=current_user.get("avatar_url"),
        created_at=current_user.get("created_at")
    )


@router.get(
    "/verify",
    response_model=MessageResponse,
    summary="Verificar token",
    description="Verifica si el token es válido",
    responses={
        200: {"description": "Token válido"},
        401: {"model": ErrorResponse, "description": "Token inválido o expirado"}
    }
)
async def verify_token(
    user_id: str = Depends(get_current_user_id)
):
    """
    Verifica si el token de autenticación es válido.
    
    **Requiere autenticación** (enviar token en header: `Authorization: Bearer <token>`)
    """
    return MessageResponse(
        message=f"Token válido para el usuario {user_id}"
    )


@router.put(
    "/me",
    response_model=UserResponse,
    summary="Actualizar perfil",
    description="Actualiza la información del usuario autenticado",
    responses={
        200: {"description": "Perfil actualizado exitosamente"},
        401: {"model": ErrorResponse, "description": "No autenticado"},
        500: {"model": ErrorResponse, "description": "Error interno del servidor"}
    }
)
async def update_profile(
    data: UpdateProfileRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Actualiza el perfil del usuario autenticado.
    
    - **full_name**: Nombre completo (opcional)
    - **phone**: Número de teléfono (opcional)
    - **avatar_url**: URL del avatar (opcional)
    
    **Requiere autenticación** (enviar token en header: `Authorization: Bearer <token>`)
    """
    try:
        # Construir objeto de actualización solo con campos proporcionados
        update_data = {}
        if data.full_name is not None:
            update_data["full_name"] = data.full_name
        if data.phone is not None:
            update_data["phone"] = data.phone
        if data.avatar_url is not None:
            update_data["avatar_url"] = data.avatar_url
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debes proporcionar al menos un campo para actualizar"
            )
        
        # Actualizar en la base de datos
        response = supabase.table("users").update(update_data).eq("id", user_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        
        updated_user = response.data[0]
        
        return UserResponse(
            id=updated_user.get("id"),
            email=updated_user.get("email"),
            full_name=updated_user.get("full_name"),
            phone=updated_user.get("phone"),
            avatar_url=updated_user.get("avatar_url"),
            created_at=updated_user.get("created_at")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error actualizando perfil: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar perfil: {str(e)}"
        )