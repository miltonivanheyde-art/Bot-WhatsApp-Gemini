import unittest
from unittest.mock import patch, MagicMock
import socket
import hashlib
from app.web_retrieval_service import (
    retrieve_source_content,
    NetworkError,
    InvalidURLError,
    HTTPError,
    ContentPolicyError,
    DomainNotAllowedError,
    TooManyRedirectsError,
    RetrievedContent
)
import requests

class TestWebRetrievalService(unittest.TestCase):

    def _create_mock_response(self, content, status_code=200, content_type="text/html", headers=None):
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        final_headers = {"Content-Type": content_type}
        if headers:
            final_headers.update(headers)
        mock_resp.headers = final_headers

        mock_resp.iter_content.return_value = [content] if content else []
        mock_resp.is_redirect = status_code in (301, 302, 303, 307, 308)

        # Configurar correctamente el context manager para que `with` devuelva el mock
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False
        return mock_resp

    @patch('app.web_retrieval_service.socket.getaddrinfo', return_value=[(socket.AF_INET, 0, 0, '', ('8.8.8.8', 443))])
    @patch('app.web_retrieval_service.requests.get')
    def test_successful_retrieval(self, mock_requests_get, mock_getaddrinfo):
        """1. Recuperación HTTPS exitosa."""
        url = "https://www.anses.gob.ar/page"
        content = b"<html>Test content</html>"
        mock_requests_get.return_value = self._create_mock_response(content)
        result = retrieve_source_content(url)

        self.assertIsInstance(result, RetrievedContent)
        self.assertEqual(result.final_url, url)
        self.assertEqual(result.http_status_code, 200)
        self.assertEqual(result.original_content, content)
        self.assertEqual(result.content_hash, hashlib.sha256(content).hexdigest())
        self.assertEqual(result.mime_type, "text/html")
        self.assertEqual(result.source_domain, "www.anses.gob.ar")
        self.assertEqual(result.source_type, "official")
        mock_requests_get.assert_called_once()
        mock_getaddrinfo.assert_called_once_with(
            "www.anses.gob.ar",
            443,
            family=socket.AF_UNSPEC,
            proto=socket.IPPROTO_TCP
        )

    @patch('app.web_retrieval_service._validate_domain_and_ip')
    @patch('app.web_retrieval_service.requests.get')
    def test_valid_relative_redirection(self, mock_requests_get, mock_validate_domain):
        """2. Redirección relativa válida."""
        initial_url = "https://www.anses.gob.ar/page1"
        final_url = "https://www.anses.gob.ar/page2"
        mock_requests_get.side_effect = [
            self._create_mock_response(b"", status_code=301, headers={"Location": "/page2"}),
            self._create_mock_response(b"Final page")
        ]

        result = retrieve_source_content(initial_url)
        self.assertEqual(result.final_url, final_url)
        self.assertEqual(mock_requests_get.call_count, 2)
        self.assertEqual(mock_validate_domain.call_count, 2)

    @patch('app.web_retrieval_service._validate_domain_and_ip')
    @patch('app.web_retrieval_service.requests.get')
    def test_valid_cross_domain_redirection(self, mock_requests_get, mock_validate_domain):
        """3. Redirección válida entre dominios permitidos."""
        initial_url = "https://anses.gob.ar/redirect"
        final_url = "https://www.argentina.gob.ar/anses/final"
        mock_requests_get.side_effect = [
            self._create_mock_response(b"", status_code=301, headers={"Location": final_url}),
            self._create_mock_response(b"Final page")
        ]

        result = retrieve_source_content(initial_url)
        self.assertEqual(result.final_url, final_url)
        self.assertEqual(result.source_domain, "www.argentina.gob.ar")
        self.assertEqual(mock_validate_domain.call_count, 2)

    def test_disallowed_initial_domain(self):
        """4. Bloqueo de dominio inicial no autorizado."""
        with self.assertRaises(DomainNotAllowedError):
            retrieve_source_content("https://www.example.com")

    @patch('app.web_retrieval_service.socket.getaddrinfo', return_value=[(socket.AF_INET, 0, 0, '', ('8.8.8.8', 443))])
    @patch('app.web_retrieval_service.requests.get')
    def test_redirection_to_disallowed_domain(self, mock_requests_get, mock_getaddrinfo):
        """5. Bloqueo de redirección a dominio no autorizado antes de la segunda solicitud."""
        initial_url = "https://anses.gob.ar/redirect"
        final_url = "https://www.example.com/final"
        mock_requests_get.return_value = self._create_mock_response(b"", status_code=301, headers={"Location": final_url})

        with self.assertRaises(DomainNotAllowedError):
            retrieve_source_content(initial_url)
        mock_getaddrinfo.assert_called_once_with(
            "anses.gob.ar",
            443,
            family=socket.AF_UNSPEC,
            proto=socket.IPPROTO_TCP
        )
        mock_requests_get.assert_called_once()

    @patch('app.web_retrieval_service.socket.getaddrinfo')
    def test_private_ip_address_on_allowed_hostname(self, mock_getaddrinfo):
        """6. Bloqueo de IP privada en hostname autorizado."""
        url = "https://mi.anses.gob.ar"
        mock_getaddrinfo.return_value = [(socket.AF_INET, 0, 0, '', ('192.168.1.100', 443))]
        with self.assertRaises(DomainNotAllowedError):
            retrieve_source_content(url)

    @patch('app.web_retrieval_service.socket.getaddrinfo')
    def test_all_ips_are_validated(self, mock_getaddrinfo):
        """7. Validación de todas las IPv4 e IPv6 devueltas por getaddrinfo."""
        url = "https://www.anses.gob.ar"
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, 0, 0, '', ('8.8.8.8', 443)),
            (socket.AF_INET6, 0, 0, '', ('2606:4700:4700::1111', 443)),
            (socket.AF_INET, 0, 0, '', ('10.0.0.1', 443)),  # IP privada en la lista
            (socket.AF_INET, 0, 0, '', ('8.8.4.4', 443)),
        ]
        with self.assertRaises(DomainNotAllowedError):
            retrieve_source_content(url)

    @patch('app.web_retrieval_service._validate_domain_and_ip')
    @patch('app.web_retrieval_service.requests.get')
    def test_too_many_redirects(self, mock_requests_get, mock_validate_domain):
        """8. Exceso de tres redirecciones."""
        mock_requests_get.return_value = self._create_mock_response(b"", status_code=301, headers={"Location": "/redirect"})
        with self.assertRaises(TooManyRedirectsError):
            retrieve_source_content("https://anses.gob.ar")
        self.assertEqual(mock_requests_get.call_count, 4)

    @patch('app.web_retrieval_service._validate_domain_and_ip')
    @patch('app.web_retrieval_service.requests.get')
    def test_redirect_without_location(self, mock_requests_get, mock_validate_domain):
        """9. Redirección sin Location."""
        mock_requests_get.return_value = self._create_mock_response(b"", status_code=301, headers={})
        with self.assertRaises(NetworkError):
            retrieve_source_content("https://anses.gob.ar")

    def test_url_with_credentials(self):
        """10. URL con credenciales."""
        with self.assertRaises(InvalidURLError):
            retrieve_source_content("https://user:pass@anses.gob.ar")

    def test_url_without_hostname(self):
        """11. URL sin hostname."""
        with self.assertRaises(InvalidURLError):
            retrieve_source_content("https:///path")

    def test_url_with_invalid_port(self):
        """12. Puerto distinto de 443."""
        with self.assertRaises(InvalidURLError):
            retrieve_source_content("https://anses.gob.ar:8443")

    @patch('app.web_retrieval_service._validate_domain_and_ip')
    @patch('app.web_retrieval_service.requests.get')
    def test_http_and_network_errors(self, mock_requests_get, mock_validate_domain):
        """13. Timeout y error HTTP."""
        # Timeout
        mock_requests_get.side_effect = requests.exceptions.Timeout
        with self.assertRaises(NetworkError):
            retrieve_source_content("https://anses.gob.ar")
        # HTTP
        mock_resp = self._create_mock_response(b"", status_code=404)
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError
        mock_requests_get.side_effect = [mock_resp]
        with self.assertRaises(HTTPError):
            retrieve_source_content("https://anses.gob.ar")

    @patch('app.web_retrieval_service._validate_domain_and_ip')
    @patch('app.web_retrieval_service.requests.get')
    def test_disallowed_mime_type(self, mock_requests_get, mock_validate_domain):
        """14. MIME no permitido."""
        mock_requests_get.return_value = self._create_mock_response(b"video data", content_type="video/mp4")
        with self.assertRaises(ContentPolicyError):
            retrieve_source_content("https://anses.gob.ar")

    @patch('app.web_retrieval_service._validate_domain_and_ip')
    @patch('app.web_retrieval_service.requests.get')
    def test_invalid_content_length(self, mock_requests_get, mock_validate_domain):
        """15. Content-Length negativo, no numérico y excesivo."""
        # Excesivo
        mock_requests_get.return_value = self._create_mock_response(b"", headers={"Content-Length": str(20 * 1024 * 1024)})
        with self.assertRaises(ContentPolicyError):
            retrieve_source_content("https://anses.gob.ar")
        # Negativo
        mock_requests_get.return_value = self._create_mock_response(b"", headers={"Content-Length": "-100"})
        with self.assertRaises(ContentPolicyError):
            retrieve_source_content("https://anses.gob.ar")

        # No numérico
        mock_requests_get.return_value = self._create_mock_response(b"", headers={"Content-Length": "abc"})
        with self.assertRaises(ContentPolicyError):
            retrieve_source_content("https://anses.gob.ar")

    @patch('app.web_retrieval_service._validate_domain_and_ip')
    @patch('app.web_retrieval_service.requests.get')
    def test_content_too_large_from_stream(self, mock_requests_get, mock_validate_domain):
        """16. Exceso de tamaño durante streaming."""
        large_chunk = b"a" * (1024 * 1024) # 1MB
        mock_resp = self._create_mock_response(b"")
        mock_resp.iter_content.return_value = [large_chunk] * 11
        mock_requests_get.return_value = mock_resp

        with self.assertRaises(ContentPolicyError):
            retrieve_source_content("https://anses.gob.ar")

    @patch('app.web_retrieval_service._validate_domain_and_ip')
    @patch('app.web_retrieval_service.requests.get')
    def test_hash_and_metadata(self, mock_requests_get, mock_validate_domain):
        """17. Hash SHA-256 y metadatos devueltos."""
        url = "https://www.anses.gob.ar/page"
        content = b"test content"
        mock_requests_get.return_value = self._create_mock_response(content)
        result = retrieve_source_content(url)
        self.assertEqual(result.content_hash, hashlib.sha256(content).hexdigest())
        self.assertEqual(result.requested_url, url)
        self.assertTrue(isinstance(result.retrieval_date, str))

    @patch('app.web_retrieval_service._validate_domain_and_ip')
    @patch('app.web_retrieval_service.requests.get')
    def test_empty_chunks_are_ignored(self, mock_requests_get, mock_validate_domain):
        """18. Chunks vacíos ignorados."""
        content = b"some data"
        mock_resp = self._create_mock_response(b"")
        mock_resp.iter_content.return_value = [b"", content, b"", b""]
        mock_requests_get.return_value = mock_resp
        result = retrieve_source_content("https://anses.gob.ar")
        self.assertEqual(result.original_content, content)

    @patch('app.web_retrieval_service.socket.getaddrinfo')
    @patch('app.web_retrieval_service.requests.get')
    def test_redirection_to_private_ip_is_blocked(self, mock_requests_get, mock_getaddrinfo):
        """Prueba que una redirección a una IP privada se bloquee ANTES de la segunda solicitud."""
        initial_url = "https://www.anses.gob.ar"
        redirect_url = "https://private.anses.gob.ar"
        mock_requests_get.return_value = self._create_mock_response(b"", status_code=301, headers={"Location": redirect_url})
        mock_getaddrinfo.side_effect = [
            [(socket.AF_INET, 0, 0, '', ('8.8.8.8', 443))], # IP pública para anses.gob.ar
            [(socket.AF_INET, 0, 0, '', ('127.0.0.1', 443))]      # IP privada para private.anses.gob.ar
        ]
        with self.assertRaises(DomainNotAllowedError):
            retrieve_source_content(initial_url)
        mock_requests_get.assert_called_once()

    @patch('app.web_retrieval_service.socket.getaddrinfo')
    def test_dns_resolution_failure(self, mock_getaddrinfo):
        """Prueba que una falla en la resolución DNS lance NetworkError."""
        mock_getaddrinfo.side_effect = socket.gaierror
        with self.assertRaises(NetworkError):
            retrieve_source_content("https://unresolvable.anses.gob.ar")

if __name__ == '__main__':
    unittest.main()