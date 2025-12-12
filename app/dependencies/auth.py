"""
CronoPlan API - Auth Dependencies
Dependencias para validar tokens y obtener usuario actual
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import Client
from app.database import get_supabase
from typing import Optional, Dict
import jwt
from app.config import settings


# Security scheme para Swagger
security = HTTPBearer()


class AuthDependency:
    """Clase para manejar la autenticación"""
    
    @staticmethod
    def verify_token(token: str) -> Dict:
        """
        Verifica y decodifica un JWT token.
        
        Args:
            token: JWT token a verificar
            
        Returns:
            Dict con la información del payload del token
            
        Raises:
            HTTPException: Si el token es inválido o ha expirado
        """
        try:
            # Decodificar el token
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token ha expirado",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    @staticmethod
    async def get_current_user_id(
        credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> str:
        """
        Obtiene el ID del usuario actual desde el token.
        
        Args:
            credentials: Credenciales HTTP Bearer
            
        Returns:
            str: UUID del usuario
            
        Raises:
            HTTPException: Si el token es inválido
        """
        token = credentials.credentials
        
        try:
            # Primero intentar verificar con Supabase
            supabase = get_supabase()
            user = supabase.auth.get_user(token)
            
            if user and user.user:
                return user.user.id
            
            # Si Supabase no funciona, usar verificación local
            payload = AuthDependency.verify_token(token)
            user_id = payload.get("sub")
            
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="No se pudo obtener el ID del usuario",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            return user_id
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido o expirado",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    @staticmethod
    async def get_current_user(
        user_id: str = Depends(get_current_user_id),
        supabase: Client = Depends(get_supabase)
    ) -> Dict:
        """
        Obtiene la información completa del usuario actual.
        
        Args:
            user_id: ID del usuario (inyectado por get_current_user_id)
            supabase: Cliente de Supabase
            
        Returns:
            Dict con la información del usuario
            
        Raises:
            HTTPException: Si el usuario no existe
        """
        try:
            # Obtener datos del usuario desde la tabla users
            response = supabase.table("users").select("*").eq("id", user_id).single().execute()
            
            if not response.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Usuario no encontrado"
                )
            
            return response.data
            
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al obtener usuario: {str(e)}"
            )


# Crear instancia para usar como dependencia
auth_dependency = AuthDependency()

# Aliases para usar en los endpoints
get_current_user_id = auth_dependency.get_current_user_id
get_current_user = auth_dependency.get_current_user


# =====================================================
# DEPENDENCIAS OPCIONALES
# =====================================================

async def get_optional_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[str]:
    """
    Obtiene el user_id si hay token, sino retorna None.
    Útil para endpoints que funcionan con o sin autenticación.
    """
    if not credentials:
        return None
    
    try:
        return await get_current_user_id(credentials)
    except HTTPException:
        return None