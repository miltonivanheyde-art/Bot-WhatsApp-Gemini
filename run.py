from ngrok import ngrok
import uvicorn
import os
from dotenv import load_dotenv

# Puerto donde corre FastAPI
PORT = 8000

def start_server():
    """Inicia el servidor uvicorn con recarga automática."""
    uvicorn.run(
        "app.main:app",  # Apunta a la app de FastAPI dentro de la carpeta 'app'
        host="0.0.0.0",
        port=PORT,
        reload=True,
        reload_dirs=["app"]  # Vigila solo la carpeta 'app' para evitar reinicios innecesarios
    )

if __name__ == "__main__":
    # Este bloque solo se ejecuta cuando el script es llamado directamente (`python run.py`),
    # no cuando es importado por el proceso de recarga de uvicorn.

    # Cargar variables de entorno
    load_dotenv("bot.env")
    authtoken = os.getenv("NGROK_AUTHTOKEN")

    # Desconectar cualquier túnel activo para empezar de cero y evitar errores.
    # Esto es útil si el script anterior no se cerró correctamente.
    try:
        ngrok.disconnect()
    except:
        pass

    # Iniciar el túnel de ngrok
    listener = ngrok.forward(f"localhost:{PORT}", authtoken=authtoken)

    print("\n============================================")
    print("   INICIANDO BOT DE WHATSAPP")
    print("============================================")
    print(f"🔗 URL pública del webhook: {listener.url()}")
    print("============================================\n")

    # Iniciar el servidor FastAPI
    start_server()
