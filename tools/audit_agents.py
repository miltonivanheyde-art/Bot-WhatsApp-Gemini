import os
import warnings
import json
from dotenv import load_dotenv
from google import genai

warnings.filterwarnings(
    "ignore",
    message="Agents usage is experimental"
)


def dump_object(obj, title):
    print(f"\n--- {title} ---")

    print("\nTYPE:")
    print(type(obj))

    print("\nREPR:")
    print(repr(obj))

    if hasattr(obj, "to_dict"):
        try:
            print("\nTO_DICT:")
            print(
                json.dumps(
                    obj.to_dict(),
                    indent=2,
                    ensure_ascii=False
                )
            )
        except Exception as e:
            print(f"No fue posible serializar: {e}")


def test_anses_whatsapp_agent():
    print("--- FASE 4C: VALIDACIÓN FUNCIONAL DE AGENTS API ---")

    load_dotenv("bot.env")
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        print("❌ GEMINI_API_KEY ausente.")
        return

    client = genai.Client(api_key=api_key)

    generated_agent_id = None

    try:

        print("\n1. CREATE")

        new_agent = client.agents.create(
            description="Motor Conversacional - ANSES WhatsApp Bot",
            system_instruction=(
                "Eres un asistente virtual oficial de ANSES. "
                "Respondes consultas sobre trámites, requisitos "
                "y fechas de cobro de forma clara y breve."
            )
        )

        dump_object(
            new_agent,
            "OBJETO AGENTE CREADO"
        )

        if not hasattr(new_agent, "id"):
            raise RuntimeError(
                "El objeto Agent no posee atributo 'id'."
            )

        generated_agent_id = new_agent.id

        print(
            f"\n✅ Agent creado correctamente: "
            f"{generated_agent_id}"
        )

        print("\n2. GET")

        fetched_agent = client.agents.get(
            id=generated_agent_id
        )

        dump_object(
            fetched_agent,
            "OBJETO AGENTE RECUPERADO"
        )

        print(
            "\n✅ Recuperación validada."
        )

        print("\n3. LIST")

        listed_agents = client.agents.list(
            page_size=10
        )

        found = False
        count = 0

        for agent in listed_agents:
            count += 1

            if (
                hasattr(agent, "id")
                and
                agent.id == generated_agent_id
            ):
                found = True

        print(
            f"\n✅ Total observados: {count}"
        )

        if found:
            print(
                "✅ El agente aparece en el catálogo."
            )
        else:
            print(
                "⚠️ El agente no apareció en el listado."
            )

        print("\n--- DICTAMEN ---")
        print(
            "✅ Create / Get / List operativos."
        )

    except Exception as e:

        print(
            f"\n❌ {type(e).__name__}: {e}"
        )

        if (
            hasattr(e, "response")
            and
            e.response is not None
        ):
            try:
                print(
                    json.dumps(
                        e.response.json(),
                        indent=2,
                        ensure_ascii=False
                    )
                )
            except Exception:
                print(e.response.text)

    finally:

        print("\n4. DELETE")

        if generated_agent_id:

            try:
                client.agents.delete(
                    id=generated_agent_id
                )

                print(
                    f"✅ Eliminado: "
                    f"{generated_agent_id}"
                )

            except Exception as e:
                print(
                    f"⚠️ No se pudo eliminar: "
                    f"{type(e).__name__}"
                )

        else:
            print(
                "ℹ️ No existe agente para eliminar."
            )


if __name__ == "__main__":
    test_anses_whatsapp_agent()