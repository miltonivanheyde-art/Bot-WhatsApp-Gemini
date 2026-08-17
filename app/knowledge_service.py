from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Any, Dict
from urllib.parse import urlparse

from app.database import DatabaseManager
from app.web_retrieval_service import (
    retrieve_source_content,
    RetrievedContent,
    RetrievalError,
)

# ==============================================================================
# ESTRUCTURAS DE DATOS Y ESTADOS
# ==============================================================================

class KnowledgeStatus(Enum):
    VALIDATED_KNOWLEDGE = auto()
    PENDING_NOTICE = auto()
    STALE_NOTICE = auto()
    NOT_FOUND = auto()
    ERROR = auto()

@dataclass(frozen=True)
class ValidatedKnowledge:
    title: str
    content: str
    source_url: str

@dataclass(frozen=True)
class PendingNotice:
    final_url: str

@dataclass(frozen=True)
class ServiceResponse:
    status: KnowledgeStatus
    data: Optional[Any] = None
    error_message: Optional[str] = None

# ==============================================================================
# SERVICIO DE CONOCIMIENTO
# ==============================================================================

class KnowledgeService:
    """
    Orquesta la búsqueda y recuperación de conocimiento.
    Este servicio está diseñado para ser aislado y no tiene estado propio.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db_manager = DatabaseManager(db_path)

    def _search_local_validated(self, query_text: str) -> Optional[ValidatedKnowledge]:
        """
        Busca conocimiento validado en la base de datos local usando la API pública.
        """
        try:
            self.db_manager.connect()
            result = self.db_manager.search_validated_knowledge(query_text)
            if result:
                return ValidatedKnowledge(
                    title=result["title"],
                    content=result["extracted_text"],
                    source_url=result["final_url"]
                )
            return None
        finally:
            self.db_manager.close()

    def _store_retrieved_content(self, retrieved_content: RetrievedContent) -> None:
        """
        Almacena el contenido recuperado en la base de datos con estado PENDING.
        """
        try:
            self.db_manager.connect()
            
            # 1. Buscar o crear la fuente (source)
            source = self.db_manager.get_source_by_url(retrieved_content.requested_url)
            if source:
                source_id = source['id']
            else:
                hostname = urlparse(retrieved_content.requested_url).hostname
                if not hostname:
                    # Teóricamente inalcanzable debido a la validación en web_retrieval_service
                    raise ValueError("No se puede almacenar contenido de una URL sin hostname.")

                source_id = self.db_manager.insert_source(
                    canonical_url=retrieved_content.requested_url,
                    source_domain=hostname,
                    source_type=retrieved_content.source_type
                )

            # 2. Insertar la nueva versión del conocimiento
            self.db_manager.insert_knowledge_version(
                source_id=source_id,
                final_url=retrieved_content.final_url,
                retrieval_date=retrieved_content.retrieval_date,
                content_hash=retrieved_content.content_hash,
                original_content=retrieved_content.original_content,
                extracted_text=None,  # La extracción de texto es una fase posterior
                content_type="pagina", # Placeholder, debería ser más dinámico
                http_status_code=retrieved_content.http_status_code,
                mime_type=retrieved_content.mime_type
            )
        finally:
            self.db_manager.close()

    def handle_query(self, query_text: str, requested_url: Optional[str] = None) -> ServiceResponse:
        """
        Punto de entrada principal para manejar una consulta.
        """
        try:
            # 1. Buscar conocimiento validado localmente
            validated_result = self._search_local_validated(query_text)
            if validated_result:
                return ServiceResponse(status=KnowledgeStatus.VALIDATED_KNOWLEDGE, data=validated_result)

            # 2. Si no se encuentra y se proporciona una URL, intentar recuperar
            if requested_url:
                try:
                    retrieved_content = retrieve_source_content(requested_url)
                    self._store_retrieved_content(retrieved_content)
                    
                    # Nunca devolver el contenido PENDING, solo una notificación
                    notice = PendingNotice(final_url=retrieved_content.final_url)
                    return ServiceResponse(status=KnowledgeStatus.PENDING_NOTICE, data=notice)

                except RetrievalError as e:
                    return ServiceResponse(status=KnowledgeStatus.ERROR, error_message=f"Error de recuperación: {e}")

            # 3. Si no se encuentra localmente y no hay URL, es NOT_FOUND
            return ServiceResponse(status=KnowledgeStatus.NOT_FOUND)

        except Exception as e:
            # Captura de errores inesperados del servicio o la base de datos
            return ServiceResponse(status=KnowledgeStatus.ERROR, error_message=f"Error interno del servicio: {e}")