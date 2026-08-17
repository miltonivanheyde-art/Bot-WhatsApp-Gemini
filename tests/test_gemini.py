from time import perf_counter

from app.gemini_service import generar_respuesta_gemini


def ejecutar_prueba_aislada():

    print("\n=== PRUEBA AISLADA GEMINI ===\n")

    prompt_de_prueba = """
Analiza la siguiente situación:

Una persona necesita información actualizada sobre
un trámite público y no sabe si la información que encontró
en internet es confiable.

Describe:

1. Cómo abordarías el problema.
2. Qué información necesitarías.
3. Qué riesgos existen al utilizar información desactualizada.
4. Cómo verificarías la validez de una fuente.

Responde de forma estructurada.
"""

    print("PROMPT ENVIADO:")
    print(prompt_de_prueba)

    inicio = perf_counter()

    respuesta = generar_respuesta_gemini(prompt_de_prueba)

    fin = perf_counter()

    tiempo = fin - inicio

    print("\n=== RESPUESTA DE GEMINI ===\n")
    print(respuesta)

    print("\n=== MÉTRICAS ===")
    print(f"Tiempo de respuesta: {tiempo:.3f} segundos")
    print(f"Caracteres recibidos: {len(respuesta)}")

    print("\n===========================\n")


if __name__ == "__main__":
    ejecutar_prueba_aislada()