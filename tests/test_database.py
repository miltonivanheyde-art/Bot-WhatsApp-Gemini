import unittest
import sqlite3
import os
import tempfile
from datetime import datetime
from app.database import DatabaseManager # Importa DatabaseManager

class TestDatabaseManager(unittest.TestCase):
    def setUp(self):
        # Use a temporary file for the database to test file system operations
        self.db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.db_path = self.db_file.name
        self.db_file.close() # Close the file so the manager can open it

        self.db_manager = DatabaseManager(db_path=self.db_path)
        self.db_manager.connect()
        self.db_manager.create_schema()

    def tearDown(self):
        self.db_manager.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_schema_creation(self):
        cursor = self.db_manager._execute_read_query("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        expected_tables = [
            "sources", "knowledge_versions", "validations",
            "knowledge_entries", "form_identities", "form_versions", "query_logs"
        ]
        for table in expected_tables:
            self.assertIn(table, tables)

    def test_foreign_keys_enabled(self):
        cursor = self.db_manager._execute_read_query("PRAGMA foreign_keys;")
        result = cursor.fetchone()[0]
        self.assertEqual(result, 1)

    def test_insert_source(self):
        source_id = self.db_manager.insert_source("https://anses.gob.ar/auh", "anses.gob.ar", "official")
        self.assertIsNotNone(source_id)
        retrieved_source = self.db_manager.get_source_by_url("https://anses.gob.ar/auh")
        self.assertIsNotNone(retrieved_source)
        assert retrieved_source is not None # Pylance hint: asegura que retrieved_source no es None
        self.assertEqual(retrieved_source["canonical_url"], "https://anses.gob.ar/auh")

    def test_insert_duplicate_source_url_fails(self):
        self.db_manager.insert_source("https://anses.gob.ar/auh", "anses.gob.ar", "official")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db_manager.insert_source("https://anses.gob.ar/auh", "anses.gob.ar", "official")

    def test_insert_knowledge_version(self):
        source_id = self.db_manager.insert_source("https://anses.gob.ar/auh", "anses.gob.ar", "official")
        version_id = self.db_manager.insert_knowledge_version(
            source_id=source_id,
            final_url="https://anses.gob.ar/auh",
            retrieval_date=datetime.now().isoformat(),
            content_hash="hash123",
            original_content=b"<html><body>Test Content</body></html>",
            extracted_text="Extracted text",
            content_type="pagina",
            http_status_code=200,
            mime_type="text/html"
        )
        self.assertIsNotNone(version_id)
        retrieved_version = self.db_manager.get_knowledge_version_by_id(version_id)
        self.assertIsNotNone(retrieved_version)
        assert retrieved_version is not None # Pylance hint: asegura que retrieved_version no es None
        self.assertEqual(retrieved_version["content_hash"], "hash123")

    def test_insert_knowledge_version_invalid_source_id_fails(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db_manager.insert_knowledge_version(
                source_id=999, # Non-existent source
                final_url="https://anses.gob.ar/auh",
                retrieval_date=datetime.now().isoformat(),
                content_hash="hash123",
                original_content=b"<html><body>Test Content</body></html>",
                extracted_text="Extracted text",
                content_type="pagina",
                http_status_code=200,
                mime_type="text/html"
            )

    def test_update_knowledge_version_status_and_log_transaction(self):
        source_id = self.db_manager.insert_source("https://anses.gob.ar/auh", "anses.gob.ar", "official")
        version_id = self.db_manager.insert_knowledge_version(
            source_id=source_id,
            final_url="https://anses.gob.ar/auh",
            retrieval_date=datetime.now().isoformat(),
            content_hash="hash123",
            original_content=b"<html><body>Test Content</body></html>",
            extracted_text="Extracted text",
            content_type="pagina",
            http_status_code=200,
            mime_type="text/html"
        )
        self.db_manager.update_knowledge_version_status(
            version_id=version_id,
            new_status="VALIDATED",
            event_by="test_user",
            event_date=datetime.now().isoformat(),
            notes="Initial validation"
        )

        updated_version = self.db_manager.get_knowledge_version_by_id(version_id)
        self.assertIsNotNone(updated_version, "La versión actualizada no debería ser None")
        assert updated_version is not None # Pylance hint: asegura que updated_version no es None
        self.assertEqual(updated_version["current_status"], "VALIDATED")
        self.assertEqual(updated_version["current_validated_by"], "test_user")

        cursor = self.db_manager._execute_read_query("SELECT * FROM validations WHERE version_id = ?", (version_id,))
        validation_log = cursor.fetchone()
        self.assertIsNotNone(validation_log)
        self.assertEqual(validation_log["validation_event_type"], "VALIDATED_EVENT")
        self.assertEqual(validation_log["event_by"], "test_user")

    def test_insert_knowledge_entry(self):
        source_id = self.db_manager.insert_source("https://anses.gob.ar/auh", "anses.gob.ar", "official")
        version_id = self.db_manager.insert_knowledge_version(
            source_id=source_id, final_url="https://anses.gob.ar/auh", retrieval_date=datetime.now().isoformat(),
            content_hash="hash123", original_content=b"<html><body>Test Content</body></html>", extracted_text="text", content_type="pagina", http_status_code=200, mime_type="text/html"
        )
        self.db_manager.update_knowledge_version_status(version_id, "VALIDATED", "user", datetime.now().isoformat())
        entry_id = self.db_manager.insert_knowledge_entry("AUH Requirements", "AUH, requisitos", "Description", version_id)
        self.assertIsNotNone(entry_id)

    def test_insert_form_identity_and_version(self):
        form_identity_id = self.db_manager.insert_form_identity("PS 1.47", "Libreta AUH", "ANSES")
        source_id = self.db_manager.insert_source("https://anses.gob.ar/form/147", "anses.gob.ar", "official")
        version_id = self.db_manager.insert_knowledge_version(
            source_id=source_id, final_url="https://anses.gob.ar/form/147.pdf", retrieval_date=datetime.now().isoformat(),
            content_hash="pdfhash", original_content=b"%PDF-1.4...", extracted_text="PDF content", content_type="pdf", http_status_code=200, mime_type="application/pdf"
        )
        form_version_id = self.db_manager.insert_form_version(form_identity_id, version_id, "v2023", "2023-01-01")
        self.assertIsNotNone(form_version_id)

    def test_insert_query_log(self):
        log_id = self.db_manager.insert_query_log("session123", datetime.now().isoformat(), "GEMINI_FALLBACK", None)
        self.assertIsNotNone(log_id)

    def test_check_constraints_content_type(self):
        source_id = self.db_manager.insert_source("https://anses.gob.ar/test", "anses.gob.ar", "official")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db_manager.insert_knowledge_version(
                source_id=source_id, final_url="https://anses.gob.ar/test", retrieval_date=datetime.now().isoformat(),
                content_hash="hash_invalid_type", original_content=b"<html><body>Test Content</body></html>", extracted_text="text",
                content_type="invalid_type", http_status_code=200, mime_type="text/html"
            )

    def test_insert_with_invalid_status_fails_at_db_level(self):
        source_id = self.db_manager.insert_source("https://anses.gob.ar/test2", "anses.gob.ar", "official")
        with self.assertRaises(sqlite3.IntegrityError):
            # This bypasses the DatabaseManager logic to test the DB constraint directly
            self.db_manager._execute_write_operation(
                """INSERT INTO knowledge_versions (source_id, final_url, retrieval_date, content_hash, original_content, extracted_text, content_type, http_status_code, mime_type, current_status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (source_id, "url", "date", "hash_invalid", b"c", "t", "pagina", 200, "html", "INVALID_STATUS")
            )

    def test_check_constraints_source_type(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db_manager.insert_source("https://invalid.com", "invalid.com", "invalid_type")

    def test_update_to_invalid_status_fails(self):
        source_id = self.db_manager.insert_source("https://anses.gob.ar/test3", "anses.gob.ar", "official")
        version_id = self.db_manager.insert_knowledge_version(
            source_id=source_id, final_url="https://anses.gob.ar/test3", retrieval_date=datetime.now().isoformat(),
            content_hash="hash_invalid_update", original_content=b"<html><body>Test Content</body></html>", extracted_text="text", content_type="pagina", http_status_code=200, mime_type="text/html"
        )
        with self.assertRaises(ValueError):
            self.db_manager.update_knowledge_version_status(version_id, "INVALID_STATUS", "user", datetime.now().isoformat())

    def test_invalid_status_transition_fails(self):
        source_id = self.db_manager.insert_source("https://anses.gob.ar/auh", "anses.gob.ar", "official")
        version_id = self.db_manager.insert_knowledge_version(
            source_id=source_id, final_url="https://anses.gob.ar/auh", retrieval_date=datetime.now().isoformat(),
            content_hash="hash123", original_content=b"<html><body>Test Content</body></html>", extracted_text="text", content_type="pagina", http_status_code=200, mime_type="text/html"
        )
        # PENDING -> VALIDATED (ok)
        self.db_manager.update_knowledge_version_status(version_id, "VALIDATED", "user", datetime.now().isoformat())
        # VALIDATED -> PENDING (invalid)
        with self.assertRaises(ValueError):
            self.db_manager.update_knowledge_version_status(version_id, "PENDING", "user", datetime.now().isoformat())

    def test_revalidation_logs_correct_event(self):
        source_id = self.db_manager.insert_source("https://anses.gob.ar/auh", "anses.gob.ar", "official")
        version_id = self.db_manager.insert_knowledge_version(
            source_id=source_id, final_url="https://anses.gob.ar/auh", retrieval_date=datetime.now().isoformat(),
            content_hash="hash123", original_content=b"<html><body>Test Content</body></html>", extracted_text="text", content_type="pagina", http_status_code=200, mime_type="text/html"
        )
        self.db_manager.update_knowledge_version_status(version_id, "VALIDATED", "user1", datetime.now().isoformat())
        self.db_manager.update_knowledge_version_status(version_id, "STALE", "system", datetime.now().isoformat())
        self.db_manager.update_knowledge_version_status(version_id, "VALIDATED", "user2", datetime.now().isoformat())

        cursor = self.db_manager._execute_read_query("SELECT validation_event_type FROM validations WHERE version_id = ? ORDER BY id DESC", (version_id,))
        last_event = cursor.fetchone()
        self.assertEqual(last_event["validation_event_type"], "REVALIDATED_EVENT")

    def test_insert_knowledge_entry_with_non_validated_version_fails(self):
        source_id = self.db_manager.insert_source("https://anses.gob.ar/auh", "anses.gob.ar", "official")
        pending_version_id = self.db_manager.insert_knowledge_version(
            source_id=source_id, final_url="https://anses.gob.ar/auh", retrieval_date=datetime.now().isoformat(),
            content_hash="hash123", original_content=b"<html><body>Test Content</body></html>", extracted_text="text", content_type="pagina", http_status_code=200, mime_type="text/html"
        )
        stale_version_id = self.db_manager.insert_knowledge_version(
            source_id=source_id, final_url="https://anses.gob.ar/auh2", retrieval_date=datetime.now().isoformat(),
            content_hash="hash456", original_content=b"<html><body>Test Content</body></html>", extracted_text="text2", content_type="pagina", http_status_code=200, mime_type="text/html"
        )
        self.db_manager.update_knowledge_version_status(stale_version_id, "VALIDATED", "user", datetime.now().isoformat())
        self.db_manager.update_knowledge_version_status(stale_version_id, "STALE", "system", datetime.now().isoformat())

        with self.assertRaises(ValueError):
            self.db_manager.insert_knowledge_entry("Title", "keywords", "desc", pending_version_id)

        with self.assertRaises(ValueError):
            self.db_manager.insert_knowledge_entry("Title", "keywords", "desc", stale_version_id)

        with self.assertRaises(ValueError):
            self.db_manager.insert_knowledge_entry("Title", "keywords", "desc", 999) # Non-existent

if __name__ == '__main__':
    unittest.main()