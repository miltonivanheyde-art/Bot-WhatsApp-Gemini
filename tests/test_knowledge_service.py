import unittest
from unittest.mock import patch
from bs4 import BeautifulSoup

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
        """1. Devuelve un fragmento de VALIDATED_KNOWLEDGE cuando hay coincidencia."""
        # Configurar el mock para que devuelva un resultado de búsqueda
        full_text = "Este es un parrafo sobre otros temas.\n\nEl Programa de Atencion Medica Integral (PAMI) es la obra social de los jubilados y pensionados.\n\nEste es un parrafo final."
        mock_search_result = {
            "title": "Info PAMI",
            "extracted_text": full_text,
            "final_url": "https://www.anses.gob.ar/pami"
        }
        self.mock_db_manager.search_validated_knowledge.return_value = mock_search_result

        # Ejecutar el servicio
        response = self.service.handle_query("atencion pami")

        # Verificar el resultado
        self.assertEqual(response.status, KnowledgeStatus.VALIDATED_KNOWLEDGE)
        self.assertIsInstance(response.data, ValidatedKnowledge)
        assert response.data is not None
        self.assertEqual(response.data.content, "El Programa de Atencion Medica Integral (PAMI) es la obra social de los jubilados y pensionados.")
        self.assertNotEqual(response.data.content, full_text)
        self.assertEqual(response.data.source_url, "https://www.anses.gob.ar/pami")
        self.mock_db_manager.search_validated_knowledge.assert_called_once_with("atencion pami")

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
            original_content=b"<html><body><p>El Programa de Atencion Medica Integral (PAMI) es la obra social de los jubilados y pensionados, de las personas mayores de 70 anios sin jubilacion y de los ex combatientes de Malvinas.</p></body></html>",
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
            original_content=b"<html><body><p>El Programa de Atencion Medica Integral (PAMI) es la obra social de los jubilados y pensionados, de las personas mayores de 70 anios sin jubilacion y de los ex combatientes de Malvinas.</p></body></html>",
            extracted_text="El Programa de Atencion Medica Integral (PAMI) es la obra social de los jubilados y pensionados, de las personas mayores de 70 anios sin jubilacion y de los ex combatientes de Malvinas.",
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
        self.assertIn("Error de recuperación o contenido: 404 Not Found", response.error_message)

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
            original_content=b"La Asignacion Universal por Hijo (AUH) es una suma mensual que se paga por cada hijo o hija menor de 18 anios cuando sus padres estan desocupados.",
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

    def test_html_extraction_and_cleaning(self):
        """Prueba que el HTML se limpia correctamente antes de almacenarse."""
        html_content = b"""
        <html>
            <head><style>.hide{display:none}</style></head>
            <body>
                <header>Ignored Header</header>
                <nav>Ignored Nav</nav>
                <p>  La Libreta de Asignacion Universal acredita el cumplimiento de los controles de salud, vacunacion y educacion de los ninos y ninas.  </p>
                <script>alert('ignored script');</script>
                <footer>Ignored Footer</footer>
            </body>
        </html>
        """
        retrieved_content = RetrievedContent("url", "url", 200, "hash", html_content, "text/html", "domain", "official", "date")

        # Simular que no hay nada en la DB para forzar el almacenamiento
        self.mock_db_manager.search_validated_knowledge.return_value = None
        with patch('app.knowledge_service.retrieve_source_content', return_value=retrieved_content):
            self.service.handle_query("query", requested_url="url")

        self.mock_db_manager.insert_knowledge_version.assert_called_once()
        call_args = self.mock_db_manager.insert_knowledge_version.call_args[1]
        self.assertEqual(call_args['extracted_text'], "La Libreta de Asignacion Universal acredita el cumplimiento de los controles de salud, vacunacion y educacion de los ninos y ninas.")

    def test_extraction_fails_on_antibot_page(self):
        """Prueba que el almacenamiento falla si se detecta una página anti-bot."""
        incapsula_content = b"<html><title>Incapsula</title><body>Request unsuccessful.</body></html>"
        retrieved_content = RetrievedContent("url", "url", 200, "hash", incapsula_content, "text/html", "domain", "official", "date")

        self.mock_db_manager.search_validated_knowledge.return_value = None
        with patch('app.knowledge_service.retrieve_source_content', return_value=retrieved_content):
            response = self.service.handle_query("query", requested_url="url")

        self.assertEqual(response.status, KnowledgeStatus.ERROR)
        self.assertIn("Incapsula", response.error_message)
        self.mock_db_manager.insert_knowledge_version.assert_not_called()

    def test_extraction_fails_on_short_content(self):
        """Prueba que el almacenamiento falla si el texto extraído es muy corto."""
        short_content = b"<p>Ok</p>"
        retrieved_content = RetrievedContent("url", "url", 200, "hash", short_content, "text/html", "domain", "official", "date")

        self.mock_db_manager.search_validated_knowledge.return_value = None
        with patch('app.knowledge_service.retrieve_source_content', return_value=retrieved_content):
            response = self.service.handle_query("query", requested_url="url")

        self.assertEqual(response.status, KnowledgeStatus.ERROR)
        self.assertIn("demasiado corto", response.error_message)
        self.mock_db_manager.insert_knowledge_version.assert_not_called()

    def test_text_plain_extraction(self):
        """Prueba la extracción y normalización de texto plano."""
        plain_content = b"  Calendario de Pagos - Jubilados y Pensionados\n\n  Documentos terminados en 0: 08/08/2026\n  Documentos terminados en 1: 09/08/2026  "
        retrieved_content = RetrievedContent("url", "url", 200, "hash", plain_content, "text/plain", "domain", "official", "date")

        self.mock_db_manager.search_validated_knowledge.return_value = None
        with patch('app.knowledge_service.retrieve_source_content', return_value=retrieved_content):
            self.service.handle_query("query", requested_url="url")

        self.mock_db_manager.insert_knowledge_version.assert_called_once()
        call_args = self.mock_db_manager.insert_knowledge_version.call_args[1]
        self.assertEqual(call_args['extracted_text'], "Calendario de Pagos - Jubilados y Pensionados\nDocumentos terminados en 0: 08/08/2026\nDocumentos terminados en 1: 09/08/2026")

    def test_pdf_is_not_extracted(self):
        """Prueba que para un PDF, el texto extraído es None."""
        pdf_content = b"%PDF-1.4..."
        retrieved_content = RetrievedContent("url", "url", 200, "hash", pdf_content, "application/pdf", "domain", "official", "date")

        self.mock_db_manager.search_validated_knowledge.return_value = None
        with patch('app.knowledge_service.retrieve_source_content', return_value=retrieved_content):
            self.service.handle_query("query", requested_url="url")

        self.mock_db_manager.insert_knowledge_version.assert_called_once()
        call_args = self.mock_db_manager.insert_knowledge_version.call_args[1]
        self.assertIsNone(call_args['extracted_text'])

    def test_snippet_is_truncated_if_too_long(self):
        """Prueba que el fragmento se recorta si supera los 900 caracteres."""
        long_paragraph = "Este es un párrafo extremadamente largo sobre un tema específico. " * 50  # > 900 chars
        full_text = f"Parrafo inicial.\n\n{long_paragraph}\n\nParrafo final."
        mock_search_result = {
            "title": "Largo",
            "extracted_text": full_text,
            "final_url": "https://www.anses.gob.ar/largo"
        }
        self.mock_db_manager.search_validated_knowledge.return_value = mock_search_result

        response = self.service.handle_query("tema específico")

        self.assertEqual(response.status, KnowledgeStatus.VALIDATED_KNOWLEDGE)
        self.assertIsInstance(response.data, ValidatedKnowledge)
        assert response.data is not None
        self.assertEqual(len(response.data.content), 900)
        self.assertTrue(response.data.content.endswith("..."))

    def test_returns_not_found_if_no_relevant_snippet(self):
        """Prueba que devuelve NOT_FOUND si la consulta no coincide con el contenido."""
        full_text = "Este texto solo habla de jubilaciones y pensiones."
        mock_search_result = {
            "title": "Jubilaciones",
            "extracted_text": full_text,
            "final_url": "https://www.anses.gob.ar/jubilaciones"
        }
        self.mock_db_manager.search_validated_knowledge.return_value = mock_search_result

        # La consulta es sobre un tema no presente en el texto
        response = self.service.handle_query("asignacion universal")

        self.assertEqual(response.status, KnowledgeStatus.NOT_FOUND)


if __name__ == '__main__':
    unittest.main()