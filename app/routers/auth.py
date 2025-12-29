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
    Crea el perfil del usuario en la tabla users con retry logic y exponential backoff.
    Esto previene race conditions cuando múltiples usuarios hacen requests simultáneos.
    """
    max_retries = 5
    retry_delay = 0.3  # Empezar con 300ms
    
    for attempt in range(max_retries):
        try:
            user_data = {
                "id": user_id,
                "full_name": full_name,
                "phone": phone,
                "avatar_url": avatar_url
            }
            
            #print(f"Intento {attempt + 1}/{max_retries} - Creando perfil para {email}")
            
            response = supabase.table("users").insert(user_data).execute()
            
            if response.data:
                #print(f"Perfil creado exitosamente para {email}")
                return response.data[0]
            else:
                #print(f"Respuesta vacía, retornando datos básicos")
                return {**user_data, "email": email, "created_at": datetime.utcnow().isoformat()}
        
        except Exception as e:
            error_msg = str(e)
            
            # Si es el último intento, retornar datos básicos
            if attempt == max_retries - 1:
                #print(f"Error después de {max_retries} intentos: {error_msg}")
                #print(f"Retornando datos básicos para continuar el flujo")
                return {
                    "id": user_id,
                    "email": email,
                    "full_name": full_name,
                    "phone": phone,
                    "avatar_url": avatar_url,
                    "created_at": datetime.utcnow().isoformat()
                }
            
            # Si no es el último intento, esperar y reintentar
            #print(f"Intento {attempt + 1} falló: {error_msg}")
            #print(f"Reintentando en {retry_delay}s...")
            await asyncio.sleep(retry_delay)
            retry_delay *= 2  # Exponential backoff: 0.3s -> 0.6s -> 1.2s -> 2.4s


async def get_or_create_user_profile(supabase: Client, user_id: str, email: str, full_name: str = None, phone: str = None, avatar_url: str = None) -> Dict:
    """
    Intenta obtener el perfil del usuario, si no existe lo crea.
    Útil para login donde el perfil debería existir pero podría no existir por errores previos.
    """
    max_retries = 3
    retry_delay = 0.2
    
    for attempt in range(max_retries):
        try:
            # Intentar obtener el perfil existente
            profile_response = supabase.table("users").select("*").eq("id", user_id).single().execute()
            
            if profile_response.data:
                return profile_response.data
            else:
                # Si no existe, crearlo
                #print(f"Perfil no encontrado, creando uno nuevo...")
                return await create_user_profile(supabase, user_id, email, full_name, phone, avatar_url)
        
        except Exception as e:
            error_msg = str(e).lower()
            
            # Si el error es porque no existe el registro, crear el perfil
            if "no rows" in error_msg or "not found" in error_msg:
                #print(f"Perfil no existe, creando...")
                return await create_user_profile(supabase, user_id, email, full_name, phone, avatar_url)
            
            # Para otros errores, reintentar
            if attempt < max_retries - 1:
                #print(f"Error obteniendo perfil, reintentando en {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
            else:
                # En el último intento, retornar datos básicos
                #print(f"No se pudo obtener/crear perfil, retornando datos básicos")
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
        #print(f"Intentando registrar usuario: {data.email}")
        
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
        
        #print(f"Usuario creado en Supabase Auth: {user_email}")
        
        # Pequeño delay para evitar race condition con Supabase
        await asyncio.sleep(0.1)
        
        # Crear perfil en la tabla users con retry logic
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
        
        #print(f"Registro completado exitosamente para: {user_email}")
        
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
        
        #print(f"Error en registro: {error_message}")
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
        #print(f"Intento de login: {data.email}")
        
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
        
        #print(f"Login exitoso en Supabase Auth: {user_email}")
        
        # Obtener o crear perfil del usuario con retry logic
        user_profile = await get_or_create_user_profile(
            supabase=supabase,
            user_id=user_id,
            email=user_email
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
        
        #print(f"Login completado para: {user_email}")
        
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
        
        print(f"Error en login: {error_message}")
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
        
        # Verificar que el usuario aún exista con retry logic
        user_profile = await get_or_create_user_profile(
            supabase=supabase,
            user_id=user_id,
            email=email
        )
        
        if not user_profile:
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
        #print(f"Intento de login con Google")
        
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
        
        #print(f"Login con Google exitoso para: {user_email}")
        
        # Pequeño delay
        await asyncio.sleep(0.1)
        
        # Obtener o crear perfil con retry logic
        user_profile = await get_or_create_user_profile(
            supabase=supabase,
            user_id=user_id,
            email=user_email,
            full_name=full_name,
            avatar_url=avatar_url
        )
        
        # Si el perfil ya existía, actualizar avatar si es necesario
        if user_profile.get("id") and avatar_url and user_profile.get("avatar_url") != avatar_url:
            try:
                update_response = supabase.table("users").update({
                    "avatar_url": avatar_url,
                    "full_name": full_name or user_profile.get("full_name")
                }).eq("id", user_id).execute()
                
                if update_response.data:
                    user_profile = update_response.data[0]
            except Exception as update_error:
                print(f" No se pudo actualizar avatar: {update_error}")
        
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
        #print(f" Error en login con Google: {error_message}")
        
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