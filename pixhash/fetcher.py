import hashlib
import ipaddress
import logging
import os
import socket
import time
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

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


def _is_ssrf_target(hostname: str) -> bool:
    """Resolve hostname and return True if any address is private/reserved."""
    try:
        for info in socket.getaddrinfo(hostname, None):
            if _is_private_ip(info[4][0]):
                return True
    except socket.gaierror:
        pass
    return False


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
    # SVG / XML-based formats
    stripped = data.lstrip()
    if stripped.startswith((b"<svg", b"<?xml", b"<SVG", b"<?XML")):
        return True
    return False


class _SSRFBlockingRedirectHandler(HTTPRedirectHandler):
    """Block redirects that resolve to private/reserved addresses."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        hostname = urlparse(newurl).hostname or ""
        if hostname and _is_ssrf_target(hostname):
            raise URLError(f"Redirect to private address blocked: {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Fetcher:
    def __init__(self, user_agent: str, timeout: int, delay: int, max_size: int = MAX_RESPONSE_BYTES) -> None:
        self.opener = build_opener(_SSRFBlockingRedirectHandler())
        self.headers = {"User-Agent": user_agent}
        self.timeout = timeout
        self.delay = delay
        self.max_size = max_size

    def _guard_ssrf(self, url: str) -> None:
        """Raise URLError if the URL resolves to a private/reserved address."""
        hostname = urlparse(url).hostname or ""
        if hostname and _is_ssrf_target(hostname):
            raise URLError(f"Request to private address blocked: {url}")

    def fetch_bytes(self, url: str) -> bytes:
        self._guard_ssrf(url)
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
        if self.delay > 0:
            time.sleep(self.delay)
        return data

    def fetch_text(self, url: str) -> str:
        self._guard_ssrf(url)
        req = Request(url, headers=self.headers)
        resp = self.opener.open(req, timeout=self.timeout)
        data = resp.read(self.max_size + 1)
        if len(data) > self.max_size:
            raise ValueError(f"Response exceeds {self.max_size // 1_048_576} MB limit")
        if self.delay > 0:
            time.sleep(self.delay)
        return data.decode("utf-8", errors="replace")

    def hash_image(self, url: str, algo: str) -> str:
        data = self.fetch_bytes(url)
        h = hashlib.new(algo)
        h.update(data)
        return h.hexdigest()

    def hash_and_save_image(
        self, url: str, algo: str, output_dir: str
    ) -> Optional[str]:
        self._guard_ssrf(url)
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
            if self.delay > 0:
                time.sleep(self.delay)
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
