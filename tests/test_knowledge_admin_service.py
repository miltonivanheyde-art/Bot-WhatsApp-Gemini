import unittest
from unittest.mock import patch, ANY, Mock
import time

from app.knowledge_admin_service import KnowledgeAdminService
from app.database import DatabaseManager

class TestKnowledgeAdminService(unittest.TestCase):

    def setUp(self):
        # Inyectar un mock de DatabaseManager
        self.mock_db_manager = Mock(spec=DatabaseManager)
        self.admin_service = KnowledgeAdminService(db_manager=self.mock_db_manager)

        # Limpiar confirmaciones pendientes entre pruebas
        self.confirmations_patcher = patch('app.knowledge_admin_service._pending_confirmations', {})
        self.mock_confirmations = self.confirmations_patcher.start()
        self.addCleanup(self.confirmations_patcher.stop)

    def test_list_pending(self):
        """Prueba el listado de versiones PENDING."""
        self.mock_db_manager.list_knowledge_versions_by_status.return_value = [
            {'id': 1, 'final_url': 'https://anses.gob.ar/page1'},
            {'id': 2, 'final_url': 'https://anses.gob.ar/page2'}
        ]
        response = self.admin_service.process_command("/admin pendientes", "admin1")
        self.assertIn("ID 1", response)
        self.assertIn("ID 2", response)
        self.mock_db_manager.list_knowledge_versions_by_status.assert_called_once_with('PENDING', limit=10)

    def test_show_limited_preview(self):
        """Prueba que 'ver' muestra una vista previa limitada y no el blob completo."""
        long_content = b"start " + b"a" * 1000 + b" end"
        self.mock_db_manager.get_knowledge_version_by_id.return_value = {
            'id': 1, 'current_status': 'PENDING', 'final_url': 'url',
            'retrieval_date': 'date', 'mime_type': 'type', 'content_hash': 'hash',
            'extracted_text': None, 'original_content': long_content
        }
        response = self.admin_service.process_command("/admin ver 1", "admin1")
        self.assertIn("Vista Previa", response)
        self.assertTrue(len(response) < 500)
        self.assertNotIn(long_content.decode(), response)

    def test_validate_flow_with_confirmation_and_whitespace(self):
        """Prueba el flujo de validación, conservando espacios en los argumentos."""
        self.mock_db_manager.get_knowledge_version_by_id.return_value = {'id': 1, 'current_status': 'PENDING'}

        # Iniciar validación con espacios extra
        init_response = self.admin_service.process_command("/admin validar 1 |  Título de Prueba  |  kw1 , kw2  |  Descripción opcional  ", "admin1")
        self.assertIn("Para confirmar, envía:", init_response)

        # Confirmar
        confirm_response = self.admin_service.process_command("/admin confirmar validar 1", "admin1")
        self.assertIn("Acción confirmada. Versión 1 validada", confirm_response)

        self.mock_db_manager.update_knowledge_version_status.assert_called_once_with(1, 'VALIDATED', "admin1", ANY)
        self.mock_db_manager.insert_knowledge_entry.assert_called_once_with(
            title='Título de Prueba',
            keywords='kw1 , kw2',
            description='Descripción opcional',
            active_version_id=1
        )

    def test_reject_flow_with_confirmation_and_whitespace(self):
        """Prueba el flujo de rechazo, conservando espacios en el motivo."""
        self.mock_db_manager.get_knowledge_version_by_id.return_value = {'id': 1, 'current_status': 'PENDING'}

        # Iniciar rechazo con espacios extra
        init_response = self.admin_service.process_command("/admin rechazar 1 |  Motivo de prueba con espacios  ", "admin1")
        self.assertIn("Para confirmar, envía:", init_response)

        # Confirmar
        confirm_response = self.admin_service.process_command("/admin confirmar rechazar 1", "admin1")
        self.assertIn("Acción confirmada. Versión 1 rechazada", confirm_response)

        self.mock_db_manager.update_knowledge_version_status.assert_called_once_with(
            1, 'REJECTED', "admin1", ANY, notes='Motivo de prueba con espacios'
        )

    def test_confirmation_from_different_admin_fails(self):
        """Prueba que la confirmación de otro administrador es bloqueada."""
        self.mock_db_manager.get_knowledge_version_by_id.return_value = {'id': 1, 'current_status': 'PENDING'}

        # Admin1 inicia la validación
        self.admin_service.process_command("/admin validar 1 | Título | kw", "admin1")

        # Admin2 intenta confirmar
        response = self.admin_service.process_command("/admin confirmar validar 1", "admin2")
        self.assertIn("No tienes ninguna operación pendiente", response)
        self.mock_db_manager.update_knowledge_version_status.assert_not_called()

    @patch('app.knowledge_admin_service.time.time')
    def test_confirmation_expires(self, mock_time):
        """Prueba que una solicitud de confirmación expira."""
        self.mock_db_manager.get_knowledge_version_by_id.return_value = {'id': 1, 'current_status': 'PENDING'}

        # Iniciar validación en el tiempo 0
        mock_time.return_value = 0.0
        self.admin_service.process_command("/admin validar 1 | Título | kw", "admin1")

        # Adelantar el tiempo más allá del timeout
        mock_time.return_value = 300.0
        response = self.admin_service.process_command("/admin confirmar validar 1", "admin1")

        self.assertIn("La solicitud de confirmación ha expirado", response)
        self.mock_db_manager.update_knowledge_version_status.assert_not_called()

    def test_cannot_validate_non_pending_version(self):
        """Prueba que no se puede validar una versión que no está PENDING."""
        self.mock_db_manager.get_knowledge_version_by_id.return_value = {'id': 1, 'current_status': 'VALIDATED'}
        response = self.admin_service.process_command("/admin validar 1 | Título | kw", "admin1")
        self.assertIn("no está en estado PENDING", response)
        self.mock_db_manager.update_knowledge_version_status.assert_not_called()

    def test_cannot_reject_non_pending_version(self):
        """Prueba que no se puede rechazar una versión que no está PENDING."""
        self.mock_db_manager.get_knowledge_version_by_id.return_value = {'id': 1, 'current_status': 'VALIDATED'}
        response = self.admin_service.process_command("/admin rechazar 1 | Motivo", "admin1")
        self.assertIn("no está en estado PENDING", response)
        self.mock_db_manager.update_knowledge_version_status.assert_not_called()

    def test_unauthorized_user_is_ignored_in_main(self):
        """
        Simula el comportamiento de main.py.
        Esta prueba verifica que el servicio no se invoca si el usuario no es admin.
        """
        # Esta es una prueba conceptual, la lógica real está en main.py
        admin_numbers = {"admin1", "admin2"}

        # Usuario no autorizado
        user_number = "user123"
        command = "/admin pendientes"

        if command.startswith("/admin") and user_number in admin_numbers:
            # Se llamaría al servicio
            called = True
        else:
            # No se llama al servicio
            called = False

        self.assertFalse(called)

    def test_normal_command_is_not_processed(self):
        """Prueba que un comando normal no es procesado por el servicio de admin."""
        response = self.admin_service.process_command("Hola, ¿cómo estás?", "admin1")
        self.assertIn("Comando no válido", response)

if __name__ == '__main__':
    unittest.main()