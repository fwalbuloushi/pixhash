import hashlib
import http.client
import ipaddress
import logging
import os
import socket
import time
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPHandler, HTTPSHandler, Request, build_opener

from pixhash.constants import ANSI_BOLD_RED, ANSI_BOLD_YELLOW, ANSI_RESET, MAX_RESPONSE_BYTES

# Private/reserved IP ranges blocked to prevent SSRF
_PRIVATE_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),   # link-local / cloud metadata
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),    # shared address space
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)


def _is_private_ip(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(addr)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_unspecified
            or any(ip in net for net in _PRIVATE_NETWORKS)
        )
    except ValueError:
        return False


def _check_host(hostname: str, port: int) -> list:
    """Resolve hostname and raise URLError if any address is private/reserved."""
    try:
        infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise URLError(f"DNS resolution failed for {hostname!r}: {exc}") from exc
    for _af, _stype, _proto, _canon, addr in infos:
        if _is_private_ip(addr[0]):
            raise URLError(f"Blocked: {hostname!r} resolves to private address {addr[0]}")
    return infos


# Magic byte signatures for supported image formats
_IMAGE_MAGIC: tuple[tuple[bytes, ...], ...] = (
    (b"\x89PNG\r\n\x1a\n",),           # PNG
    (b"\xff\xd8\xff",),                 # JPEG
    (b"GIF87a", b"GIF89a"),             # GIF
    (b"BM",),                           # BMP
    (b"II*\x00", b"MM\x00*"),           # TIFF
    (b"\x00\x00\x01\x00",),             # ICO
)


def _validate_image_magic(data: bytes) -> bool:
    """Return True if data begins with a recognised image magic signature."""
    for sigs in _IMAGE_MAGIC:
        if any(data.startswith(sig) for sig in sigs):
            return True
    # WebP: RIFF....WEBP
    if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WEBP":
        return True
    # SVG: accept <svg directly, or <?xml only when <svg follows within 512 bytes
    stripped = data.lstrip()
    if stripped[:4].lower() == b"<svg":
        return True
    if stripped[:5].lower() == b"<?xml" and b"<svg" in data[:512].lower():
        return True
    return False


class _ValidatingHTTPConnection(http.client.HTTPConnection):
    """Resolves DNS once, checks the IP, then connects directly — no second lookup."""

    def connect(self) -> None:
        infos = _check_host(self.host, self.port)
        af, socktype, proto, _canon, addr = infos[0]
        sock = socket.socket(af, socktype, proto)
        if self.timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
            sock.settimeout(self.timeout)
        if self.source_address:
            sock.bind(self.source_address)
        sock.connect(addr)
        self.sock = sock


class _ValidatingHTTPSConnection(http.client.HTTPSConnection):
    """Same as _ValidatingHTTPConnection but wraps the socket with TLS after connecting."""

    def connect(self) -> None:
        infos = _check_host(self.host, self.port)
        af, socktype, proto, _canon, addr = infos[0]
        sock = socket.socket(af, socktype, proto)
        if self.timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
            sock.settimeout(self.timeout)
        if self.source_address:
            sock.bind(self.source_address)
        sock.connect(addr)
        server_hostname = getattr(self, "_tunnel_host", None) or self.host
        self.sock = self._context.wrap_socket(sock, server_hostname=server_hostname)


class _ValidatingHTTPHandler(HTTPHandler):
    def http_open(self, req):
        return self.do_open(_ValidatingHTTPConnection, req)


class _ValidatingHTTPSHandler(HTTPSHandler):
    def https_open(self, req):
        return self.do_open(_ValidatingHTTPSConnection, req, context=self._context)


