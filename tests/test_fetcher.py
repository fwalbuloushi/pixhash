import hashlib
import socket
import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from pixhash.fetcher import Fetcher, _check_host, _validate_image_magic

# Valid PNG magic header used as test image data
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def make_fetcher(**kwargs):
    defaults = {"user_agent": "TestAgent/1.0", "timeout": 5, "delay": 0}
    return Fetcher(**{**defaults, **kwargs})


def mock_response(data: bytes, content_type: str = "image/png"):
    resp = MagicMock()
    resp.read.return_value = data
    resp.headers.get.return_value = content_type
    return resp


class TestFetchBytes(unittest.TestCase):
    def test_returns_bytes_for_image(self):
        fetcher = make_fetcher()
        data = PNG_MAGIC + b"\x00" * 8
        resp = mock_response(data)
        with patch.object(fetcher.opener, "open", return_value=resp):
            result = fetcher.fetch_bytes("https://upload.wikimedia.org/wikipedia/commons/logo.png")
        self.assertEqual(result, data)

    def test_raises_for_non_image_content_type(self):
        fetcher = make_fetcher()
        resp = mock_response(b"<html>", content_type="text/html")
        with patch.object(fetcher.opener, "open", return_value=resp):
            with self.assertRaises(ValueError):
                fetcher.fetch_bytes("https://www.wikipedia.org/wiki/Main_Page")

    def test_raises_for_invalid_magic(self):
        fetcher = make_fetcher()
        resp = mock_response(b"not an image at all")
        with patch.object(fetcher.opener, "open", return_value=resp):
            with self.assertRaises(ValueError):
                fetcher.fetch_bytes("https://upload.wikimedia.org/wikipedia/commons/logo.png")


class TestFetchText(unittest.TestCase):
    def test_returns_decoded_text(self):
        fetcher = make_fetcher()
        resp = MagicMock()
        resp.read.return_value = b"<html><body></body></html>"
        resp.headers.get.return_value = "text/html"
        with patch.object(fetcher.opener, "open", return_value=resp):
            result = fetcher.fetch_text("https://www.wikipedia.org/")
        self.assertEqual(result, "<html><body></body></html>")


class TestHashImage(unittest.TestCase):
    def test_sha256_hash(self):
        fetcher = make_fetcher()
        data = PNG_MAGIC + b"fake image bytes"
        expected = hashlib.sha256(data).hexdigest()
        resp = mock_response(data)
        with patch.object(fetcher.opener, "open", return_value=resp):
            result = fetcher.hash_image("https://upload.wikimedia.org/wikipedia/commons/logo.png", "sha256")
        self.assertEqual(result, expected)

    def test_md5_hash(self):
        fetcher = make_fetcher()
        data = PNG_MAGIC + b"fake image bytes"
        expected = hashlib.md5(data).hexdigest()
        resp = mock_response(data)
        with patch.object(fetcher.opener, "open", return_value=resp):
            result = fetcher.hash_image("https://upload.wikimedia.org/wikipedia/commons/logo.png", "md5")
        self.assertEqual(result, expected)


class TestHashAndSaveImage(unittest.TestCase):
    def test_saves_file_and_returns_hash(self, tmp_path=None):
        import tempfile, os
        fetcher = make_fetcher()
        data = PNG_MAGIC + b"fake image bytes"
        expected = hashlib.sha256(data).hexdigest()

        resp = MagicMock()
        resp.headers.get.return_value = "image/png"
        # Simulate chunked read: first call returns data, second returns b""
        resp.read.side_effect = [data, b""]

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(fetcher.opener, "open", return_value=resp):
                result = fetcher.hash_and_save_image(
                    "https://upload.wikimedia.org/wikipedia/commons/logo.png", "sha256", tmpdir
                )
            self.assertEqual(result, expected)
            self.assertIn("logo.png", os.listdir(tmpdir))

    def test_returns_none_for_non_image(self):
        fetcher = make_fetcher()
        resp = MagicMock()
        resp.headers.get.return_value = "text/html"
        resp.read.return_value = b""
        with patch.object(fetcher.opener, "open", return_value=resp):
            result = fetcher.hash_and_save_image(
                "https://www.wikipedia.org/wiki/Main_Page", "sha256", "/tmp"
            )
        self.assertIsNone(result)

    def test_no_collision_overwrite(self):
        import tempfile, os
        fetcher = make_fetcher()
        data = PNG_MAGIC + b"second image"
        expected = hashlib.sha256(data).hexdigest()

        resp = MagicMock()
        resp.headers.get.return_value = "image/png"
        resp.read.side_effect = [data, b""]

        with tempfile.TemporaryDirectory() as tmpdir:
            # Pre-create a file with the same name
            with open(os.path.join(tmpdir, "logo.png"), "wb") as f:
                f.write(b"original")
            with patch.object(fetcher.opener, "open", return_value=resp):
                result = fetcher.hash_and_save_image(
                    "https://upload.wikimedia.org/wikipedia/commons/logo.png", "sha256", tmpdir
                )
            self.assertEqual(result, expected)
            files = os.listdir(tmpdir)
            # Both the original and the renamed file should exist
            self.assertIn("logo.png", files)
            self.assertIn("logo_1.png", files)


