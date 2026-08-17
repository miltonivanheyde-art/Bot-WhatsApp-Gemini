import os
from dotenv import load_dotenv
from google import genai


def descubrir_modelos_disponibles():
    """
    Script de diagnóstico para listar los modelos de Gemini accesibles
    con la clave de API actual, utilizando la arquitectura canónica y
    los atributos de objeto validados.
    """
    print("--- Iniciando descubrimiento de modelos de Gemini (versión corregida) ---")
 
    # Cargar la clave de API desde el entorno
    load_dotenv(dotenv_path="bot.env")
    api_key = os.getenv("GEMINI_API_KEY")
 
    if not api_key:
        print("❌ ERROR: La variable de entorno GEMINI_API_KEY no fue encontrada en 'bot.env'.")
        return

    try:
        client = genai.Client(api_key=api_key)
        print("✅ Cliente de Gemini instanciado correctamente.")

        print("\n--- Modelos de texto disponibles ('generateContent') ---")
        modelos_encontrados = 0
        for model in client.models.list():
            # Corrección: Se añade una guarda para asegurar que 'supported_actions' no es None
            # antes de verificar la pertenencia, evitando un TypeError.
            if model.supported_actions and 'generateContent' in model.supported_actions:
                print(f" -> {model.name}")
                modelos_encontrados += 1
        
        if modelos_encontrados == 0:
            print("No se encontraron modelos de texto compatibles.")

    except Exception as e:
        print(f"\n❌ Ocurrió un error durante el descubrimiento: {e}")

if __name__ == "__main__":
    descubrir_modelos_disponibles()