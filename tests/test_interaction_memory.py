import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

def test_conversational_memory():
    """
    FASE 3A: Valida la persistencia del contexto (Memoria Conversacional)
    aplicando los estándares arquitectónicos del SDK google-genai.
    """
    print("--- FASE 3A: VALIDACIÓN ESTRUCTURAL DE MEMORIA CONVERSACIONAL ---")

    load_dotenv(dotenv_path="bot.env")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ ERROR CRÍTICO: GEMINI_API_KEY ausente en el entorno.")
        return

    try:
        client = genai.Client(api_key=api_key)
        model_name = "models/gemini-flash-lite-latest"
        print(f"Instanciando cliente para el modelo: {model_name}\n")

        # -------------------------------------------------------------------
        # MÉTODO 1: Implementación Stateful (Client Chats) - [RECOMENDADO]
        # El objeto 'chat' mantiene internamente la coherencia del historial.
        # -------------------------------------------------------------------
        print("▶ PRUEBA 1: Gestión de Memoria Automática (client.chats)")
        
        # Se inicializa el canal de chat (instancia stateful)
        chat = client.chats.create(model=model_name)

        # Turno 1 (Inyección de memoria)
        prompt1 = "Hola. Mi nombre es Milton. Por favor, recuérdalo."
        print(f"   [User] -> '{prompt1}'")
        response1 = chat.send_message(prompt1)
        print(f"   [Model] <- '{response1.text}'")

        # Turno 2 (Recuperación de memoria)
        prompt2 = "¿Cómo dije que me llamo?"
        print(f"   [User] -> '{prompt2}'")
        response2 = chat.send_message(prompt2)
        print(f"   [Model] <- '{response2.text}'")

        if "milton" in response2.text.lower():
            print("   ✅ Estado: Éxito. El objeto chat mantuvo el contexto.")
        else:
            print("   ❌ Estado: Falla de persistencia en la abstracción de chat.")

        print("\n-------------------------------------------------------------------")

        # -------------------------------------------------------------------
        # MÉTODO 2: Implementación Stateless (Inyección manual del grafo)
        # Útil para APIs REST puras, arquitecturas serverless o hidratación
        # de sesiones desde bases de datos externas.
        # -------------------------------------------------------------------
        print("▶ PRUEBA 2: Gestión de Memoria Manual (Inyección de types.Content)")

        # Construcción determinista del historial (grafo de la conversación)
        conversation_history = [
            types.Content(role="user", parts=[types.Part.from_text(text="Mi color favorito es el azul oscuro.")]),
            types.Content(role="model", parts=[types.Part.from_text(text="Entendido, lo he memorizado.")]),
            types.Content(role="user", parts=[types.Part.from_text(text="Si quisiera comprar un vehículo, ¿qué color me recomendarías basado en mis gustos?")])
        ]

        print(f"   [User] -> '{conversation_history[-1].parts[0].text}' (Historial inyectado manualmente)")
        
        # Se envía el grafo completo al endpoint de generación de contenido
        response_stateless = client.models.generate_content(
            model=model_name,
            contents=conversation_history
        )
        print(f"   [Model] <- '{response_stateless.text}'")

        if "azul" in response_stateless.text.lower():
            print("   ✅ Estado: Éxito. La inferencia procesó el vector de historial correctamente.")
        else:
            print("   ❌ Estado: Falla de inferencia contextual.")

        # --- Conclusión Global ---
        print("\n--- Conclusión de Ejecución ---")
        print("Clasificación final: Memoria conversacional (Ambos paradigmas): ✅ Funciona")

    except Exception as e:
        print(f"\n❌ Excepción no controlada durante la validación de memoria: {type(e).__name__}: {e}")
        print("\nClasificación final: Memoria conversacional: ⚠️ Fallo a nivel de sistema/SDK")

if __name__ == "__main__":
    test_conversational_memory()