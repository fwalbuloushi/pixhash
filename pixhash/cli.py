#!/usr/bin/env python3
import logging
import socket
import sys
import time
import argparse
import hashlib
from typing import Optional

from pixhash.extractor import ImageURLExtractor, STYLE_URL_PATTERN
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

# Configure logging to only show the message (to stderr)
logging.basicConfig(format="%(message)s", level=logging.ERROR)

# --- Defaults & Constants ---
DEFAULT_TIMEOUT: int = 10
DEFAULT_ALGO: str = "sha256"
DEFAULT_DELAY: int = 0

DESKTOP_UA: str = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/114.0.5735.133 Safari/537.36"
)
MOBILE_UA: str = (
    "Mozilla/5.0 (Linux; Android 10; Mobile) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/114.0.5735.133 Mobile Safari/537.36"
)

ANSI_BOLD_RED: str = "\033[1;31m"
ANSI_BOLD_YELLOW: str = "\033[1;33m"
ANSI_RESET: str = "\033[0m"


class Fetcher:
    """Handles HTTP/S fetching, delays, and User-Agent management."""

    def __init__(self, user_agent: str, timeout: int, delay: int) -> None:
        self.opener = build_opener()
        self.headers = {"User-Agent": user_agent}
        self.timeout = timeout
        self.delay = delay

    def fetch_bytes(self, url: str) -> bytes:
        """Fetch raw bytes from a URL, enforcing image content-type."""
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
        """Fetch text (HTML/CSS) from a URL."""
        req = Request(url, headers=self.headers)
        resp = self.opener.open(req, timeout=self.timeout)
        data = resp.read()
        if self.delay > 0:
            time.sleep(self.delay)
        return data.decode("utf-8", errors="replace")

    def hash_image(self, url: str, algo: str) -> str:
        """Download and hash an image with the given algorithm."""
        data = self.fetch_bytes(url)
        h = hashlib.new(algo)
        h.update(data)
        return h.hexdigest()


def print_header() -> None:
    """Print the tool banner at startup."""
    print(f"{ANSI_BOLD_RED}[#]{ANSI_RESET} Pixhash v0.1")
    print(f"{ANSI_BOLD_RED}[#]{ANSI_RESET} https://github.com/fwalbuloushi/pixhash")
    print(f"{ANSI_BOLD_RED}[#]{ANSI_RESET} CTI tool to extract and hash images from websites")


def main() -> None:
    parser = argparse.ArgumentParser(add_help=True,
        description=f"{ANSI_BOLD_RED}Pixhash v0.1{ANSI_RESET} – CTI tool to extract and hash images from websites",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-t", "--timeout", type=int, default=DEFAULT_TIMEOUT,
        help="Network timeout in seconds"
    )
    parser.add_argument(
        "--algo", choices=["sha256", "sha1", "md5"],
        default=DEFAULT_ALGO, help="Hash algorithm to use"
    )
    parser.add_argument(
        "--agent", choices=["desktop", "mobile"],
        default="desktop", help="User-Agent type"
    )
    parser.add_argument(
        "--delay", type=int, default=DEFAULT_DELAY,
        help="Seconds to wait between each HTTP request"
    )
    parser.add_argument(
        "target", metavar="URL", type=str, nargs="?",
        help="URL to scan (must begin with http or https)"
    )

    args = parser.parse_args()

    if not args.target:
        print_header()
        parser.print_help()
        sys.exit(0)

    if not args.target.startswith(("http://", "https://")):
        logging.error(
            f"{ANSI_BOLD_RED}Error:{ANSI_RESET} URL must start with http or https"
        )
        sys.exit(1)

    ua = MOBILE_UA if args.agent == "mobile" else DESKTOP_UA
    fetcher = Fetcher(user_agent=ua, timeout=args.timeout, delay=args.delay)
    socket.setdefaulttimeout(args.timeout)

    print_header()
    print(f"{ANSI_BOLD_RED}[#]{ANSI_RESET} Target: {args.target}\n")

    try:
        html = fetcher.fetch_text(args.target)
    except (HTTPError, URLError, socket.timeout):
        logging.error(f"{ANSI_BOLD_RED}Error:{ANSI_RESET} Timeout")
        sys.exit(1)

    extractor = ImageURLExtractor(args.target)
    extractor.feed(html)

    # Scan external CSS for url(...) references
    for css_url in extractor.css_links:
        try:
            text = fetcher.fetch_text(css_url)
            for ref in STYLE_URL_PATTERN.findall(text):
                extractor._add(ref)
        except (HTTPError, URLError, socket.timeout):
            continue

    # Hash and print images
    for img in sorted(extractor.urls):
        try:
            digest = fetcher.hash_image(img, args.algo)
            print(f"{img}  {ANSI_BOLD_YELLOW}>>{ANSI_RESET}  {digest}")
        except HTTPError as e:
            logging.error(
                f"{img}  {ANSI_BOLD_YELLOW}>>{ANSI_RESET}  "
                f"{ANSI_BOLD_RED}Error:{ANSI_RESET} {e.code}"
            )
        except (URLError, socket.timeout):
            logging.error(
                f"{img}  {ANSI_BOLD_YELLOW}>>{ANSI_RESET}  "
                f"{ANSI_BOLD_RED}Error:{ANSI_RESET} Timeout"
            )
        except ValueError:
            # non-image content-type
            continue
        except Exception as e:
            msg = str(e).split(":")[-1].strip()
            logging.error(
                f"{img}  {ANSI_BOLD_YELLOW}>>{ANSI_RESET}  "
                f"{ANSI_BOLD_RED}Error:{ANSI_RESET} {msg}"
            )

    print()


if __name__ == "__main__":
    main()
