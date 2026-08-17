import os

from dotenv import load_dotenv
from google import genai

# ==========================================================
# CONFIGURACIÓN
# ==========================================================

load_dotenv("bot.env")

DEFAULT_GEMINI_MODEL = "models/gemini-flash-lite-latest"

API_KEY = os.getenv("GEMINI_API_KEY")

# ==========================================================
# CLIENTE
# ==========================================================

CLIENT = None

if API_KEY:
    CLIENT = genai.Client(api_key=API_KEY)

# ==========================================================
# GEMINI
# ==========================================================

def generar_respuesta_gemini(prompt: str) -> str:
    """
    Genera una respuesta utilizando Gemini.
    """

    if not API_KEY:
        return "Error: GEMINI_API_KEY no configurada."

    if CLIENT is None:
        print("[GEMINI ERROR] El cliente de Gemini no fue inicializado correctamente. Verifique la clave API y la conexión.")
        return "Error: El cliente de Gemini no está disponible."

    try:

        print(f"[GEMINI] Modelo: {DEFAULT_GEMINI_MODEL}")

        response = CLIENT.models.generate_content(
            model=DEFAULT_GEMINI_MODEL,
            contents=prompt
        )

        # --------------------------------------------------
        # DIAGNÓSTICO
        # --------------------------------------------------

        print(f"[GEMINI] Tipo respuesta: {type(response)}")

        if not hasattr(response, "text"):
            print("[GEMINI] La respuesta no contiene atributo text")
            print(response)

            return (
                "Error: Gemini devolvió una respuesta "
                "sin contenido textual."
            )

        if not response.text:
            print("[GEMINI] response.text vacío")
            print(dir(response))
            print(response)

            return (
                "Error: Gemini devolvió una respuesta vacía."
            )

        return response.text

    except Exception as e:

        print(
            f"[GEMINI ERROR] "
            f"{type(e).__name__}: {e}"
        )

        return (
            "Error: No se pudo generar una respuesta "
            "en este momento."
        )