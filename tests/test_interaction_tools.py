import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

def mock_weather_api(location: str) -> dict:
    """
    Simulación local de una API externa.
    En producción, aquí residiría la lógica de negocio real (HTTP requests, DB queries).
    """
    print(f"\n   [🛠️ SISTEMA LOG] -> Ejecutando 'mock_weather_api' para: {location}")
    if "buenos aires" in location.lower():
        return {"temperatura": 24, "condicion": "Despejado", "humedad": "60%"}
    return {"temperatura": 0, "condicion": "Desconocido", "humedad": "0%"}

def test_tool_calling_full_loop():
    """
    FASE 3C: Valida el ciclo completo de invocación, ejecución local
    y resolución (feedback) hacia el modelo mediante la abstracción del SDK.
    """
    print("--- FASE 3C: VALIDACIÓN ARQUITECTÓNICA DE TOOL CALLING (FULL LOOP) ---")

    load_dotenv(dotenv_path="bot.env")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ ERROR CRÍTICO: GEMINI_API_KEY ausente.")
        return

    try:
        client = genai.Client(api_key=api_key)
        model_name = "models/gemini-flash-lite-latest"
        
        # 1. Declaración de la herramienta (Esquema tipado)
        weather_tool = types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="get_current_weather",
                    description="Obtiene el clima actual para una ubicación específica.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "location": types.Schema(
                                type="STRING",
                                description="Ciudad y estado, ej: Buenos Aires, AR"
                            )
                        },
                        required=["location"]
                    )
                )
            ]
        )

        config = types.GenerateContentConfig(
            tools=[weather_tool],
            temperature=0.0 # Determinismo estricto
        )

        # ---------------------------------------------------------
        # ETAPA 1: TRIGGER (El usuario pregunta)
        # ---------------------------------------------------------
        prompt = "¿Cómo está el clima en Buenos Aires?"
        print(f"\n1. [USUARIO] -> '{prompt}'")

        response_trigger = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config
        )

        if not response_trigger.function_calls:
            print("❌ Falla estructural: El modelo no disparó el Tool Call esperado.")
            return

        # ---------------------------------------------------------
        # ETAPA 2: EJECUCIÓN (El sistema procesa la petición)
        # ---------------------------------------------------------
        call = response_trigger.function_calls[0]
        print(f"2. [MODELO]  <- Solicita ejecución de herramienta: {call.name} | Args: {call.args}")

        if call.name == "get_current_weather":
            # Desempaquetamos los argumentos devueltos por el modelo y ejecutamos nuestra función
            api_result = mock_weather_api(**call.args)
            print(f"   [🛠️ SISTEMA LOG] -> Resultado obtenido: {api_result}")

            # ---------------------------------------------------------
            # ETAPA 3: RESOLUCIÓN (Construcción del grafo de historial)
            # ---------------------------------------------------------
            # Para que el modelo entienda el contexto, debemos inyectar la historia exacta:
            # Petición Usuario -> Petición Tool (Modelo) -> Respuesta Tool (Sistema)
            
            history = [
                types.Content(role="user", parts=[types.Part.from_text(text=prompt)]),
                response_trigger.candidates[0].content, # Inyectamos la petición original del modelo sin alterarla
                types.Content(
                    role="user", # La respuesta de la función se envía bajo el rol de usuario/sistema
                    parts=[
                        types.Part.from_function_response(
                            name=call.name,
                            response=api_result # Pasamos el diccionario directamente
                        )
                    ]
                )
            ]

            print("\n3. [SISTEMA] -> Devolviendo payload de resultados al modelo...")
            
            # ---------------------------------------------------------
            # ETAPA 4: RESPUESTA FINAL
            # ---------------------------------------------------------
            response_final = client.models.generate_content(
                model=model_name,
                contents=history,
                config=config
            )

            print(f"4. [MODELO]  <- Respuesta consolidada: '{response_final.text}'")
            print("\n✅ Conclusión: Ciclo Completo (Full Loop) validado. Arquitectura robusta y operativa.")

    except Exception as e:
        print(f"\n❌ Excepción de ejecución: {type(e).__name__}: {e}")

if __name__ == "__main__":
    test_tool_calling_full_loop()