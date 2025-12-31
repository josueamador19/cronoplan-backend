from supabase import create_client, Client
from app.config import settings


class SupabaseClient:
    """
    Cliente de Supabase - Nueva instancia por request.
    """
    
    _service_client: Client = None
    
    @classmethod
    def get_service_client(cls) -> Client:
        """
        Retorna el cliente de Supabase con service role key.
        Este SÍ puede ser singleton porque solo hace operaciones admin.
        """
        if cls._service_client is None:
            cls._service_client = create_client(
                supabase_url=settings.SUPABASE_URL,
                supabase_key=settings.SUPABASE_SERVICE_KEY
            )
            # ✅ IMPORTANTE: Asegurar que no hay sesión activa
            try:
                cls._service_client.auth.sign_out()
            except:
                pass
        
        return cls._service_client


def get_supabase() -> Client:
    """
    Dependencia de FastAPI para obtener el cliente de Supabase.
    IMPORTANTE: Crea una NUEVA instancia por cada request para evitar
    conflictos de sesión cuando múltiples usuarios están autenticados.
    """
    return create_client(
        supabase_url=settings.SUPABASE_URL,
        supabase_key=settings.SUPABASE_ANON_KEY
    )


def get_service_supabase() -> Client:
    """
    Dependencia para obtener el cliente con service role.
    Solo usar cuando sea absolutamente necesario.
    
    IMPORTANTE: Siempre crea una NUEVA instancia para evitar
    contaminación de sesión entre requests.
    """
    # ✅ CREAR NUEVA INSTANCIA EN CADA REQUEST
    client = create_client(
        supabase_url=settings.SUPABASE_URL,
        supabase_key=settings.SUPABASE_SERVICE_KEY
    )
    
    # ✅ Asegurar que no hay sesión activa
    try:
        client.auth.sign_out()
    except:
        pass
    
    return client


async def test_connection() -> bool:
    """
    Prueba la conexión a Supabase.
    """
    try:
        client = get_supabase()
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