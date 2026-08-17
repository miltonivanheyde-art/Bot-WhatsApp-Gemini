import unittest
import subprocess
import os
import tempfile
from datetime import datetime

# Añadir el directorio raíz al path para poder importar desde 'app'
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import DatabaseManager

class TestManageKnowledgeCLI(unittest.TestCase):

    def setUp(self):
        self.db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.db_path = self.db_file.name
        self.db_file.close()

        self.db = DatabaseManager(self.db_path)
        self.db.connect()
        self.db.create_schema()
        self._populate_test_data()
        self.db.close()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def _populate_test_data(self):
        source_id = self.db.insert_source("https://anses.gob.ar/test", "anses.gob.ar", "official")
        self.long_blob_content = b"start_of_blob_" + b"a" * 1000 + b"_end_of_blob"
        
        # Versión PENDING (ID 1)
        self.pending_id = self.db.insert_knowledge_version(
            source_id=source_id, final_url="https://anses.gob.ar/pending", retrieval_date=datetime.now().isoformat(),
            content_hash="hash_pending", original_content=self.long_blob_content, extracted_text=None,
            content_type="pagina", http_status_code=200, mime_type="text/html"
        )

        # Versión VALIDATED
        self.validated_id = self.db.insert_knowledge_version(
            source_id=source_id, final_url="https://anses.gob.ar/validated", retrieval_date=datetime.now().isoformat(),
            content_hash="hash_validated", original_content=b"validated content", extracted_text="texto validado",
            content_type="pagina", http_status_code=200, mime_type="text/html"
        )
        self.db.update_knowledge_version_status(self.validated_id, "VALIDATED", "test_setup", datetime.now().isoformat())
        self.db.insert_knowledge_entry("Validated Title", "keywords", "desc", self.validated_id)

    def _run_cli(self, command_list: list[str]):
        script_path = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'manage_knowledge.py')
        full_command = [sys.executable, script_path, '--db-path', self.db_path] + command_list
        return subprocess.run(full_command, capture_output=True, text=True)

    def test_list_pending_versions(self):
        """Prueba que el comando 'list' muestre solo las versiones PENDING."""
        result = self._run_cli(["list"])
        self.assertEqual(result.returncode, 0)
        self.assertIn(str(self.pending_id), result.stdout)
        self.assertNotIn("https://anses.gob.ar/validated", result.stdout)

    def test_show_version_details(self):
        """Prueba que 'show' muestre metadatos y no el contenido completo."""
        result = self._run_cli(["show", str(self.pending_id)])
        self.assertEqual(result.returncode, 0)
        self.assertIn("Estado Actual:     PENDING", result.stdout)
        self.assertIn("hash_pending", result.stdout)
        self.assertIn("Vista Previa del Contenido", result.stdout)
        self.assertNotIn(self.long_blob_content.decode('utf-8', errors='ignore'), result.stdout)

    def test_validate_pending_version(self):
        """Prueba que 'validate' cambie el estado y cree una entrada de conocimiento."""
        title = "Nuevo Conocimiento Validado"
        result = self._run_cli(["validate", str(self.pending_id), "--title", title, "--keywords", "kw1,kw2"])
        
        self.assertEqual(result.returncode, 0)
        self.assertIn(f"Versión {self.pending_id} validada", result.stdout)

        # Verificar directamente en la DB
        self.db.connect()
        version = self.db.get_knowledge_version_by_id(self.pending_id)
        self.assertIsNotNone(version)
        assert version is not None  # Hint for Pylance
        self.assertEqual(version['current_status'], 'VALIDATED')
        
        entry = self.db.search_validated_knowledge(title)
        self.assertIsNotNone(entry)
        assert entry is not None  # Hint for Pylance
        self.assertEqual(entry['title'], title)
        self.db.close()

    def test_reject_pending_version(self):
        """Prueba que 'reject' cambie el estado a REJECTED."""
        result = self._run_cli(["reject", str(self.pending_id), "--notes", "Contenido obsoleto"])
        
        self.assertEqual(result.returncode, 0)
        self.assertIn(f"Versión {self.pending_id} rechazada", result.stdout)

        # Verificar directamente en la DB
        self.db.connect()
        version = self.db.get_knowledge_version_by_id(self.pending_id)
        self.assertIsNotNone(version)
        assert version is not None  # Hint for Pylance
        self.assertEqual(version['current_status'], 'REJECTED')
        self.db.close()

    def test_block_invalid_transitions(self):
        """Prueba que se bloqueen transiciones de estado inválidas."""
        # Intentar validar una versión ya validada (ID 2)
        validated_id = self.validated_id
        result = self._run_cli(["validate", str(validated_id), "--title", "Intento Ilegal"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Solo se pueden validar versiones en estado PENDING", result.stderr)

        # Intentar rechazar una versión ya validada (ID 2)
        result = self._run_cli(["reject", str(validated_id), "--notes", "Intento Ilegal"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Solo se pueden rechazar versiones en estado PENDING", result.stderr)

    def test_cannot_create_entry_from_non_validated(self):
        """Prueba que la API de DB impida crear una entrada desde una versión no validada."""
        self.db.connect()
        with self.assertRaises(ValueError):
            self.db.insert_knowledge_entry("Título Ilegal", "kw", "desc", self.pending_id)
        self.db.close()

if __name__ == '__main__':
    unittest.main()