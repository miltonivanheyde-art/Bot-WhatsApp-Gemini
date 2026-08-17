import os
from dotenv import load_dotenv
from google import genai

def audit_interactions_api():
    """
    Script de diagnóstico para auditar la API `client.interactions` del SDK de Gemini,
    determinando su existencia, métodos y documentación.
    """
    print("--- INICIANDO AUDITORÍA DE INTERACTIONS API ---")

    # 1. Cargar la clave de API desde el entorno.
    load_dotenv(dotenv_path="bot.env")
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        print("❌ ERROR: La variable de entorno GEMINI_API_KEY no fue encontrada en 'bot.env'.")
        return

    try:
        # 2. Instanciar el cliente canónico, cuya funcionalidad ya fue validada.
        client = genai.Client(api_key=api_key)
        print("✅ Cliente de Gemini instanciado correctamente.")

        # 3. Auditar la existencia del atributo 'interactions'.
        print("\n--- AUDITORÍA DE 'client.interactions' ---")
        if hasattr(client, 'interactions'):
            print("✅ Atributo 'client.interactions' ENCONTRADO.")
            
            # 4. Introspección con dir() para listar métodos y atributos.
            print("\n--- dir(client.interactions) ---")
            interactions_attrs = dir(client.interactions)
            for attr in interactions_attrs:
                # Filtrar los atributos "mágicos" para mayor claridad.
                if not attr.startswith('_'):
                    print(f" -> {attr}")
            
            # 5. Introspección con help() para obtener la documentación oficial del SDK.
            print("\n--- help(client.interactions) ---")
            help(client.interactions)

        else:
            print("❌ Atributo 'client.interactions' NO ENCONTRADO.")

    except Exception as e:
        print(f"\n❌ Ocurrió un error durante la auditoría: {type(e).__name__}: {e}")

if __name__ == "__main__":
    audit_interactions_api()