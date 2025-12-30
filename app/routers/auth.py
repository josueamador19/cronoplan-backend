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
    UpdateProfileRequest,
    RefreshTokenRequest
)
from app.dependencies.auth import get_current_user, get_current_user_id
from typing import Dict
import jwt
from datetime import datetime, timedelta
from app.config import settings
from pydantic import BaseModel


router = APIRouter()


# =====================================================
# SCHEMAS ADICIONALES
# =====================================================
class GoogleAuthRequest(BaseModel):
    """Schema para autenticación con Google"""
    id_token: str  # Token de Google OAuth


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
    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60  
    
    to_encode = {
        "sub": user_id,
        "email": email,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    }
    
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.SECRET_KEY, 
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt, expires_in


def create_refresh_token(user_id: str, email: str) -> tuple[str, int]:
    """
    Crea un JWT refresh token de larga duración.
    
    Returns:
        tuple: (token, expires_in_seconds)
    """
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    expires_in = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    
    to_encode = {
        "sub": user_id,
        "email": email,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    }
    
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.SECRET_KEY, 
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt, expires_in


async def create_user_profile(supabase: Client, user_id: str, email: str, full_name: str = None, phone: str = None, avatar_url: str = None) -> Dict:
    """
    Crea el perfil del usuario en la tabla users.
    """
    try:
        user_data = {
            "id": user_id,
            "full_name": full_name,
            "phone": phone,
            "avatar_url": avatar_url
        }
        
        response = supabase.table("users").insert(user_data).execute()
        
        if response.data:
            return response.data[0]
        else:
            return {**user_data, "email": email, "created_at": datetime.utcnow().isoformat()}
    except Exception as e:
        print(f"Error creando perfil de usuario: {e}")
        return {
            "id": user_id,
            "email": email,
            "full_name": full_name,
            "phone": phone,
            "avatar_url": avatar_url,
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
    try:
        print(f"Intentando registrar usuario: {data.email}")
        
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
        
        if not auth_response.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pudo crear el usuario. Verifica que el email sea válido y no esté ya registrado."
            )
        
        user_id = auth_response.user.id
        user_email = auth_response.user.email
        
        # Crear perfil en la tabla users
        user_profile = await create_user_profile(
            supabase=supabase,
            user_id=user_id,
            email=user_email,
            full_name=data.full_name,
            phone=data.phone
        )
        
        # Generar tokens de acceso y refresh
        access_token, access_expires = create_access_token(
            user_id=user_id,
            email=user_email
        )
        
        refresh_token, refresh_expires = create_refresh_token(
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
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=access_expires,
            user=user_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_message = str(e)
        
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
    try:
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
        
        # Obtener perfil del usuario
        try:
            profile_response = supabase.table("users").select("*").eq("id", user_id).single().execute()
            user_profile = profile_response.data if profile_response.data else {}
        except:
            # Si no existe perfil, crearlo
            user_profile = await create_user_profile(supabase, user_id, user_email)
        
        # Generar tokens de acceso y refresh
        access_token, access_expires = create_access_token(
            user_id=user_id,
            email=user_email
        )
        
        refresh_token, refresh_expires = create_refresh_token(
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
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=access_expires,
            user=user_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_message = str(e)
        
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
    "/refresh",
    response_model=AuthResponse,
    summary="Renovar token de acceso",
    description="Genera un nuevo access_token usando el refresh_token",
    responses={
        200: {"description": "Token renovado exitosamente"},
        401: {"model": ErrorResponse, "description": "Refresh token inválido o expirado"}
    }
)
async def refresh_token(
    data: RefreshTokenRequest,
    supabase: Client = Depends(get_supabase)
):
    """
    Endpoint para renovar el access token usando un refresh token válido.
    
    Este endpoint permite mantener la sesión del usuario sin necesidad de
    volver a hacer login cuando el access token expira.
    """
    try:
        # Decodificar y validar refresh token
        payload = jwt.decode(
            data.refresh_token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        
        # Verificar que sea un refresh token
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido: no es un refresh token"
            )
        
        user_id = payload.get("sub")
        email = payload.get("email")
        
        if not user_id or not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido: información de usuario incompleta"
            )
        
        # Verificar que el usuario aún exista en la base de datos
        try:
            profile_response = supabase.table("users").select("*").eq("id", user_id).single().execute()
            if not profile_response.data:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Usuario no encontrado"
                )
            user_profile = profile_response.data
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no encontrado"
            )
        
        # Generar nuevos tokens
        new_access_token, access_expires = create_access_token(user_id, email)
        new_refresh_token, refresh_expires = create_refresh_token(user_id, email)
        
        user_response = UserResponse(
            id=user_id,
            email=email,
            full_name=user_profile.get("full_name"),
            phone=user_profile.get("phone"),
            avatar_url=user_profile.get("avatar_url"),
            created_at=user_profile.get("created_at")
        )
        
        return AuthResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=access_expires,
            user=user_response
        )
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expirado. Por favor, inicia sesión nuevamente."
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido"
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error al renovar token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Error al renovar token"
        )


@router.post(
    "/google",
    response_model=AuthResponse,
    summary="Iniciar sesión con Google",
    description="Autentica un usuario usando Google OAuth. No requiere confirmación de email.",
    responses={
        200: {"description": "Login exitoso"},
        400: {"model": ErrorResponse, "description": "Token de Google inválido"},
        500: {"model": ErrorResponse, "description": "Error interno del servidor"}
    }
)
async def google_auth(
    data: GoogleAuthRequest,
    supabase: Client = Depends(get_supabase)
):
    try:
        print(f"Intento de login con Google")
        
        # Autenticar con Google usando Supabase
        auth_response = supabase.auth.sign_in_with_id_token({
            "provider": "google",
            "token": data.id_token
        })
        
        if not auth_response.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pudo autenticar con Google. Token inválido."
            )
        
        user_id = auth_response.user.id
        user_email = auth_response.user.email
        user_metadata = auth_response.user.user_metadata or {}
        
        # Extraer información de Google
        full_name = user_metadata.get("full_name") or user_metadata.get("name")
        avatar_url = user_metadata.get("avatar_url") or user_metadata.get("picture")
        
        print(f"Login con Google exitoso para: {user_email}")
        
        # Verificar si el perfil existe en la tabla users
        try:
            profile_response = supabase.table("users").select("*").eq("id", user_id).single().execute()
            user_profile = profile_response.data
            
            # Si existe, actualizar avatar si es necesario
            if avatar_url and user_profile.get("avatar_url") != avatar_url:
                update_response = supabase.table("users").update({
                    "avatar_url": avatar_url,
                    "full_name": full_name or user_profile.get("full_name")
                }).eq("id", user_id).execute()
                user_profile = update_response.data[0] if update_response.data else user_profile
                
        except Exception as profile_error:
            # Si no existe perfil, crearlo
            print(f"Perfil no encontrado, creando uno nuevo para usuario de Google...")
            user_profile = await create_user_profile(
                supabase=supabase,
                user_id=user_id,
                email=user_email,
                full_name=full_name,
                avatar_url=avatar_url
            )
        
        # Generar tokens de acceso y refresh
        access_token, access_expires = create_access_token(
            user_id=user_id,
            email=user_email
        )
        
        refresh_token, refresh_expires = create_refresh_token(
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
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=access_expires,
            user=user_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_message = str(e)
        print(f"Error en login con Google: {error_message}")
        
        if "invalid" in error_message.lower() or "token" in error_message.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token de Google inválido o expirado"
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al autenticar con Google: {error_message}"
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar perfil: {str(e)}"
        )