import os
import json
from fastapi import FastAPI, Request, Response, status
import sys
import requests
from dotenv import load_dotenv
# Cargar variables de entorno desde el archivo bot.env

from app.gemini_service import generar_respuesta_gemini
from app.knowledge_service import KnowledgeService, KnowledgeStatus, ValidatedKnowledge

load_dotenv(dotenv_path="bot.env")

# Variables desde .env
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

DEBUG_WEBHOOK = False

app = FastAPI()

# Crear una única instancia del servicio de conocimiento
knowledge_service = KnowledgeService(db_path="data/tita.db")

# Almacenamiento en memoria para el estado de la conversación.
CONVERSATION_STATE = {}
STATE_FILE_PATH = "state.json"

def _load_state():
    """Carga el estado de las conversaciones desde un archivo JSON al iniciar."""
    global CONVERSATION_STATE
    try:
        if os.path.exists(STATE_FILE_PATH):
            with open(STATE_FILE_PATH, "r", encoding="utf-8") as f:
                CONVERSATION_STATE = json.load(f)
            print(f"✅ Estado cargado desde '{STATE_FILE_PATH}'.")
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠️ No se pudo cargar el estado desde '{STATE_FILE_PATH}'. Empezando con estado vacío. Error: {e}")
        CONVERSATION_STATE = {}

def _save_state():
    """Guarda el estado actual de las conversaciones en un archivo JSON."""
    try:
        with open(STATE_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(CONVERSATION_STATE, f, indent=4)
    except IOError as e:
        print(f"❌ ERROR CRÍTICO: No se pudo guardar el estado en '{STATE_FILE_PATH}'. Error: {e}", file=sys.stderr)

@app.on_event("startup")
def on_startup():
    _load_state()

def _enviar_mensaje(payload: dict):
    """Función base para enviar un payload a la API de WhatsApp."""
    if not all([WHATSAPP_TOKEN, PHONE_NUMBER_ID]):
        print("Error: Faltan las variables de entorno WHATSAPP_TOKEN o PHONE_NUMBER_ID.")
        return

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    # Usar una versión reciente y estable de la API de Graph (ej. v20.0).
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        print(f"📤 RESPUESTA ENVIADA\n👤 {payload.get('to')}\n✅ OK\n")
    except requests.exceptions.RequestException as e:
        print(f"Error al enviar mensaje: {e}")
        if e.response is not None:
            print(f"Detalles del error: {e.response.text}")

def enviar_mensaje_whatsapp(texto: str, numero: str):
    """Prepara y envía un mensaje de texto a un número de WhatsApp."""
    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "text",
        "text": {"body": texto},
    }
    _enviar_mensaje(payload)

def enviar_mensaje_template(nombre_template: str, codigo_lenguaje: str, numero: str):
    """Prepara y envía un mensaje de plantilla a un número de WhatsApp."""
    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "template",
        "template": {
            "name": nombre_template,
            "language": {"code": codigo_lenguaje}
        }
    }
    _enviar_mensaje(payload)

def _get_gemini_response_and_reply(prompt: str, sender_id: str, user_state: dict):
    """
    Orchestrates getting a response from Gemini and handling the reply,
    including state management for conversation ID and user name.
    """
    previous_interaction_id = user_state.get("interaction_id")
    user_name = user_state.get("name")

    texto_respuesta, new_interaction_id = generar_respuesta_gemini(
        prompt=prompt,
        previous_interaction_id=previous_interaction_id,
        user_name=user_name
    )

    # Lógica para detectar y guardar el nombre del usuario si Gemini lo indica
    NAME_TAG_PREFIX = "[SAVE_NAME:"
    if texto_respuesta and texto_respuesta.startswith(NAME_TAG_PREFIX):
        end_tag_index = texto_respuesta.find("]")
        if end_tag_index != -1:
            # Extraer el nombre de la etiqueta
            newly_detected_name = texto_respuesta[len(NAME_TAG_PREFIX):end_tag_index].strip()
            # Actualizar el nombre en el estado del usuario
            user_state["name"] = newly_detected_name
            # Limpiar la respuesta para que la etiqueta no sea visible para el usuario
            texto_respuesta = texto_respuesta[end_tag_index + 1:].lstrip()

    # Actualizar el estado de la conversación
    if new_interaction_id:
        user_state["interaction_id"] = new_interaction_id
    elif "interaction_id" in user_state:
        del user_state["interaction_id"]

    CONVERSATION_STATE[sender_id] = user_state
    _save_state()

    enviar_mensaje_whatsapp(texto_respuesta, sender_id)

