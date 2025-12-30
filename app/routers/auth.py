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
import asyncio


router = APIRouter()


class GoogleAuthRequest(BaseModel):
    """Schema para autenticación con Google"""
    id_token: str


def create_access_token(user_id: str, email: str) -> tuple[str, int]:
    """Crea un JWT token de acceso."""
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
    """Crea un JWT refresh token de larga duración."""
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


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar nuevo usuario",
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
        print(f"📧 Registrando usuario: {data.email}")
        
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
                detail="No se pudo crear el usuario. Verifica que el email sea válido."
            )
        
        user_id = auth_response.user.id
        user_email = auth_response.user.email
        
        print(f"✅ Usuario creado en Auth: {user_email}")
        
        # El trigger de la base de datos creará el perfil automáticamente
        # Esperar un momento para que el trigger termine
        await asyncio.sleep(0.3)
        
        # Obtener el perfil creado por el trigger
        try:
            response = supabase.table("users").select("*").eq("id", user_id).single().execute()
            user_profile = response.data
        except:
            # Si el trigger aún no terminó, usar datos básicos
            user_profile = {
                "id": user_id,
                "email": user_email,
                "full_name": data.full_name,
                "phone": data.phone,
                "created_at": datetime.utcnow().isoformat()
            }
        
        # Generar tokens JWT
        access_token, access_expires = create_access_token(user_id, user_email)
        refresh_token, refresh_expires = create_refresh_token(user_id, user_email)
        
        user_response = UserResponse(
            id=user_id,
            email=user_email,
            full_name=user_profile.get("full_name") or data.full_name,
            phone=user_profile.get("phone") or data.phone,
            avatar_url=user_profile.get("avatar_url"),
            created_at=user_profile.get("created_at")
        )
        
        print(f"✅ Registro completado: {user_email}")
        
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
        print(f"❌ Error en registro: {error_message}")
        
        if "already registered" in error_message.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El email ya está registrado"
            )
        
        if "invalid" in error_message.lower() and "email" in error_message.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El formato del email es inválido"
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al registrar usuario: {error_message}"
        )


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Iniciar sesión",
    responses={
        200: {"description": "Login exitoso"},
        401: {"model": ErrorResponse, "description": "Credenciales inválidas"}
    }
)
async def login(
    data: LoginRequest,
    supabase: Client = Depends(get_supabase)
):
    try:
        print(f"🔐 Login: {data.email}")
        
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
            response = supabase.table("users").select("*").eq("id", user_id).single().execute()
            user_profile = response.data
        except:
            user_profile = {
                "id": user_id,
                "email": user_email,
                "created_at": datetime.utcnow().isoformat()
            }
        
        # Generar tokens JWT
        access_token, access_expires = create_access_token(user_id, user_email)
        refresh_token, refresh_expires = create_refresh_token(user_id, user_email)
        
        user_response = UserResponse(
            id=user_id,
            email=user_email,
            full_name=user_profile.get("full_name"),
            phone=user_profile.get("phone"),
            avatar_url=user_profile.get("avatar_url"),
            created_at=user_profile.get("created_at")
        )
        
        print(f"✅ Login exitoso: {user_email}")
        
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
        
        if "invalid" in error_message.lower() or "credentials" in error_message.lower():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales inválidas"
            )
        
        print(f"❌ Error en login: {error_message}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al iniciar sesión"
        )


@router.post(
    "/refresh",
    response_model=AuthResponse,
    summary="Renovar token de acceso"
)
async def refresh_token(
    data: RefreshTokenRequest,
    supabase: Client = Depends(get_supabase)
):
    """Renueva el access token usando un refresh token válido."""
    try:
        payload = jwt.decode(
            data.refresh_token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        
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
                detail="Token inválido: información incompleta"
            )
        
        # Verificar que el usuario exista
        response = supabase.table("users").select("*").eq("id", user_id).single().execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no encontrado"
            )
        
        user_profile = response.data
        
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
            detail="Refresh token expirado. Inicia sesión nuevamente."
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido"
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error renovando token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Error al renovar token"
        )


@router.post(
    "/google",
    response_model=AuthResponse,
    summary="Iniciar sesión con Google"
)
async def google_auth(
    data: GoogleAuthRequest,
    supabase: Client = Depends(get_supabase)
):
    try:
        print(f"🔐 Login con Google")
        
        auth_response = supabase.auth.sign_in_with_id_token({
            "provider": "google",
            "token": data.id_token
        })
        
        if not auth_response.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token de Google inválido"
            )
        
        user_id = auth_response.user.id
        user_email = auth_response.user.email
        user_metadata = auth_response.user.user_metadata or {}
        
        full_name = user_metadata.get("full_name") or user_metadata.get("name")
        avatar_url = user_metadata.get("avatar_url") or user_metadata.get("picture")
        
        # Esperar a que el trigger cree el perfil
        await asyncio.sleep(0.3)
        
        # Obtener o actualizar perfil
        try:
            response = supabase.table("users").select("*").eq("id", user_id).single().execute()
            user_profile = response.data
            
            # Actualizar avatar si cambió
            if avatar_url and user_profile.get("avatar_url") != avatar_url:
                supabase.table("users").update({
                    "avatar_url": avatar_url,
                    "full_name": full_name or user_profile.get("full_name")
                }).eq("id", user_id).execute()
                user_profile["avatar_url"] = avatar_url
        except:
            user_profile = {
                "id": user_id,
                "email": user_email,
                "full_name": full_name,
                "avatar_url": avatar_url,
                "created_at": datetime.utcnow().isoformat()
            }
        
        # Generar tokens JWT
        access_token, access_expires = create_access_token(user_id, user_email)
        refresh_token, refresh_expires = create_refresh_token(user_id, user_email)
        
        user_response = UserResponse(
            id=user_id,
            email=user_email,
            full_name=user_profile.get("full_name"),
            phone=user_profile.get("phone"),
            avatar_url=user_profile.get("avatar_url"),
            created_at=user_profile.get("created_at")
        )
        
        print(f"✅ Login Google exitoso: {user_email}")
        
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
        print(f"❌ Error en Google login: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al autenticar con Google"
        )


@router.post("/logout", response_model=MessageResponse)
async def logout(user_id: str = Depends(get_current_user_id)):
    """Cierra la sesión del usuario."""
    return MessageResponse(message="Sesión cerrada exitosamente")


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: Dict = Depends(get_current_user)):
    """Obtiene información del usuario actual."""
    return UserResponse(
        id=current_user.get("id"),
        email=current_user.get("email"),
        full_name=current_user.get("full_name"),
        phone=current_user.get("phone"),
        avatar_url=current_user.get("avatar_url"),
        created_at=current_user.get("created_at")
    )


@router.get("/verify", response_model=MessageResponse)
async def verify_token(user_id: str = Depends(get_current_user_id)):
    """Verifica si el token es válido."""
    return MessageResponse(message=f"Token válido para el usuario {user_id}")


@router.put("/me", response_model=UserResponse)
async def update_profile(
    data: UpdateProfileRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """Actualiza el perfil del usuario."""
    try:
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