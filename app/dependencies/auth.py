from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import Client
from app.database import get_supabase
from typing import Optional, Dict
import jwt
from app.config import settings


security = HTTPBearer()


class AuthDependency:

    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> Dict:
        """
        Verifica y decodifica un JWT token.
        """
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            
            token_type_in_payload = payload.get("type")
            
            if token_type_in_payload != token_type:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Token inválido: se esperaba un {token_type} token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            if not payload.get("sub"):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token inválido: información de usuario incompleta",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tu sesión ha expirado. Por favor, inicia sesión nuevamente.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de autenticación inválido. Por favor, inicia sesión.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    @staticmethod
    async def get_current_user_id(
        credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> str:
        """
        Obtiene el ID del usuario actual desde el token.
        """
        token = credentials.credentials
        
        try:
            payload = AuthDependency.verify_token(token, token_type="access")
            user_id = payload.get("sub")
            
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="No se pudo identificar al usuario. Por favor, inicia sesión.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            return user_id
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No se pudo validar las credenciales. Por favor, inicia sesión.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    @staticmethod
    async def get_current_user(
        user_id: str = Depends(get_current_user_id),
        supabase: Client = Depends(get_supabase)
    ) -> Dict:
        """
        Obtiene la información completa del usuario actual.
        """
        try:
            response = supabase.table("users").select("*").eq("id", user_id).single().execute()
            
            if not response.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Usuario no encontrado. Es posible que tu cuenta haya sido eliminada."
                )
            
            return response.data
            
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            print(f"❌ Error al obtener usuario: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al obtener información del usuario"
            )


auth_dependency = AuthDependency()

get_current_user_id = auth_dependency.get_current_user_id
get_current_user = auth_dependency.get_current_user


async def get_optional_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[str]:
    """
    Obtiene el user_id si hay token, sino retorna None.
    """
    if not credentials:
        return None
    
    try:
        return await get_current_user_id(credentials)
    except HTTPException:
        return None