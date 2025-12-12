"""
CronoPlan API - Configuración
Manejo de variables de entorno y configuración global
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    """
    Configuración de la aplicación.
    Lee las variables de entorno del archivo .env
    """
    
    # Supabase
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_KEY: str
    
    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 días
    
    # API
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "CronoPlan API"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "API para gestión de tareas y productividad"
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Convierte el string de CORS_ORIGINS en una lista"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """
    Retorna la configuración cacheada.
    Se carga solo una vez y se reutiliza.
    """
    return Settings()


# Instancia global de configuración
settings = get_settings()


# Para debugging - imprimir configuración al iniciar
if __name__ == "__main__":
    print("=== CronoPlan Configuration ===")
    print(f"Project: {settings.PROJECT_NAME}")
    print(f"Version: {settings.VERSION}")
    print(f"Environment: {settings.ENVIRONMENT}")
    print(f"API Prefix: {settings.API_V1_PREFIX}")
    print(f"Supabase URL: {settings.SUPABASE_URL}")
    print(f"CORS Origins: {settings.cors_origins_list}")
    print("=" * 30)