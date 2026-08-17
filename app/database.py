import sqlite3
import os
from typing import Dict, Any, Optional, Tuple

# Default database file path for production/development, overridden for tests
DEFAULT_DB_FILE = "data/tita.db"

class DatabaseManager:
    def __init__(self, db_path: str = DEFAULT_DB_FILE):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        # Crear el directorio padre si no existe y no es una base de datos en memoria
        if self.db_path != ":memory:":
            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)

    def connect(self):
        """Establece la conexión a la base de datos y habilita las claves foráneas."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.execute("PRAGMA foreign_keys = ON;")
            self.conn.row_factory = sqlite3.Row # Permite acceder a las columnas por nombre
        except sqlite3.Error as e:
            print(f"Error al conectar a la base de datos {self.db_path}: {e}")
            raise

    def close(self):
        """Cierra la conexión a la base de datos."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def _execute_write_operation(self, query: str, params: Tuple = ()) -> sqlite3.Cursor:
        """Ejecuta una operación de escritura (INSERT, UPDATE, DELETE) y maneja transacciones."""
        if not self.conn:
            raise ConnectionError("Database connection not established.")
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, params)
            self.conn.commit()
            return cursor
        except sqlite3.Error:
            self.conn.rollback()
            raise

    def _execute_read_query(self, query: str, params: Tuple = ()) -> sqlite3.Cursor:
        """Ejecuta una consulta de lectura (SELECT) sin realizar commit."""
        if not self.conn:
            raise ConnectionError("Database connection not established.")
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, params)
            return cursor
        except sqlite3.Error:
            raise

    def create_schema(self):
        """Crea todas las tablas de la base de datos según el esquema V3.1."""
        if not self.conn: raise ConnectionError("Database connection not established.")
        schema_sql = """
        -- Tabla: sources
        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_url TEXT NOT NULL UNIQUE, -- URL de referencia para la fuente
            source_domain TEXT NOT NULL,
            source_type TEXT NOT NULL CHECK(source_type IN ('official', 'non_official', 'unknown'))
        );

        CREATE INDEX IF NOT EXISTS idx_sources_domain ON sources (source_domain);

        -- Tabla: knowledge_versions
        CREATE TABLE IF NOT EXISTS knowledge_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            final_url TEXT NOT NULL, -- URL efectiva después de redirecciones
            retrieval_date TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            original_content BLOB NOT NULL, -- Contenido binario o texto crudo
            extracted_text TEXT, -- Texto limpio y procesado para búsqueda/RAG
            content_type TEXT NOT NULL CHECK(content_type IN ('formulario', 'pagina', 'pdf', 'tramite', 'faq', 'calendario', 'instructivo', 'otro')),
            http_status_code INTEGER NOT NULL,
            mime_type TEXT,
            current_status TEXT NOT NULL CHECK(current_status IN ('PENDING', 'VALIDATED', 'REJECTED', 'STALE')), -- Estado actual de esta versión
            current_validated_by TEXT, -- Último validador
            current_validation_date TEXT, -- Fecha de la última actualización de estado
            UNIQUE(source_id, content_hash), -- Una fuente no debe tener el mismo contenido dos veces
            FOREIGN KEY (source_id) REFERENCES sources(id)
        );

        CREATE INDEX IF NOT EXISTS idx_knowledge_versions_hash ON knowledge_versions (content_hash);
        CREATE INDEX IF NOT EXISTS idx_knowledge_versions_status ON knowledge_versions (current_status);

        -- Tabla: validations
        CREATE TABLE IF NOT EXISTS validations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_id INTEGER NOT NULL,
            validation_event_type TEXT NOT NULL CHECK(validation_event_type IN ('SUBMITTED_FOR_VALIDATION', 'VALIDATED_EVENT', 'REJECTED_EVENT', 'STALED_EVENT', 'REVALIDATED_EVENT')),
            event_by TEXT,
            event_date TEXT NOT NULL,
            notes TEXT,
            FOREIGN KEY (version_id) REFERENCES knowledge_versions(id)
        );

        -- Tabla: knowledge_entries
        CREATE TABLE IF NOT EXISTS knowledge_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL UNIQUE, -- Título descriptivo del concepto de conocimiento
            keywords TEXT, -- Palabras clave para búsqueda
            description TEXT, -- Descripción breve del conocimiento
            active_version_id INTEGER, -- FK a knowledge_versions (debe ser VALIDATED)
            FOREIGN KEY (active_version_id) REFERENCES knowledge_versions(id)
        );

        CREATE INDEX IF NOT EXISTS idx_knowledge_entries_title ON knowledge_entries (title);
        CREATE INDEX IF NOT EXISTS idx_knowledge_entries_keywords ON knowledge_entries (keywords);

        -- Tabla: form_identities
        CREATE TABLE IF NOT EXISTS form_identities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            form_code TEXT NOT NULL UNIQUE, -- ej. "PS 1.47"
            form_name TEXT NOT NULL,
            organism TEXT NOT NULL -- ej. "ANSES"
        );

        -- Tabla: form_versions
        CREATE TABLE IF NOT EXISTS form_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            form_identity_id INTEGER NOT NULL,
            knowledge_version_id INTEGER NOT NULL UNIQUE, -- Cada versión de formulario apunta a una única knowledge_version
            detected_version TEXT, -- Versión del formulario si se informa en el documento (ej. "2023-05")
            official_date TEXT, -- Fecha oficial del formulario si se informa en el documento (ISO 8601)
            FOREIGN KEY (form_identity_id) REFERENCES form_identities(id),
            FOREIGN KEY (knowledge_version_id) REFERENCES knowledge_versions(id)
        );

        CREATE INDEX IF NOT EXISTS idx_form_versions_identity ON form_versions (form_identity_id);

        -- Tabla: query_logs
        CREATE TABLE IF NOT EXISTS query_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL, -- ID de sesión seudonimizado.
            timestamp TEXT NOT NULL,
            response_type TEXT NOT NULL CHECK(response_type IN ('VALIDATED_KNOWLEDGE', 'PENDING_NOTICE', 'STALE_NOTICE', 'GEMINI_FALLBACK', 'ERROR')),
            used_knowledge_entry_id INTEGER, -- FK a knowledge_entries si se usó conocimiento validado
            FOREIGN KEY (used_knowledge_entry_id) REFERENCES knowledge_entries(id)
        );
        """
        try:
            self.conn.executescript(schema_sql)
            self.conn.commit()
        except sqlite3.Error as e:
            self.conn.rollback()
            print(f"Error creating schema: {e}")
            raise

    def insert_source(self, canonical_url: str, source_domain: str, source_type: str) -> int:
        cursor = self._execute_write_operation(
            "INSERT INTO sources (canonical_url, source_domain, source_type) VALUES (?, ?, ?)",
            (canonical_url, source_domain, source_type)
        )
        last_id = cursor.lastrowid
        if last_id is None:
            raise RuntimeError("Failed to get last row ID after INSERT on 'sources' table.")
        return last_id

    def get_source_by_url(self, canonical_url: str) -> Optional[Dict[str, Any]]:
        cursor = self._execute_read_query("SELECT * FROM sources WHERE canonical_url = ?", (canonical_url,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def insert_knowledge_version(self, source_id: int, final_url: str, retrieval_date: str, content_hash: str, original_content: bytes, extracted_text: Optional[str], content_type: str, http_status_code: int, mime_type: Optional[str]) -> int:
        cursor = self._execute_write_operation(
            """INSERT INTO knowledge_versions (source_id, final_url, retrieval_date, content_hash, original_content, extracted_text, content_type, http_status_code, mime_type, current_status, current_validated_by, current_validation_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (source_id, final_url, retrieval_date, content_hash, original_content, extracted_text, content_type, http_status_code, mime_type, "PENDING", None, None)
        )
        last_id = cursor.lastrowid
        if last_id is None:
            raise RuntimeError("Failed to get last row ID after INSERT on 'knowledge_versions' table.")
        return last_id

    def get_knowledge_version_by_id(self, version_id: int) -> Optional[Dict[str, Any]]:
        cursor = self._execute_read_query("SELECT * FROM knowledge_versions WHERE id = ?", (version_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def search_validated_knowledge(self, query_text: str) -> Optional[Dict[str, Any]]:
        """
        Busca una entrada de conocimiento validada que coincida con el texto de la consulta.
        Devuelve la primera coincidencia encontrada.
        """
        search_term = f"%{query_text.strip()}%"
        query = """
            SELECT
                ke.title,
                kv.extracted_text,
                kv.final_url
            FROM knowledge_entries ke
            JOIN knowledge_versions kv ON ke.active_version_id = kv.id
            WHERE
                kv.current_status = 'VALIDATED' AND
                (ke.title LIKE ? OR ke.keywords LIKE ? OR kv.extracted_text LIKE ?)
            LIMIT 1;
        """
        cursor = self._execute_read_query(query, (search_term, search_term, search_term))
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_knowledge_versions_by_status(self, status: str, limit: int = 10) -> list[Dict[str, Any]]:
        """
        Lista las versiones de conocimiento por un estado específico, ordenadas por ID descendente.
        """
        query = """
            SELECT id, final_url, retrieval_date, mime_type, content_hash
            FROM knowledge_versions
            WHERE current_status = ?
            ORDER BY id DESC
            LIMIT ?
        """
        cursor = self._execute_read_query(query, (status, limit))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def update_knowledge_version_status(self, version_id: int, new_status: str, event_by: str, event_date: str, notes: Optional[str] = None):
        """
        Updates the status of a knowledge_version and logs the validation event in a single transaction.
        Enforces the state machine rules.
        """
        if not self.conn:
            raise ConnectionError("Database connection not established.")

        # 1. Get current status
        version = self.get_knowledge_version_by_id(version_id)
        if not version:
            raise ValueError(f"Version with id {version_id} not found.")
        current_status = version['current_status']

        # 2. Enforce state machine
        valid_transitions = {
            'PENDING': ['VALIDATED', 'REJECTED'],
            'VALIDATED': ['STALE'],
            'STALE': ['VALIDATED', 'REJECTED'],
            'REJECTED': ['PENDING']
        }
        if new_status not in valid_transitions.get(current_status, []):
            raise ValueError(f"Invalid status transition from '{current_status}' to '{new_status}'.")

        # 3. Determine event type
        if current_status == 'STALE' and new_status == 'VALIDATED':
            event_type = 'REVALIDATED_EVENT'
        else:
            event_type_map = {
                "PENDING": "SUBMITTED_FOR_VALIDATION",
                "VALIDATED": "VALIDATED_EVENT",
                "REJECTED": "REJECTED_EVENT",
                "STALE": "STALED_EVENT"
            }
            event_type = event_type_map[new_status]

        # 4. Execute transaction
        try:
            self.conn.execute("BEGIN TRANSACTION;")
            self.conn.execute(
                "UPDATE knowledge_versions SET current_status = ?, current_validated_by = ?, current_validation_date = ? WHERE id = ?",
                (new_status, event_by, event_date, version_id)
            )
            self.conn.execute(
                "INSERT INTO validations (version_id, validation_event_type, event_by, event_date, notes) VALUES (?, ?, ?, ?, ?)",
                (version_id, event_type, event_by, event_date, notes)
            )
            self.conn.commit()
        except sqlite3.Error:
            self.conn.rollback()
            raise

    def insert_knowledge_entry(self, title: str, keywords: Optional[str], description: Optional[str], active_version_id: Optional[int]) -> int:
        if active_version_id is not None:
            version = self.get_knowledge_version_by_id(active_version_id)
            if not version or version['current_status'] != 'VALIDATED':
                raise ValueError("active_version_id must point to a VALIDATED knowledge version.")

        cursor = self._execute_write_operation(
            "INSERT INTO knowledge_entries (title, keywords, description, active_version_id) VALUES (?, ?, ?, ?)",
            (title, keywords, description, active_version_id)
        )
        last_id = cursor.lastrowid
        if last_id is None:
            raise RuntimeError("Failed to get last row ID after INSERT on 'knowledge_entries' table.")
        return last_id

    def insert_form_identity(self, form_code: str, form_name: str, organism: str) -> int:
        cursor = self._execute_write_operation(
            "INSERT INTO form_identities (form_code, form_name, organism) VALUES (?, ?, ?)",
            (form_code, form_name, organism)
        )
        last_id = cursor.lastrowid
        if last_id is None:
            raise RuntimeError("Failed to get last row ID after INSERT on 'form_identities' table.")
        return last_id

    def insert_form_version(self, form_identity_id: int, knowledge_version_id: int, detected_version: Optional[str], official_date: Optional[str]) -> int:
        cursor = self._execute_write_operation(
            "INSERT INTO form_versions (form_identity_id, knowledge_version_id, detected_version, official_date) VALUES (?, ?, ?, ?)",
            (form_identity_id, knowledge_version_id, detected_version, official_date)
        )
        last_id = cursor.lastrowid
        if last_id is None:
            raise RuntimeError("Failed to get last row ID after INSERT on 'form_versions' table.")
        return last_id

    def insert_query_log(self, session_id: str, timestamp: str, response_type: str, used_knowledge_entry_id: Optional[int]) -> int:
        cursor = self._execute_write_operation(
            "INSERT INTO query_logs (session_id, timestamp, response_type, used_knowledge_entry_id) VALUES (?, ?, ?, ?)",
            (session_id, timestamp, response_type, used_knowledge_entry_id)
        )
        last_id = cursor.lastrowid
        if last_id is None:
            raise RuntimeError("Failed to get last row ID after INSERT on 'query_logs' table.")
        return last_id