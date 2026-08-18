import sys
import os
import time
from datetime import datetime, timezone
from typing import Dict, Tuple, Any

# Añadir el directorio raíz al path para poder importar desde 'app'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import DatabaseManager

# Almacenamiento en memoria para confirmaciones pendientes.
# Estructura: { "admin_number": (action, version_id, data, timestamp) }
_pending_confirmations: Dict[str, Tuple[str, int, Dict[str, Any], float]] = {}
CONFIRMATION_TIMEOUT_SECONDS = 120  # 2 minutos para confirmar

class KnowledgeAdminService:
    """Gestiona los comandos administrativos para la base de conocimiento."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def _handle_list(self) -> str:
        try:
            self.db_manager.connect()
            versions = self.db_manager.list_knowledge_versions_by_status('PENDING', limit=10)
            if not versions:
                return "No hay versiones pendientes de validación."

            response_lines = ["Versiones pendientes de validación:"]
            for version in versions:
                url_corta = version['final_url'][:60] + "..." if len(version['final_url']) > 60 else version['final_url']
                response_lines.append(f"• ID {version['id']}: {url_corta}")
            return "\n".join(response_lines)
        finally:
            self.db_manager.close()

    def _handle_show(self, version_id: int) -> str:
        try:
            self.db_manager.connect()
            version = self.db_manager.get_knowledge_version_by_id(version_id)
            if not version:
                return f"Error: No se encontró la versión con ID {version_id}."

            preview_text = ""
            if version.get('extracted_text'):
                preview_text = version['extracted_text'][:500]
                if len(version['extracted_text']) > 500:
                    preview_text += "\n\n... (Vista previa recortada)"
            else:
                preview_text = "Sin texto limpio disponible. No validar."

            return (
                f"Detalles de la Versión ID: {version['id']}\n"
                f"--------------------\n"
                f"Estado: {version['current_status']}\n"
                f"URL: {version['final_url']}\n"
                f"MIME: {version['mime_type']}\n"
                f"Texto Extraído:\n---\n{preview_text}"
            )
        finally:
            self.db_manager.close()

    def _handle_validate_init(self, admin_number: str, parts: list[str]) -> str:
        try:
            if len(parts) < 3:
                raise ValueError("Formato incorrecto. Uso: /admin validar <ID> | <título> | <palabras_clave>")

            command_body = parts[2]
            version_id_str, _, rest_of_body = command_body.partition('|')
            title, _, rest_of_body = rest_of_body.partition('|')
            keywords, _, description = rest_of_body.partition('|')

            version_id = int(version_id_str.strip())
            title = title.strip()
            keywords = keywords.strip()
            description = description.strip() or None

            if not title or not keywords:
                raise ValueError("Se requiere título y palabras clave. Uso: ... | <título> | <palabras_clave>")

            self.db_manager.connect()
            try:
                version = self.db_manager.get_knowledge_version_by_id(version_id)
                if not version or version['current_status'] != 'PENDING':
                    return f"Error: La versión {version_id} no existe o no está en estado PENDING."
            finally:
                self.db_manager.close()

            confirmation_data = {"title": title, "keywords": keywords, "description": description}
            _pending_confirmations[admin_number] = ("validate", version_id, confirmation_data, time.time())

            return f"Se validará la versión {version_id} con el título '{title}'.\nPara confirmar, envía:\n/admin confirmar validar {version_id}"
        except (ValueError, IndexError) as e:
            return f"Error en el comando: {e}"

    def _handle_reject_init(self, admin_number: str, parts: list[str]) -> str:
        try:
            if len(parts) < 3:
                raise ValueError("Formato incorrecto. Uso: /admin rechazar <ID> | <motivo>")

            command_body = parts[2]
            version_id_str, _, reason = command_body.partition('|')
            version_id = int(version_id_str.strip())
            reason = reason.strip()

            if not reason:
                raise ValueError("El motivo del rechazo es obligatorio.")

            self.db_manager.connect()
            try:
                version = self.db_manager.get_knowledge_version_by_id(version_id)
                if not version or version['current_status'] != 'PENDING':
                    return f"Error: La versión {version_id} no existe o no está en estado PENDING."
            finally:
                self.db_manager.close()

            _pending_confirmations[admin_number] = ("reject", version_id, {"notes": reason}, time.time())

            return f"Se rechazará la versión {version_id} por el motivo: '{reason}'.\nPara confirmar, envía:\n/admin confirmar rechazar {version_id}"
        except (ValueError, IndexError) as e:
            return f"Error en el comando: {e}"

    def _handle_confirm(self, admin_number: str, parts: list[str]) -> str:
        try:
            if len(parts) < 4:
                raise ValueError("Comando de confirmación incompleto.")

            action_map = {
                "validar": "validate",
                "rechazar": "reject",
            }
            action_to_confirm = action_map.get(parts[2])
            if action_to_confirm is None:
                return "Error: Acción de confirmación desconocida."

            version_id_to_confirm = int(parts[3])

            if admin_number not in _pending_confirmations:
                return "No tienes ninguna operación pendiente de confirmación."

            action, version_id, data, timestamp = _pending_confirmations[admin_number]

            if (time.time() - timestamp) > CONFIRMATION_TIMEOUT_SECONDS:
                del _pending_confirmations[admin_number]
                return "La solicitud de confirmación ha expirado. Por favor, inicia el proceso de nuevo."

            if action != action_to_confirm or version_id != version_id_to_confirm:
                return "Error: La confirmación no coincide con la operación pendiente."

            # Limpiar la confirmación pendiente antes de ejecutar
            del _pending_confirmations[admin_number]

            self.db_manager.connect()
            try:
                if action == "validate":
                    self.db_manager.update_knowledge_version_status(version_id, 'VALIDATED', admin_number, datetime.now(timezone.utc).isoformat())
                    self.db_manager.insert_knowledge_entry(
                        title=data['title'],
                        keywords=data['keywords'],
                        description=data['description'],
                        active_version_id=version_id
                    )
                    return f"✅ Acción confirmada. Versión {version_id} validada."
                elif action == "reject":
                    self.db_manager.update_knowledge_version_status(version_id, 'REJECTED', admin_number, datetime.now(timezone.utc).isoformat(), notes=data['notes'])
                    return f"✅ Acción confirmada. Versión {version_id} rechazada."
                else:
                    return "Error: Acción de confirmación desconocida."
            finally:
                self.db_manager.close()

        except (ValueError, IndexError) as e:
            return f"Error en el comando de confirmación: {e}"
        except Exception as e:
            return f"Error inesperado durante la confirmación: {e}"

    def process_command(self, command_text: str, admin_number: str) -> str:
        """Punto de entrada principal para procesar comandos administrativos."""
        parts = command_text.strip().lower().split()
        if not parts or parts[0] != '/admin':
            return "Comando no válido. Debe empezar con /admin."

        command = parts[1] if len(parts) > 1 else 'ayuda'

        try:
            if command == 'ayuda':
                return (
                    "Comandos de administrador disponibles:\n"
                    "• /admin pendientes\n"
                    "• /admin ver <ID>\n"
                    "• /admin validar <ID> | <título> | <palabras_clave> [| <descripción>]\n"
                    "• /admin rechazar <ID> | <motivo>\n"
                    "• /admin confirmar <validar|rechazar> <ID>"
                )
            elif command == 'pendientes':
                return self._handle_list()
            elif command == 'ver':
                if len(parts) < 3: return "Uso: /admin ver <ID>"
                return self._handle_show(int(parts[2]))
            elif command == 'validar':
                # Se pasan los parts originales para preservar mayúsculas/minúsculas en el contenido
                return self._handle_validate_init(admin_number, command_text.strip().split(maxsplit=2))
            elif command == 'rechazar':
                return self._handle_reject_init(admin_number, command_text.strip().split(maxsplit=2))
            elif command == 'confirmar':
                return self._handle_confirm(admin_number, parts)
            else:
                return f"Comando desconocido: '{command}'. Usa '/admin ayuda' para ver la lista de comandos."
        except Exception as e:
            return f"Error al procesar el comando: {e}"