import os
import sys
from dotenv import load_dotenv
from google import genai

# Helper para capturar la salida de help() de forma no interactiva.
_original_stdout = sys.stdout
_original_help = help

class HelpRedirect:
    def __init__(self):
        self.output = ""

    def write(self, text):
        self.output += text

    def flush(self):
        pass

def captured_help(item):
    redirector = HelpRedirect()
    sys.stdout = redirector
    try:
        _original_help(item)
    finally:
        sys.stdout = _original_stdout
    print(redirector.output)


def structural_audit_interactions():
    """
    Realiza una auditoría estructural de `client.interactions` para descubrir su API.
    Este script es para descubrimiento y no ejecuta métodos que muten estado.
    """
    print("--- INICIANDO AUDITORÍA ESTRUCTURAL DE INTERACTIONS API ---")

    load_dotenv(dotenv_path="bot.env")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ ERROR: GEMINI_API_KEY no encontrada.")
        return

    try:
        client = genai.Client(api_key=api_key)
        print("✅ Cliente de Gemini instanciado correctamente.\n")

        print("=== INTERACTIONS EXISTE ===")
        if hasattr(client, "interactions"):
            print("SI\n")
        else:
            print("NO\n")
            print("--- FIN DE LA AUDITORÍA ---")
            return

        print("=== TYPE CLIENT ===")
        print(f"{type(client)}\n")

        print("=== TYPE INTERACTIONS ===")
        print(f"{type(client.interactions)}\n")

        print("=== ATRIBUTOS CLIENT ===")
        for attr in sorted(dir(client)):
            if not attr.startswith('_'):
                print(f"- {attr}")
        print("")

        print("=== ATRIBUTOS INTERACTIONS ===")
        interactions_attrs = [attr for attr in dir(client.interactions) if not attr.startswith('_')]
        for attr in sorted(interactions_attrs):
            print(f"- {attr}")
        print("")

        print("=== HELP INTERACTIONS ===")
        captured_help(client.interactions)

        crud_methods = ['create', 'get', 'list', 'delete', 'update']
        for method_name in crud_methods:
            if method_name in interactions_attrs:
                print(f"\n=== HELP {method_name.upper()} ===")
                captured_help(getattr(client.interactions, method_name))

    except Exception as e:
        print(f"\n❌ Ocurrió un error durante la auditoría: {type(e).__name__}: {e}")

    print("\n--- FIN DE LA AUDITORÍA ESTRUCTURAL ---")

if __name__ == "__main__":
    structural_audit_interactions()