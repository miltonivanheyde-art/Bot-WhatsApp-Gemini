import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types

def test_rag_grounding_full_loop():
    """
    FASE 4A: Valida el ciclo completo de Grounding/RAG.
    Diseño consolidado y de bajo consumo: Sin persistencia de almacenes innecesarios.
    El contexto se inyecta dinámicamente en el array de contenidos.
    """
    print("--- FASE 4A: VALIDACIÓN ARQUITECTÓNICA DE GROUNDING / RAG ---")

    # --- 1. Generación de Artefacto Local ---
    file_content = "La capital secreta del Proyecto Centinela es Valle Verde."
    file_name = "DOCUMENTO_PRUEBA.txt"
    
    with open(file_name, "w", encoding="utf-8") as f:
        f.write(file_content)
    print(f"1. Artefacto local '{file_name}' generado.")

    load_dotenv(dotenv_path="bot.env")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ ERROR CRÍTICO: GEMINI_API_KEY ausente en el entorno.")
        os.remove(file_name)
        return

    try:
        client = genai.Client(api_key=api_key)
        model_name = "models/gemini-flash-lite-latest"
        uploaded_file = None

        # --- 2. Ingesta a la Nube (API de Archivos) ---
        print("\n2. Transfiriendo artefacto al entorno de Gemini...")
        # El SDK actual requiere client.files.upload() para transferir archivos locales
        uploaded_file = client.files.upload(
            file=file_name, 
            config={'display_name': 'Documento Centinela'}
        )
        print(f"   -> Archivo transferido. Identificador unívoco: {uploaded_file.name}")

        # Polling de validación de estado (Resiliencia)
        while uploaded_file.state.name == 'PROCESSING':
            print(f"   -> Estado de indexación: {uploaded_file.state.name}. Aguardando resolución...")
            time.sleep(2) # Reducción del delay para optimizar tiempos de prueba
            uploaded_file = client.files.get(name=uploaded_file.name)
        
        if uploaded_file.state.name == 'FAILED':
            raise Exception("El procesamiento del documento falló en los servidores de Google.")
            
        print(f"   -> Estado de indexación: {uploaded_file.state.name}. Listo para inferencia.")

        # --- 3. Validación de Inferencia (General vs. Inyectada) ---
        print("\n3. Ejecutando pruebas de asilamiento y grounding...")
        
        # Test A: Conocimiento General Absoluto (Sin contexto)
        prompt_a = "¿Cuál es la capital de Francia?"
        print(f"   [Test A - General] -> '{prompt_a}'")
        response_a = client.models.generate_content(
            model=model_name, 
            contents=prompt_a,
            config=types.GenerateContentConfig(temperature=0.0) # Determinismo
        )
        print(f"   [Respuesta A]      <- '{response_a.text}'")

        # Test B: RAG Estricto (Contexto Inyectado)
        prompt_b = "¿Cuál es la capital secreta del Proyecto Centinela?"
        print(f"   [Test B - RAG]     -> '{prompt_b}'")
        # Inyección directa del objeto de archivo como parte del payload multimodal
        response_b = client.models.generate_content(
            model=model_name, 
            contents=[uploaded_file, prompt_b],
            config=types.GenerateContentConfig(temperature=0.0)
        )
        print(f"   [Respuesta B]      <- '{response_b.text}'")

        # --- 4. Conclusión Analítica ---
        print("\n--- Dictamen de Auditoría ---")
        if "parís" in response_a.text.lower() and "valle verde" in response_b.text.lower():
            print("✅ Estado: Operativo. El modelo resolvió exitosamente las consultas segmentando el conocimiento pre-entrenado del contexto inyectado de forma dinámica.")
            print("Clasificación final: Grounding / RAG: ✅ Validado")
        else:
            print("❌ Estado: Falla Crítica. El modelo presentó alucinaciones o no logró integrar el documento base.")
            print("Clasificación final: Grounding / RAG: ❌ No Validado")

    except Exception as e:
        print(f"\n❌ Excepción no controlada durante el pipeline: {type(e).__name__}: {e}")
        print("Clasificación final: Grounding / RAG: ⚠️ Fallo de Entorno")

    finally:
        # --- 5. Purga de Recursos (Protección contra fugas de datos y sobrecostos) ---
        print("\n4. Iniciando protocolo de limpieza y desvinculación de recursos...")
        if uploaded_file:
            try:
                client.files.delete(name=uploaded_file.name)
                print(f"   -> Artefacto remoto '{uploaded_file.name}' purgado del entorno.")
            except Exception as e:
                 print(f"   -> ⚠️ Advertencia: Fallo al purgar archivo remoto: {e}")
                 
        if os.path.exists(file_name):
            os.remove(file_name)
            print(f"   -> Artefacto local '{file_name}' eliminado.")
            
        print("   -> Protocolo de limpieza finalizado con éxito.")

if __name__ == "__main__":
    test_rag_grounding_full_loop()