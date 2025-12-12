from supabase import create_client, Client
from app.config import settings
from functools import lru_cache


class SupabaseClient:
    """
    Cliente de Supabase singleton.
    Maneja la conexión y proporciona acceso a la base de datos.
    """
    
    _client: Client = None
    _service_client: Client = None
    
    @classmethod
    def get_client(cls) -> Client:
        """
        Retorna el cliente de Supabase con anon key.

        """
        if cls._client is None:
            cls._client = create_client(
                supabase_url=settings.SUPABASE_URL,
                supabase_key=settings.SUPABASE_ANON_KEY
            )
        return cls._client
    
    @classmethod
    def get_service_client(cls) -> Client:
        """
        Retorna el cliente de Supabase con service role key.
        """
        if cls._service_client is None:
            cls._service_client = create_client(
                supabase_url=settings.SUPABASE_URL,
                supabase_key=settings.SUPABASE_SERVICE_KEY
            )
        return cls._service_client


@lru_cache()
def get_supabase() -> Client:
    """
    Dependencia de FastAPI para obtener el cliente de Supabase.
    Usar en endpoints como dependencia.
    
    Ejemplo:
        @app.get("/tasks")
        def get_tasks(supabase: Client = Depends(get_supabase)):
            ...
    """
    return SupabaseClient.get_client()


def get_service_supabase() -> Client:
    """
    Dependencia para obtener el cliente con service role.
    Solo usar cuando sea absolutamente necesario.
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
        print("Conexión a Supabase exitosa")
        return True
    except Exception as e:
        print(f"Error conectando a Supabase: {e}")
        return False


if __name__ == "__main__":
    import asyncio
    print("=== Probando conexión a Supabase ===")
    asyncio.run(test_connection())