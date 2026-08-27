# test_calendar_service.py
import json
import os
from app.calendar_service import AnsesCalendarService

def run_test():
    """
    Ejecuta una prueba del AnsesCalendarService para obtener,
    mostrar y auditar la estructura del calendario de pagos.
    """
    print("--- Iniciando prueba del AnsesCalendarService ---")

    # 1. Crear una instancia del servicio
    calendar_service = AnsesCalendarService()

    # 2. Obtener los calendarios de pago (usará el caché si es válido)
    print("Solicitando calendarios de pago...")
    schedules = calendar_service.get_payment_schedules()

    if not schedules:
        print("\n[ERROR] No se pudieron obtener los calendarios. Revisa los logs para más detalles.")
        print("--- Prueba finalizada con errores ---")
        return

    # 3. Auditar y mostrar la estructura de los datos obtenidos
    print("\n--- Auditoría de la Estructura de Datos ---")
    print("La información se obtiene y se guarda en una estructura de diccionario (JSON).")
    print("A continuación se muestra la estructura completa:")

    # Usamos json.dumps para una visualización "bonita" (pretty-print)
    pretty_schedules = json.dumps(schedules, indent=2, ensure_ascii=False)
    print(pretty_schedules)

    print("\n--- Análisis de la Estructura ---")
    print("La estructura principal es un diccionario donde cada 'clave' es el nombre de la prestación (ej. 'Jubilaciones y pensiones que no superen el haber mínimo').")
    print("Dentro de cada prestación, hay otro diccionario con dos claves:")
    print("  - 'month': El mes al que corresponde el calendario (ej. 'Agosto').")
    print("  - 'dates': Una lista de diccionarios, donde cada uno representa una fecha de pago con:")
    print("    - 'documento': El grupo de DNI (ej. 'DNI terminados en 0').")
    print("    - 'fecha': La fecha de cobro correspondiente (ej. '10/8').")

    print("\n--- Prueba finalizada exitosamente ---")
    print(f"Puedes verificar el archivo de caché que se ha creado/actualizado en: {calendar_service.CACHE_FILE}")


if __name__ == "__main__":
    run_test()