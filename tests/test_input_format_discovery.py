import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

def pretty_print_response(obj):
    """Imprime una representación estructurada y tipada del objeto SDK."""
    try:
        if hasattr(obj, "model_dump_json"):
            print(obj.model_dump_json(indent=2))
        elif hasattr(obj, "to_dict"):
            print(json.dumps(obj.to_dict(), indent=2, ensure_ascii=False))
        else:
            print(obj)
    except Exception as e:
        print(f"Error en volcado de datos: {e}")

def validate_canonical_input_formats():
    """
    Demuestra y valida las estructuras de input (contents) soportadas de forma
    nativa por el SDK google-genai, eliminando la necesidad de adivinar diccionarios.
    """
    print("--- VALIDACIÓN ARQUITECTÓNICA DE FORMATOS DE INPUT ---")

    # --- Configuración ---
    load_dotenv(dotenv_path="bot.env")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ ERROR CRÍTICO: GEMINI_API_KEY ausente en el entorno.")
        return

    try:
        client = genai.Client(api_key=api_key)
        model_name = "models/gemini-flash-lite-latest"
        print(f"Instanciando cliente para el modelo: {model_name}\n")

        # Prompt de control para minimizar el consumo de tokens en la prueba
        test_prompt = "Responde únicamente con la palabra 'Comprendido'."

        # -------------------------------------------------------------------
        # FORMATO 1: String Plano (Abstracción de Alto Nivel)
        # El SDK convierte automáticamente el string a types.Content.
        # -------------------------------------------------------------------
        print("▶ PRUEBA 1: Input como String Plano")
        response_1 = client.models.generate_content(
            model=model_name,
            contents=test_prompt
        )
        print(f"✅ Éxito [String]. Respuesta del modelo: {response_1.text}\n")

        # -------------------------------------------------------------------
        # FORMATO 2: Lista de Strings (Concatenación Automática)
        # Útil para inyectar múltiples partes de texto de forma secuencial.
        # -------------------------------------------------------------------
        print("▶ PRUEBA 2: Input como Lista de Strings")
        response_2 = client.models.generate_content(
            model=model_name,
            contents=[test_prompt, " (Asegúrate de que sea una sola palabra)."]
        )
        print(f"✅ Éxito [Lista]. Respuesta del modelo: {response_2.text}\n")

        # -------------------------------------------------------------------
        # FORMATO 3: Tipado Estricto (types.Content y types.Part)
        # Esta es la estructura base que intentabas emular con diccionarios.
        # Es mandatario usarlo cuando combinas texto con media (imágenes/audio)
        # o cuando defines roles específicos en el historial de chat.
        # -------------------------------------------------------------------
        print("▶ PRUEBA 3: Input con Tipado Estricto Pydantic")
        
        # Construcción determinista del objeto Content
        strict_content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=test_prompt)]
        )

        response_3 = client.models.generate_content(
            model=model_name,
            contents=strict_content
        )
        print(f"✅ Éxito [Tipado Estricto]. Respuesta del modelo: {response_3.text}\n")

        # Inspección del grafo de respuesta para el formato estricto
        print("--- Volcado de Estructura de Respuesta (Prueba 3) ---")
        pretty_print_response(response_3)

    except Exception as e:
        print(f"\n❌ Excepción de validación estructural: {type(e).__name__}: {e}")

if __name__ == "__main__":
    validate_canonical_input_formats()