class Fetcher:
    def __init__(self, user_agent: str, timeout: int, delay: int, max_size: int = MAX_RESPONSE_BYTES) -> None:
        self.opener = build_opener(_ValidatingHTTPHandler, _ValidatingHTTPSHandler)
        self.headers = {"User-Agent": user_agent}
        self.timeout = timeout
        self.delay = delay
        self.max_size = max_size
        self._last_request: dict[str, float] = {}

    def _apply_delay(self, url: str) -> None:
        """Enforce per-domain rate limiting before each request."""
        if self.delay <= 0:
            return
        hostname = urlparse(url).hostname or ""
        if not hostname:
            return
        now = time.monotonic()
        wait = self.delay - (now - self._last_request.get(hostname, 0.0))
        if wait > 0:
            time.sleep(wait)
        self._last_request[hostname] = time.monotonic()

    def fetch_bytes(self, url: str) -> bytes:
        self._apply_delay(url)
        req = Request(url, headers=self.headers)
        resp = self.opener.open(req, timeout=self.timeout)
        ctype = resp.headers.get("Content-Type", "")
        if not ctype.startswith("image/"):
            raise ValueError(f"Non-image content-type: {ctype}")
        data = resp.read(self.max_size + 1)
        if len(data) > self.max_size:
            raise ValueError(f"Response exceeds {self.max_size // 1_048_576} MB limit")
        if not _validate_image_magic(data):
            raise ValueError("Response does not match any known image format")
        return data

    def fetch_text(self, url: str) -> str:
        self._apply_delay(url)
        req = Request(url, headers=self.headers)
        resp = self.opener.open(req, timeout=self.timeout)
        ctype = resp.headers.get("Content-Type", "")
        if ctype and not ctype.startswith(("text/", "application/")):
            raise ValueError(f"Unexpected content-type for text fetch: {ctype!r}")
        data = resp.read(self.max_size + 1)
        if len(data) > self.max_size:
            raise ValueError(f"Response exceeds {self.max_size // 1_048_576} MB limit")
        return data.decode("utf-8", errors="replace")

    def hash_image(self, url: str, algo: str) -> str:
        data = self.fetch_bytes(url)
        h = hashlib.new(algo)
        h.update(data)
        return h.hexdigest()

    def hash_and_save_image(
        self, url: str, algo: str, output_dir: str
    ) -> Optional[str]:
        self._apply_delay(url)
        h = hashlib.new(algo)
        req = Request(url, headers=self.headers)
        out_path = None
        try:
            resp = self.opener.open(req, timeout=self.timeout)
            ctype = resp.headers.get("Content-Type", "")
            if not ctype.startswith("image/"):
                raise ValueError(f"Non-image content-type: {ctype}")

            # Read and validate first chunk before creating the file
            first_chunk = resp.read(8192)
            if not first_chunk:
                raise ValueError("Empty response")
            if not _validate_image_magic(first_chunk):
                raise ValueError("Response does not match any known image format")

            # Resolve filename collisions
            fname = os.path.basename(urlparse(url).path) or "index"
            base, ext = os.path.splitext(fname)
            candidate = fname
            counter = 1
            while os.path.exists(os.path.join(output_dir, candidate)):
                candidate = f"{base}_{counter}{ext}"
                counter += 1
            out_path = os.path.join(output_dir, candidate)

            total = len(first_chunk)
            h.update(first_chunk)
            with open(out_path, "wb") as fout:
                fout.write(first_chunk)
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > self.max_size:
                        raise ValueError(
                            f"Response exceeds {self.max_size // 1_048_576} MB limit"
                        )
                    h.update(chunk)
                    fout.write(chunk)
        except HTTPError as e:
            logging.error(
                f"{url} {ANSI_BOLD_YELLOW}>>{ANSI_RESET} {ANSI_BOLD_RED}Error:{ANSI_RESET} {e.code}"
            )
            return None
        except (URLError, socket.timeout):
            logging.error(
                f"{url} {ANSI_BOLD_YELLOW}>>{ANSI_RESET} {ANSI_BOLD_RED}Error:{ANSI_RESET} Timeout"
            )
            return None
        except OSError as e:
            logging.error(
                f"{url} {ANSI_BOLD_YELLOW}>>{ANSI_RESET} {ANSI_BOLD_RED}Error:{ANSI_RESET} Could not write file: {e.strerror}"
            )
            return None
        except ValueError:
            # Clean up any partial file created before the error
            if out_path and os.path.exists(out_path):
                try:
                    os.remove(out_path)
                except OSError:
                    pass
            return None
        return h.hexdigest()