def _process_text_message(message_info: dict):
    """Procesa un evento de mensaje de tipo 'text'."""
    numero_remitente = message_info.get("from")
    texto_recibido = message_info.get("text", {}).get("body")

    if not numero_remitente or not texto_recibido:
        return

    print("═══════════════════════════════════════")
    print("📩 MENSAJE RECIBIDO")
    print(f"👤 {numero_remitente}")
    print(f"💬 {texto_recibido}")
    print("═══════════════════════════════════════\n")

    user_state = CONVERSATION_STATE.get(numero_remitente, {})
    if isinstance(user_state, str):
        print(f"🔧 Migrando estado antiguo para el usuario {numero_remitente}.")
        user_state = {"interaction_id": user_state, "name": None}
        CONVERSATION_STATE[numero_remitente] = user_state

    # Obtener el estado completo del usuario (o un diccionario vacío si es nuevo).
    user_state = CONVERSATION_STATE.get(numero_remitente, user_state)

    # --- FASE F: INTEGRACIÓN MÍNIMA DE KNOWLEDGE SERVICE ---
    try:
        # 1. Consultar el KnowledgeService primero, sin recuperación web automática.
        knowledge_response = knowledge_service.handle_query(query_text=texto_recibido)

        # 2. Si se encuentra conocimiento VALIDADO, responder y terminar.
        if knowledge_response.status == KnowledgeStatus.VALIDATED_KNOWLEDGE:
            validated_data = knowledge_response.data
            if isinstance(validated_data, ValidatedKnowledge):
                respuesta_final = f"{validated_data.content}\n\nFuente: {validated_data.source_url}"
                enviar_mensaje_whatsapp(respuesta_final, numero_remitente)
                print("✅ Respuesta enviada desde la Base de Conocimiento Local.")
                return  # Finaliza el procesamiento de este mensaje.

        # 3. Para cualquier otro estado (NOT_FOUND, PENDING, etc.), continuar a Gemini.

    except Exception as e:
        # 4. Si el KnowledgeService falla, registrar el error y continuar al fallback (Gemini).
        print(f"⚠️ ADVERTENCIA: KnowledgeService falló: {e}. Continuando con Gemini.")
    # --- FIN DE LA INTEGRACIÓN ---

    # 4. If no local knowledge was found, fallback to Gemini.
    _get_gemini_response_and_reply(texto_recibido, numero_remitente, user_state)

@app.get("/")
def inicio():
    return {"estado": "Servidor del bot funcionando correctamente."}

@app.get("/webhook_whatsapp")
async def verificar_webhook(request: Request):
    """Verifica el token del webhook con la API de Meta."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print(f"WEBHOOK VERIFICADO con éxito.")
        return Response(content=challenge, status_code=status.HTTP_200_OK)
    else:
        print("ERROR: No se pudo verificar el webhook.")
        return Response(status_code=status.HTTP_403_FORBIDDEN)

@app.post("/webhook_whatsapp")
async def recibir_mensajes(request: Request):
    """Procesa los eventos entrantes de WhatsApp."""
    body_bytes = await request.body()
    if DEBUG_WEBHOOK:
        body_str = body_bytes.decode('utf-8')
        print("\n--- DEBUG: PAYLOAD COMPLETO ---")
        print(body_str)
        print("---------------------------------\n")

    try:
        body = json.loads(body_bytes)

        if body.get("object") != "whatsapp_business_account":
            print("📡 EVENTO WHATSAPP\nTipo: Payload no es de WhatsApp.\n")
            return Response(status_code=status.HTTP_200_OK)

        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                if not value:
                    continue

                # --- EVENT ROUTER ---
                if "messages" in value:
                    for message in value.get("messages", []):
                        if message.get("type") == "text":
                            _process_text_message(message)
                        else:
                            print(f"📡 EVENTO WHATSAPP\nTipo: {message.get('type', 'unknown')}\n")

                elif "statuses" in value:
                    for status_update in value.get("statuses", []):
                        status_type = status_update.get("status", "unknown").upper()
                        log_message = {"SENT": "Enviado ✔️", "DELIVERED": "Entregado ✔️✔️", "READ": "Leído 👀"}.get(status_type, f"Estado: {status_type}")
                        print(f"📬 {log_message}\n")
                else:
                    print(f"📡 EVENTO WHATSAPP\nTipo: Desconocido (claves: {list(value.keys())})\n")

    except (json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"❌ ERROR DE PARSEO: No se pudo procesar el webhook. {type(e).__name__}: {e}\n", file=sys.stderr)

    return Response(status_code=status.HTTP_200_OK)
