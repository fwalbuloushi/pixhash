import hashlib
import logging
import os
import socket
import time
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, build_opener

from pixhash.constants import ANSI_BOLD_RED, ANSI_BOLD_YELLOW, ANSI_RESET


class Fetcher:
    def __init__(self, user_agent: str, timeout: int, delay: int) -> None:
        self.opener = build_opener()
        self.headers = {"User-Agent": user_agent}
        self.timeout = timeout
        self.delay = delay

    def fetch_bytes(self, url: str) -> bytes:
        req = Request(url, headers=self.headers)
        resp = self.opener.open(req, timeout=self.timeout)
        ctype = resp.headers.get("Content-Type", "")
        if not ctype.startswith("image/"):
            raise ValueError(f"Non-image content-type: {ctype}")
        data = resp.read()
        if self.delay > 0:
            time.sleep(self.delay)
        return data

    def fetch_text(self, url: str) -> str:
        req = Request(url, headers=self.headers)
        resp = self.opener.open(req, timeout=self.timeout)
        data = resp.read()
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
        h = hashlib.new(algo)
        req = Request(url, headers=self.headers)
        try:
            resp = self.opener.open(req, timeout=self.timeout)
            ctype = resp.headers.get("Content-Type", "")
            if not ctype.startswith("image/"):
                raise ValueError(f"Non-image content-type: {ctype}")
            fname = os.path.basename(urlparse(url).path) or "index"
            out_path = os.path.join(output_dir, fname)
            with open(out_path, "wb") as fout:
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
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
            return None
        return h.hexdigest()
