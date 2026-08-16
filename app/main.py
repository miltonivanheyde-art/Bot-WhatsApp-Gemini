import os
import json
from fastapi import FastAPI, Request, Response, status
import requests
from dotenv import load_dotenv
# Cargar variables de entorno desde el archivo bot.env
load_dotenv(dotenv_path="bot.env")

# Variables desde .env
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

app = FastAPI()

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
        print(f"-> Mensaje enviado con éxito. Payload: {payload.get('type', 'text')}, To: {payload.get('to')}")
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
    """Procesa los mensajes entrantes de WhatsApp."""
    body_bytes = await request.body()
    body_str = body_bytes.decode('utf-8')
    print("\n--- NUEVO WEBHOOK RECIBIDO ---")
    print(f"Cuerpo: {body_str}")

    try:
        body = json.loads(body_str)
        message_info = body['entry'][0]['changes'][0]['value']['messages'][0]
        
        if message_info.get("type") == "text":
            numero_remitente = message_info.get("from")
            texto_recibido = message_info.get("text", {}).get("body")

            if not numero_remitente or not texto_recibido:
                print("Webhook ignorado (sin remitente o texto).")
                return Response(status_code=status.HTTP_200_OK)

            print(f"Mensaje de {numero_remitente}: '{texto_recibido}'")
            
            # --- LÓGICA DE RESPUESTA ---
            # Aquí es donde estaba la llamada a la IA.
            # Por ahora, enviamos una respuesta fija.
            texto_respuesta = "Mensaje recibido. El bot está en mantenimiento. 🤖"
            enviar_mensaje_whatsapp(texto_respuesta, numero_remitente)

    except (KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"Webhook ignorado (formato no esperado o no es un mensaje de usuario). Error: {e}")

    return Response(status_code=status.HTTP_200_OK)

