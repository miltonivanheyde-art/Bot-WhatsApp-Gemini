import os
from datetime import datetime
from typing import Optional

def log_error(mensaje: str, detalle_error: Optional[Exception] = None):
    """Registra un error en un formato estándar."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] ❌ ERROR: {mensaje}")
    if detalle_error:
        print(f"         Detalle: {detalle_error}")

def log_info(message: str):
    """Registra un mensaje informativo genérico."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] 📝 {message}")