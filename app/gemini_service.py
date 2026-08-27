import os
from datetime import datetime, timezone, timedelta
import json
from dotenv import load_dotenv
from google import genai
from .calendar_service import AnsesCalendarService

# ==========================================================
# CONFIGURACIÓN
# ==========================================================

load_dotenv("bot.env")

DEFAULT_GEMINI_MODEL = "models/gemini-flash-lite-latest"
SYSTEM_PROMPT_PATH = "app/gemini_system_prompt.md"
KNOWLEDGE_BASE_PATH = "app/knowledge_base.md"
FORMS_CATALOG_PATH = "app/formularios_oficiales.json"
PRIVACY_POLICY_PATH = "app/politica_de_privacidad.md"

API_KEY = os.getenv("GEMINI_API_KEY")

# ==========================================================
# CLIENTE
# ==========================================================

CLIENT = None
BASE_SYSTEM_INSTRUCTION = None
KNOWLEDGE_BASE_CONTENT = None
FORMS_CATALOG_CONTENT = None
PRIVACY_POLICY_CONTENT = None
CALENDAR_SERVICE = AnsesCalendarService()

def _load_resource(file_path: str, is_json: bool = False):
    """Helper to load a text or JSON resource file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = json.load(f) if is_json else f.read()
        print(f"[GEMINI SERVICE] Recurso cargado desde: {file_path}")
        return content
    except FileNotFoundError:
        print(f"[GEMINI SERVICE WARNING] Archivo no encontrado: {file_path}")
    except json.JSONDecodeError as e:
        print(f"[GEMINI SERVICE ERROR] Error de formato JSON en {file_path}: {e}")
    except Exception as e:
        print(f"[GEMINI SERVICE ERROR] Error al cargar {file_path}: {e}")
    return None

if API_KEY:
    CLIENT = genai.Client(api_key=API_KEY)
    BASE_SYSTEM_INSTRUCTION = _load_resource(SYSTEM_PROMPT_PATH)
    KNOWLEDGE_BASE_CONTENT = _load_resource(KNOWLEDGE_BASE_PATH)
    FORMS_CATALOG_CONTENT = _load_resource(FORMS_CATALOG_PATH, is_json=True)
    PRIVACY_POLICY_CONTENT = _load_resource(PRIVACY_POLICY_PATH)

# ==========================================================
# GEMINI
# ==========================================================

def generar_respuesta_gemini(
    prompt: str,
    previous_interaction_id: str | None = None,
    user_name: str | None = None,
) -> tuple[str, str | None]:
    """
    Genera una respuesta utilizando la API Interactions.

    Args:
        prompt: Mensaje del usuario.
        previous_interaction_id:
            ID de interacción anterior para mantener memoria.
        user_name: Nombre del usuario para personalizar la conversación.

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
        final_system_instruction = BASE_SYSTEM_INSTRUCTION or ""
        if final_system_instruction:
            tz_ar = timezone(timedelta(hours=-3))
            now_ar = datetime.now(tz_ar)
            datetime_ar_str = now_ar.strftime("%Y-%m-%d %H:%M:%S")
            final_system_instruction = final_system_instruction.replace(
                "{current_datetime_ar}", datetime_ar_str
            )
            # Inyección del nombre del usuario
            final_system_instruction = final_system_instruction.replace(
                "{user_name}", user_name if user_name else "ciudadano/a"
            )

        # Inyección de la base de conocimiento institucional
        if KNOWLEDGE_BASE_CONTENT:
            final_system_instruction += "\n\n[INICIO DATOS INSTITUCIONALES VERIFICADOS]\n"
            final_system_instruction += KNOWLEDGE_BASE_CONTENT
            final_system_instruction += "\n[FIN DATOS INSTITUCIONALES VERIFICADOS]\n"

        # Inyección del catálogo de formularios oficiales
        if FORMS_CATALOG_CONTENT:
            final_system_instruction += "\n\n[INICIO CATÁLOGO DE FORMULARIOS OFICIALES]\n"
            final_system_instruction += json.dumps(FORMS_CATALOG_CONTENT, indent=2, ensure_ascii=False)
            final_system_instruction += "\n[FIN CATÁLOGO DE FORMULARIOS OFICIALES]\n"

        # Inyección separada del calendario del mes actual y del siguiente
        payment_schedules = CALENDAR_SERVICE.get_payment_schedules()
        if payment_schedules:
            final_system_instruction += "\n\n[INICIO CALENDARIOS DE PAGOS]\n"
            final_system_instruction += json.dumps(payment_schedules, indent=2, ensure_ascii=False)
            final_system_instruction += "\n[FIN CALENDARIOS DE PAGOS]\n"

        # Inyección de la política de privacidad
        if PRIVACY_POLICY_CONTENT:
            final_system_instruction += "\n\n[INICIO POLÍTICA DE PRIVACIDAD]\n"
            final_system_instruction += PRIVACY_POLICY_CONTENT
            final_system_instruction += "\n[FIN POLÍTICA DE PRIVACIDAD]\n"

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
