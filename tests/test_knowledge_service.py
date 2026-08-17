import unittest
from unittest.mock import patch

from app.knowledge_service import (
    KnowledgeService,
    KnowledgeStatus,
    ValidatedKnowledge,
    PendingNotice,
)
from app.web_retrieval_service import RetrievedContent, RetrievalError

class TestKnowledgeService(unittest.TestCase):

    @patch('app.knowledge_service.DatabaseManager')
    def setUp(self, MockDatabaseManager):
        # Mock the DatabaseManager instance for all tests
        self.mock_db_manager = MockDatabaseManager.return_value
        self.service = KnowledgeService(db_path=":memory:")
        # Replace the service's db_manager with our mock instance
        self.service.db_manager = self.mock_db_manager

    def test_returns_validated_knowledge_when_found(self):
        """1. Devuelve VALIDATED_KNOWLEDGE cuando la base de datos encuentra contenido."""
        # Configurar el mock para que devuelva un resultado de búsqueda
        mock_search_result = {
            "title": "Test Title",
            "extracted_text": "This is validated content.",
            "final_url": "https://www.anses.gob.ar/validated"
        }
        self.mock_db_manager.search_validated_knowledge.return_value = mock_search_result

        # Ejecutar el servicio
        response = self.service.handle_query("test query")

        # Verificar el resultado
        self.assertEqual(response.status, KnowledgeStatus.VALIDATED_KNOWLEDGE)
        self.assertIsInstance(response.data, ValidatedKnowledge)
        assert response.data is not None
        self.assertEqual(response.data.title, "Test Title")
        self.assertEqual(response.data.content, "This is validated content.")
        self.mock_db_manager.search_validated_knowledge.assert_called_once_with("test query")

    @patch('app.knowledge_service.retrieve_source_content')
    def test_retrieves_and_stores_pending_notice(self, mock_retrieve_source_content):
        """2. Recupera una URL, almacena PENDING y devuelve PENDING_NOTICE."""
        # Configurar mocks: no se encuentra nada localmente y la fuente no existe
        self.mock_db_manager.search_validated_knowledge.return_value = None
        self.mock_db_manager.get_source_by_url.return_value = None
        self.mock_db_manager.insert_source.return_value = 1 # Mock new source_id

        # Configurar mock para una recuperación web exitosa
        mock_retrieved_data = RetrievedContent(
            requested_url="https://www.anses.gob.ar/pending",
            final_url="https://www.anses.gob.ar/final-pending",
            http_status_code=200,
            content_hash="somehash",
            original_content=b"pending content",
            mime_type="text/html",
            source_domain="www.anses.gob.ar",
            source_type="official",
            retrieval_date="a-date"
        )
        mock_retrieve_source_content.return_value = mock_retrieved_data

        # Ejecutar el servicio con una URL
        response = self.service.handle_query("new query", requested_url="https://www.anses.gob.ar/pending")

        # Verificar el resultado
        self.assertEqual(response.status, KnowledgeStatus.PENDING_NOTICE)
        self.assertIsInstance(response.data, PendingNotice)
        assert response.data is not None
        self.assertEqual(response.data.final_url, "https://www.anses.gob.ar/final-pending")
        self.assertFalse(hasattr(response.data, 'original_content')) # Asegurar que no se expone el contenido

        # Verificar que se intentó buscar y luego almacenar
        self.mock_db_manager.search_validated_knowledge.assert_called_once_with("new query")
        mock_retrieve_source_content.assert_called_once_with("https://www.anses.gob.ar/pending")
        self.mock_db_manager.insert_source.assert_called_once_with(
            canonical_url="https://www.anses.gob.ar/pending",
            source_domain="www.anses.gob.ar",
            source_type="official"
        )
        self.mock_db_manager.insert_knowledge_version.assert_called_once_with(
            source_id=1,
            final_url="https://www.anses.gob.ar/final-pending",
            retrieval_date="a-date",
            content_hash="somehash",
            original_content=b"pending content",
            extracted_text=None,
            content_type="pagina",
            http_status_code=200,
            mime_type="text/html"
        )

    def test_returns_not_found(self):
        """3. Devuelve NOT_FOUND cuando no hay resultado ni URL."""
        # Configurar mock: no se encuentra nada localmente
        self.mock_db_manager.search_validated_knowledge.return_value = None

        # Ejecutar el servicio sin URL
        response = self.service.handle_query("unfindable query")

        # Verificar el resultado
        self.assertEqual(response.status, KnowledgeStatus.NOT_FOUND)
        self.assertIsNone(response.data)
        self.mock_db_manager.search_validated_knowledge.assert_called_once_with("unfindable query")

    def test_returns_error_on_database_failure(self):
        """4a. Devuelve ERROR ante un fallo de la base de datos."""
        self.mock_db_manager.search_validated_knowledge.side_effect = Exception("DB connection failed")

        response = self.service.handle_query("query during db fail")

        self.assertEqual(response.status, KnowledgeStatus.ERROR)
        assert response.error_message is not None
        self.assertIn("Error interno del servicio: DB connection failed", response.error_message)

    @patch('app.knowledge_service.retrieve_source_content')
    def test_returns_error_on_retrieval_failure(self, mock_retrieve_source_content):
        """4b. Devuelve ERROR ante un fallo del servicio de recuperación."""
        self.mock_db_manager.search_validated_knowledge.return_value = None
        mock_retrieve_source_content.side_effect = RetrievalError("404 Not Found")

        response = self.service.handle_query("query", requested_url="https://www.anses.gob.ar/404")

        self.assertEqual(response.status, KnowledgeStatus.ERROR)
        assert response.error_message is not None
        self.assertIn("Error de recuperación: 404 Not Found", response.error_message)

    @patch('app.knowledge_service.retrieve_source_content')
    def test_uses_existing_source_on_retrieval(self, mock_retrieve_source_content):
        """5. Reutiliza una fuente existente al recuperar contenido nuevo."""
        # Configurar mocks: no se encuentra nada localmente, pero la fuente SÍ existe
        self.mock_db_manager.search_validated_knowledge.return_value = None
        self.mock_db_manager.get_source_by_url.return_value = {'id': 42, 'canonical_url': 'https://www.anses.gob.ar/existing'}

        # Configurar mock para una recuperación web exitosa
        mock_retrieved_data = RetrievedContent(
            requested_url="https://www.anses.gob.ar/existing",
            final_url="https://www.anses.gob.ar/existing-final",
            http_status_code=200,
            content_hash="newhash",
            original_content=b"new content",
            mime_type="text/html",
            source_domain="www.anses.gob.ar",
            source_type="official",
            retrieval_date="another-date"
        )
        mock_retrieve_source_content.return_value = mock_retrieved_data

        # Ejecutar el servicio
        response = self.service.handle_query("query for existing source", requested_url="https://www.anses.gob.ar/existing")

        # Verificar que se devuelve el aviso correcto
        self.assertEqual(response.status, KnowledgeStatus.PENDING_NOTICE)
        self.assertIsInstance(response.data, PendingNotice)
        assert response.data is not None
        self.assertEqual(response.data.final_url, "https://www.anses.gob.ar/existing-final")
        
        # Verificar que NO se intentó crear una nueva fuente
        self.mock_db_manager.insert_source.assert_not_called()
        # Verificar que se insertó una nueva versión usando el ID de fuente existente
        self.mock_db_manager.insert_knowledge_version.assert_called_once()
        self.assertEqual(self.mock_db_manager.insert_knowledge_version.call_args[1]['source_id'], 42)

if __name__ == '__main__':
    unittest.main()