class TestValidateImageMagicSVG(unittest.TestCase):
    def test_svg_direct(self):
        self.assertTrue(_validate_image_magic(b"<svg xmlns='http://www.w3.org/2000/svg'>"))

    def test_svg_uppercase(self):
        self.assertTrue(_validate_image_magic(b"<SVG xmlns='http://www.w3.org/2000/svg'>"))

    def test_xml_declaration_with_svg(self):
        self.assertTrue(_validate_image_magic(b"<?xml version='1.0'?><svg xmlns='http://www.w3.org/2000/svg'>"))

    def test_xml_declaration_without_svg_rejected(self):
        self.assertFalse(_validate_image_magic(b"<?xml version='1.0'?><rss><channel></channel></rss>"))


class TestCheckHost(unittest.TestCase):
    def _make_addrinfo(self, ip):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 80))]

    def test_public_ip_passes(self):
        with patch("socket.getaddrinfo", return_value=self._make_addrinfo("93.184.216.34")):
            result = _check_host("example.com", 80)
        self.assertEqual(result[0][4][0], "93.184.216.34")

    def test_private_ip_blocked(self):
        for ip in ("192.168.1.1", "10.0.0.1", "127.0.0.1", "169.254.169.254"):
            with self.subTest(ip=ip):
                with patch("socket.getaddrinfo", return_value=self._make_addrinfo(ip)):
                    with self.assertRaises(URLError):
                        _check_host("internal.example", 80)

    def test_dns_failure_raises(self):
        with patch("socket.getaddrinfo", side_effect=socket.gaierror("Name resolution failed")):
            with self.assertRaises(URLError):
                _check_host("nonexistent.invalid", 80)


class TestFetchTextContentType(unittest.TestCase):
    def _mock_resp(self, ctype):
        resp = MagicMock()
        resp.read.return_value = b"<html></html>"
        resp.headers.get.return_value = ctype
        return resp

    def test_text_html_allowed(self):
        fetcher = make_fetcher()
        with patch.object(fetcher.opener, "open", return_value=self._mock_resp("text/html; charset=utf-8")):
            result = fetcher.fetch_text("https://upload.wikimedia.org/")
        self.assertEqual(result, "<html></html>")

    def test_text_css_allowed(self):
        fetcher = make_fetcher()
        with patch.object(fetcher.opener, "open", return_value=self._mock_resp("text/css")):
            fetcher.fetch_text("https://upload.wikimedia.org/style.css")

    def test_application_json_allowed(self):
        fetcher = make_fetcher()
        with patch.object(fetcher.opener, "open", return_value=self._mock_resp("application/json")):
            fetcher.fetch_text("https://upload.wikimedia.org/data.json")

    def test_image_content_type_rejected(self):
        fetcher = make_fetcher()
        with patch.object(fetcher.opener, "open", return_value=self._mock_resp("image/png")):
            with self.assertRaises(ValueError):
                fetcher.fetch_text("https://upload.wikimedia.org/")

    def test_empty_content_type_allowed(self):
        fetcher = make_fetcher()
        with patch.object(fetcher.opener, "open", return_value=self._mock_resp("")):
            fetcher.fetch_text("https://upload.wikimedia.org/")


if __name__ == "__main__":
    unittest.main()
