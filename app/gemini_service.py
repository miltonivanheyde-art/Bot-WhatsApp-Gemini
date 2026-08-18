import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from google import genai

# ==========================================================
# CONFIGURACIÓN
# ==========================================================

load_dotenv("bot.env")

DEFAULT_GEMINI_MODEL = "models/gemini-flash-lite-latest"
SYSTEM_PROMPT_PATH = "app/gemini_system_prompt.md"

API_KEY = os.getenv("GEMINI_API_KEY")

# ==========================================================
# CLIENTE
# ==========================================================

CLIENT = None
BASE_SYSTEM_INSTRUCTION = None

if API_KEY:
    CLIENT = genai.Client(api_key=API_KEY)
    try:
        with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
            BASE_SYSTEM_INSTRUCTION = f.read()
        print(f"[PROMPT] System instruction cargada desde: {SYSTEM_PROMPT_PATH}")
    except FileNotFoundError:
        print(f"[PROMPT WARNING] Archivo no encontrado: {SYSTEM_PROMPT_PATH}")
    except Exception as e:
        print(f"[PROMPT ERROR] {e}")


# ==========================================================
# GEMINI
# ==========================================================

def generar_respuesta_gemini(
    prompt: str,
    previous_interaction_id: str | None = None,
) -> tuple[str, str | None]:
    """
    Genera una respuesta utilizando la API Interactions.

    Args:
        prompt: Mensaje del usuario.
        previous_interaction_id:
            ID de interacción anterior para mantener memoria.

    Returns:
        (
            texto_respuesta,
            nuevo_interaction_id
        )
    """

    if not API_KEY:
        return ("Error: GEMINI_API_KEY no configurada.", None)

    if CLIENT is None:
        print("[GEMINI ERROR] Cliente Gemini no disponible.")
        return ("Error: El cliente de Gemini no está disponible.", None)

    try:
        print("🤖 Tita iA")
        print(f"Modelo: {DEFAULT_GEMINI_MODEL}")

        # La ID de interacción previa se utiliza para mantener la memoria, pero no se registra para mantener la consola limpia.

        # Inyección dinámica de la fecha y hora de Argentina en el prompt del sistema.
        final_system_instruction = BASE_SYSTEM_INSTRUCTION
        if final_system_instruction:
            tz_ar = timezone(timedelta(hours=-3))
            now_ar = datetime.now(tz_ar)
            datetime_ar_str = now_ar.strftime("%Y-%m-%d %H:%M:%S")
            final_system_instruction = final_system_instruction.replace(
                "{current_datetime_ar}", datetime_ar_str
            )

        # Llamada final y correcta a la API de Gemini.
        response = CLIENT.interactions.create(
            model=DEFAULT_GEMINI_MODEL,
            input=prompt,
            system_instruction=final_system_instruction,
            previous_interaction_id=previous_interaction_id,
            store=True,
        )

        interaction_id = getattr(response, "id", None)
        output_text = getattr(response, "output_text", None)

        print(f"Interaction: {interaction_id}\n")

        if not output_text:
            print("[GEMINI] output_text vacío.")
            return (
                "Error: Gemini devolvió una respuesta vacía.",
                interaction_id,
            )

        return (output_text, interaction_id)

    except Exception as e:
        print(f"❌ ERROR GEMINI: {type(e).__name__}: {e}")
        return (
            "Error: No se pudo generar una respuesta en este momento.",
            None,
        )
