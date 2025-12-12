"""
CronoPlan API - Main Application
Punto de entrada de la aplicación FastAPI
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
from app.database import test_connection
import uvicorn


# Crear instancia de FastAPI
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.DESCRIPTION,
    version=settings.VERSION,
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json"
)


# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================================================
# EVENT HANDLERS
# =====================================================

@app.on_event("startup")
async def startup_event():
    """
    Se ejecuta al iniciar la aplicación.
    Verifica la conexión a Supabase.
    """
    print("\n" + "="*50)
    print(f"🚀 Iniciando {settings.PROJECT_NAME}")
    print(f"📦 Versión: {settings.VERSION}")
    print(f"🌍 Entorno: {settings.ENVIRONMENT}")
    print("="*50 + "\n")
    
    # Probar conexión a Supabase
    await test_connection()
    
    print("\n✅ Aplicación iniciada correctamente")
    print(f"📝 Documentación: http://localhost:8000{settings.API_V1_PREFIX}/docs")
    print("="*50 + "\n")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Se ejecuta al cerrar la aplicación.
    """
    print("\n👋 Cerrando aplicación...")


# =====================================================
# ROOT ENDPOINTS
# =====================================================

@app.get("/")
async def root():
    """
    Endpoint raíz - información de la API
    """
    return {
        "message": "CronoPlan API",
        "version": settings.VERSION,
        "status": "running",
        "docs": f"{settings.API_V1_PREFIX}/docs"
    }


@app.get("/health")
async def health_check():
    """
    Endpoint de salud - verificar que la API está funcionando
    """
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "version": settings.VERSION
    }


@app.get(f"{settings.API_V1_PREFIX}/")
async def api_root():
    """
    Endpoint raíz de la API v1
    """
    return {
        "message": "CronoPlan API v1",
        "endpoints": {
            "auth": f"{settings.API_V1_PREFIX}/auth",
            "users": f"{settings.API_V1_PREFIX}/users",
            "boards": f"{settings.API_V1_PREFIX}/boards",
            "tasks": f"{settings.API_V1_PREFIX}/tasks",
            "labels": f"{settings.API_V1_PREFIX}/labels"
        },
        "documentation": f"{settings.API_V1_PREFIX}/docs"
    }


# =====================================================
# INCLUIR ROUTERS
# =====================================================

from app.routers import auth

# Auth Router
app.include_router(
    auth.router, 
    prefix=f"{settings.API_V1_PREFIX}/auth", 
    tags=["🔐 Autenticación"]
)

# Próximos routers (descomentar cuando se creen):
# from app.routers import users, boards, tasks, labels
# app.include_router(users.router, prefix=f"{settings.API_V1_PREFIX}/users", tags=["👤 Usuarios"])
# app.include_router(boards.router, prefix=f"{settings.API_V1_PREFIX}/boards", tags=["📋 Tableros"])
# app.include_router(tasks.router, prefix=f"{settings.API_V1_PREFIX}/tasks", tags=["✅ Tareas"])
# app.include_router(labels.router, prefix=f"{settings.API_V1_PREFIX}/labels", tags=["🏷️ Etiquetas"])


# =====================================================
# EXCEPTION HANDLERS
# =====================================================

@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Maneja errores 404"""
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": "El recurso solicitado no existe",
            "path": str(request.url)
        }
    )


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """Maneja errores 500"""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "Ha ocurrido un error interno en el servidor"
        }
    )


# =====================================================
# EJECUTAR APLICACIÓN
# =====================================================

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG  # Hot reload en modo desarrollo
    )