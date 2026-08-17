import os
import json
from fastapi import FastAPI, Request, Response, status
import sys
import requests
from dotenv import load_dotenv
# Cargar variables de entorno desde el archivo bot.env

from app.gemini_service import generar_respuesta_gemini

load_dotenv(dotenv_path="bot.env")

# Variables desde .env
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

DEBUG_WEBHOOK = False

app = FastAPI()

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
    # La versión de la API se actualiza a v25.0 según el ejemplo curl proporcionado.
    url = f"https://graph.facebook.com/v25.0/{PHONE_NUMBER_ID}/messages"
    
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

    previous_interaction_id = CONVERSATION_STATE.get(numero_remitente)

    texto_respuesta, new_interaction_id = generar_respuesta_gemini(
        prompt=texto_recibido,
        previous_interaction_id=previous_interaction_id
    )

    if new_interaction_id:
        CONVERSATION_STATE[numero_remitente] = new_interaction_id
        _save_state()
    elif numero_remitente in CONVERSATION_STATE:
        del CONVERSATION_STATE[numero_remitente]
        _save_state()

    enviar_mensaje_whatsapp(texto_respuesta, numero_remitente)

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

        if "entry" not in body or not body["entry"]:
            print("📡 EVENTO WHATSAPP\nTipo: Payload inválido (sin 'entry').\n")
            return Response(status_code=status.HTTP_200_OK)

        value = body["entry"][0]["changes"][0].get("value", {})

        # --- EVENT ROUTER ---
        if "messages" in value:
            for message in value["messages"]:
                message_type = message.get("type", "unknown")
                if message_type == "text":
                    _process_text_message(message)
                else:
                    print(f"📡 EVENTO WHATSAPP\nTipo: {message_type}\n")
        
        elif "statuses" in value:
            STATUS_LOG_FORMAT = {
                "SENT": "Enviado ✔️",
                "DELIVERED": "Entregado ✔️✔️",
                "READ": "Leído 👀"
            }
            for status_update in value["statuses"]:
                status_type = status_update.get("status", "unknown").upper()
                log_message = STATUS_LOG_FORMAT.get(status_type, f"Estado: {status_type}")
                print(f"📬 {log_message}\n")
        
        else:
            print(f"📡 EVENTO WHATSAPP\nTipo: Desconocido (claves: {list(value.keys())})\n")

    except (json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"❌ ERROR DE PARSEO: No se pudo procesar el webhook. {type(e).__name__}: {e}\n", file=sys.stderr)

    return Response(status_code=status.HTTP_200_OK)
