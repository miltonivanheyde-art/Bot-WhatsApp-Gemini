import requests
import hashlib
import socket
import ipaddress
from urllib.parse import urlparse, urljoin
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================

ALLOWED_DOMAINS: List[str] = ["anses.gob.ar", "argentina.gob.ar"]
CONNECTION_TIMEOUT: int = 5
READ_TIMEOUT: int = 20
MAX_REDIRECTS: int = 3
MAX_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIME_TYPES: List[str] = ["text/html", "text/plain", "application/pdf"]
USER_AGENT: str = "TitaKnowledgeBot/1.0"

# ==============================================================================
# EXCEPCIONES PERSONALIZADAS
# ==============================================================================

class RetrievalError(Exception):
    """Clase base para errores de recuperación."""
    pass

class NetworkError(RetrievalError):
    """Errores relacionados con la red (timeout, DNS, etc.)."""
    pass

class InvalidURLError(RetrievalError):
    """La URL no cumple con las políticas de seguridad o formato."""
    pass

class HTTPError(RetrievalError):
    """Errores de estado HTTP (4xx, 5xx)."""
    pass

class ContentPolicyError(RetrievalError):
    """El contenido no cumple con las políticas (tamaño, tipo MIME)."""
    pass

class DomainNotAllowedError(RetrievalError):
    """El dominio de la URL no está en la lista de permitidos."""
    pass

class TooManyRedirectsError(RetrievalError):
    """Se excedió el número máximo de redirecciones."""
    pass

# ==============================================================================
# LÓGICA DE VALIDACIÓN
# ==============================================================================

def _validate_url_security(url: str):
    """Valida la URL contra políticas de seguridad básicas (esquema, credenciales, puerto)."""
    try:
        parsed = urlparse(url)
        if parsed.scheme.lower() != "https":
            raise InvalidURLError("La URL debe usar el protocolo HTTPS.")
        if not parsed.hostname:
            raise InvalidURLError("La URL debe contener un hostname válido.")
        if parsed.port is not None and parsed.port != 443:
            raise InvalidURLError(f"Puerto no permitido: {parsed.port}. Solo se permite el puerto 443 para HTTPS.")
        if parsed.username or parsed.password:
            raise InvalidURLError("La URL no puede contener credenciales de usuario.")
    except (ValueError, AttributeError) as e:
        raise InvalidURLError(f"Formato de URL inválido: {e}") from e

def _validate_domain_and_ip(hostname: str):
    """Valida que el dominio esté permitido y no resuelva a una IP no pública."""
    if not hostname:
        raise InvalidURLError("El hostname no puede estar vacío.")

    if not any(hostname == domain or hostname.endswith(f".{domain}") for domain in ALLOWED_DOMAINS):
        raise DomainNotAllowedError(f"El dominio '{hostname}' no está permitido.")

    try:
        # RIESGO PENDIENTE: La librería `requests` puede realizar su propia resolución DNS
        # internamente, potencialmente eludiendo esta validación (DNS Rebinding).
        # Se requiere un control más avanzado a nivel de socket para una mitigación completa.
        addr_info = socket.getaddrinfo(hostname, 443, family=socket.AF_UNSPEC, proto=socket.IPPROTO_TCP)
        if not addr_info:
            raise NetworkError(f"La resolución DNS para '{hostname}' no devolvió direcciones.")

        # Resuelve el hostname a todas sus direcciones IP (IPv4/IPv6) para prevenir SSRF.
        for family, socktype, proto, canonname, sockaddr in addr_info:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)
            if not ip.is_global: # is_global es False para privada, reservada, loopback, etc.
                raise DomainNotAllowedError(f"El dominio '{hostname}' resuelve a una dirección IP no permitida: {ip_str}")
    except socket.gaierror as e:
        raise NetworkError(f"No se pudo resolver el dominio '{hostname}': {e}") from e

# ==============================================================================
# ESTRUCTURA DE DATOS DE SALIDA
# ==============================================================================

@dataclass(frozen=True)
class RetrievedContent:
    """Estructura de datos para el contenido recuperado y validado."""
    requested_url: str
    final_url: str
    http_status_code: int
    content_hash: str
    original_content: bytes
    mime_type: str
    source_domain: str
    source_type: str
    retrieval_date: str

# ==============================================================================
# FUNCIÓN PRINCIPAL
# ==============================================================================

def retrieve_source_content(requested_url: str) -> RetrievedContent:
    """
    Recupera de forma segura el contenido de una URL oficial, manejando
    redirecciones manualmente y aplicando políticas de seguridad estrictas.
    """
    headers = {"User-Agent": USER_AGENT}
    current_url = requested_url

    for redirect_attempt in range(MAX_REDIRECTS + 1):
        # 1. Validar la URL actual ANTES de cada solicitud
        _validate_url_security(current_url)
        parsed_url = urlparse(current_url)
        _validate_domain_and_ip(parsed_url.hostname)

        try:
            with requests.get(
                current_url,
                timeout=(CONNECTION_TIMEOUT, READ_TIMEOUT),
                stream=True,
                allow_redirects=False,
                headers=headers,
            ) as response:
                # 2. Manejar redirecciones manualmente
                if response.is_redirect:
                    if redirect_attempt >= MAX_REDIRECTS:
                        raise TooManyRedirectsError(f"Se excedió el máximo de {MAX_REDIRECTS} redirecciones.")

                    next_url = response.headers.get('Location')
                    if not next_url:
                        raise NetworkError("La respuesta de redirección no contiene la cabecera 'Location'.")

                    # Construir URL absoluta y continuar el bucle
                    current_url = urljoin(current_url, next_url)
                    continue

                # 3. Validar código de estado HTTP para respuestas no-redirect
                response.raise_for_status()

                # 4. Validar políticas de contenido (MIME type y tamaño)
                content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
                if content_type not in ALLOWED_MIME_TYPES:
                    raise ContentPolicyError(f"Tipo MIME no permitido: '{content_type}'")

                content_length_str = response.headers.get("Content-Length")
                if content_length_str:
                    try:
                        content_length = int(content_length_str)
                        if content_length < 0:
                            raise ContentPolicyError("Content-Length inválido (negativo).")
                        if content_length > MAX_SIZE_BYTES:
                            raise ContentPolicyError(f"El contenido excede el tamaño máximo (declarado en cabecera).")
                    except (ValueError, TypeError):
                        raise ContentPolicyError("Content-Length inválido (no es un número entero).")

                # 5. Descarga incremental con validación de tamaño
                content_buffer = bytearray()
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:  # Ignorar chunks vacíos
                        content_buffer.extend(chunk)
                        if len(content_buffer) > MAX_SIZE_BYTES:
                            raise ContentPolicyError(f"El contenido descargado excede el tamaño máximo.")

                # 6. Construir el resultado y salir del bucle
                final_parsed_url = urlparse(current_url)
                return RetrievedContent(
                    requested_url=requested_url,
                    final_url=current_url,
                    http_status_code=response.status_code,
                    content_hash=hashlib.sha256(content_buffer).hexdigest(),
                    original_content=bytes(content_buffer),
                    mime_type=content_type,
                    source_domain=final_parsed_url.hostname,
                    source_type='official',
                    retrieval_date=datetime.now(timezone.utc).isoformat(),
                )

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else "desconocido"
            raise HTTPError(f"Error HTTP {status_code} para la URL {current_url}") from e
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Error de red para la URL {current_url}: {e}") from e

    # Este punto solo se alcanza si se excede el límite de redirecciones en el bucle
    raise TooManyRedirectsError(f"Se excedió el máximo de {MAX_REDIRECTS} redirecciones.")