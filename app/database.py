from supabase import create_client, Client
from app.config import settings


class SupabaseClient:
    """
    Cliente de Supabase - ahora sin singleton para Auth.
    Cada request obtiene su propia instancia para evitar conflictos de sesión.
    """
    
    # Mantener singleton solo para el service client (operaciones admin)
    _service_client: Client = None
    
    @classmethod
    def get_service_client(cls) -> Client:
        """
        Retorna el cliente de Supabase con service role key.
        Este SÍ puede ser singleton porque no maneja auth de usuarios.
        """
        if cls._service_client is None:
            cls._service_client = create_client(
                supabase_url=settings.SUPABASE_URL,
                supabase_key=settings.SUPABASE_SERVICE_KEY
            )
        return cls._service_client


def get_supabase() -> Client:
    """
    Dependencia de FastAPI para obtener el cliente de Supabase.
    IMPORTANTE: Crea una NUEVA instancia por cada request para evitar
    conflictos de sesión cuando múltiples usuarios están autenticados.
    
    Ejemplo:
        @app.get("/tasks")
        def get_tasks(supabase: Client = Depends(get_supabase)):
            ...
    """
    # ✅ NUEVA INSTANCIA POR REQUEST - Evita conflictos de sesión
    return create_client(
        supabase_url=settings.SUPABASE_URL,
        supabase_key=settings.SUPABASE_ANON_KEY
    )


def get_service_supabase() -> Client:
    """
    Dependencia para obtener el cliente con service role.
    Solo usar cuando sea absolutamente necesario.
    Este SÍ puede ser singleton porque solo hace operaciones admin.
    """
    return SupabaseClient.get_service_client()


# Para testing - verificar conexión
async def test_connection() -> bool:
    """
    Prueba la conexión a Supabase.
    Retorna True si la conexión es exitosa.
    """
    try:
        client = get_supabase()
        # Intenta hacer una query simple
        response = client.table('users').select("id").limit(1).execute()
        print("✅ Conexión a Supabase exitosa")
        return True
    except Exception as e:
        print(f"❌ Error conectando a Supabase: {e}")
        return False


if __name__ == "__main__":
    import asyncio
    print("=== Probando conexión a Supabase ===")
    asyncio.run(test_connection())