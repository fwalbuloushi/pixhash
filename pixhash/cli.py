#!/usr/bin/env python3
import logging
import socket
import sys
import time
import argparse
import hashlib
import os
from typing import Optional
from datetime import datetime
from pixhash.extractor import ImageURLExtractor, STYLE_URL_PATTERN
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener
from urllib.parse import urljoin, urlparse

# Configure logging to only show the message (to stderr)..
logging.basicConfig(format="%(message)s", level=logging.ERROR)

# Helper to check/create/write-permission for download directory or log directory
def ensure_writable_dir(path: str) -> None:
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as e:
        sys.exit(f"{ANSI_BOLD_RED}[#] Error:{ANSI_RESET} Could not create directory {path!r}: {e.strerror}")
    if not os.access(path, os.W_OK):
        sys.exit(f"{ANSI_BOLD_RED}[#] Error:{ANSI_RESET} No write permission in {path!r}. Please choose a different directory.")

# Defaults
DEFAULT_TIMEOUT: int = 10
DEFAULT_ALGO: str = "sha256"
DEFAULT_DELAY: int = 0
DEFAULT_USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) "
    "Gecko/20100101 Firefox/115.0"
)

# Formatting
ANSI_BOLD_RED: str    = "\033[1;31m"
ANSI_BOLD_YELLOW: str = "\033[1;33m"
ANSI_RESET: str       = "\033[0m"

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
            logging.error(f"{url} {ANSI_BOLD_YELLOW}>>{ANSI_RESET} {ANSI_BOLD_RED}Error:{ANSI_RESET} {e.code}")
            return None
        except (URLError, socket.timeout):
            logging.error(f"{url} {ANSI_BOLD_YELLOW}>>{ANSI_RESET} {ANSI_BOLD_RED}Error:{ANSI_RESET} Timeout")
            return None
        except OSError as e:
            logging.error(f"{url} {ANSI_BOLD_YELLOW}>>{ANSI_RESET} {ANSI_BOLD_RED}Error:{ANSI_RESET} Could not write file: {e.strerror}")
            return None
        except ValueError:
            return None
        return h.hexdigest()


def print_header() -> None:
    print(f"{ANSI_BOLD_RED}[#]{ANSI_RESET} Pixhash v1.0.0")
    print(f"{ANSI_BOLD_RED}[#]{ANSI_RESET} https://github.com/fwalbuloushi/pixhash")
    print(f"{ANSI_BOLD_RED}[#]{ANSI_RESET} CTI tool to extract and hash images from websites")


def main() -> None:
    parser = argparse.ArgumentParser(
        add_help=True,
        description=f"{ANSI_BOLD_RED}Pixhash v1.0.0{ANSI_RESET} – CTI tool to extract and hash images from websites",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-t", "--timeout", type=int, default=DEFAULT_TIMEOUT,
        help="Network timeout in seconds"
    )
    parser.add_argument(
        "--algo", choices=["sha256", "sha1", "md5"], default=DEFAULT_ALGO,
        help="Hash algorithm to use"
    )
    parser.add_argument(
        "--user-agent", "-U", dest="user_agent", default=DEFAULT_USER_AGENT,
        help="Custom User-Agent string to use for HTTP requests"
    )
    parser.add_argument(
        "--delay", type=int, default=DEFAULT_DELAY,
        help="Seconds to wait between each HTTP request"
    )
    parser.add_argument(
        "--download", action="store_true",
        help="Download files to disk as you hash them (requires -o)"
    )
    parser.add_argument(
        "-o", "--output-dir", dest="output_dir", default=None,
        help="Directory in which to save downloaded images and/or log file"
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
        logging.error(f"{ANSI_BOLD_RED}Error:{ANSI_RESET} URL must start with http or https")
        sys.exit(1)

    if args.output_dir:
        ensure_writable_dir(args.output_dir)
    if args.download and not args.output_dir:
        sys.exit(f"{ANSI_BOLD_RED}[#] Error:{ANSI_RESET} --download requires specifying an output directory with -o/--output-dir")

    ua = args.user_agent
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

    results = []  # list of (url, hash)

    # Hash (and optionally save) each image
    for img in sorted(extractor.urls):
        if args.download:
            digest = fetcher.hash_and_save_image(img, args.algo, args.output_dir)
            if digest:
                print(f"{img} {ANSI_BOLD_YELLOW}>>{ANSI_RESET} {digest}")
                results.append((img, digest))
        else:
            try:
                digest = fetcher.hash_image(img, args.algo)
                print(f"{img} {ANSI_BOLD_YELLOW}>>{ANSI_RESET} {digest}")
                if args.output_dir:
                    results.append((img, digest))
            except HTTPError as e:
                logging.error(f"{img} {ANSI_BOLD_YELLOW}>>{ANSI_RESET} {ANSI_BOLD_RED}Error:{ANSI_RESET} {e.code}")
            except (URLError, socket.timeout):
                logging.error(f"{img} {ANSI_BOLD_YELLOW}>>{ANSI_RESET} {ANSI_BOLD_RED}Error:{ANSI_RESET} Timeout")
            except ValueError:
                continue
            except Exception as e:
                msg = str(e).split(":")[-1].strip()
                logging.error(f"{img} {ANSI_BOLD_YELLOW}>>{ANSI_RESET} {ANSI_BOLD_RED}Error:{ANSI_RESET} {msg}")

    # Write log file only if output_dir provided
    if results and args.output_dir:
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        log_name = f"pixhash_{timestamp}.txt"
        log_path = os.path.join(args.output_dir, log_name)

        with open(log_path, "w") as logf:
            logf.write("Pixhash Run Log\n")
            logf.write("================\n")
            logf.write(f"Target URL:    {args.target}\n")
            logf.write(f"Date:          {now.strftime('%Y-%m-%d')}\n")
            logf.write(f"Time:          {now.strftime('%H:%M:%S')}\n")
            logf.write(f"Algorithm:     {args.algo}\n")
            logf.write(f"User-Agent:    {ua}\n")
            logf.write(f"Output Dir:    {args.output_dir}\n\n")
            logf.write("Results\n")
            logf.write("-------\n")
            for url, digest in results:
                logf.write(f"{url} >> {digest}\n")
            if args.download:
                logf.write(f"\nAll downloaded images and this log have been saved into:\n{args.output_dir}\n")
            else:
                logf.write(f"\nHash results and log file have been saved into:\n{args.output_dir}\n")

        if args.download:
            print(f"\nAll downloaded images and log file saved into:\n{args.output_dir}")
        else:
            print(f"\nHash results and log file saved into:\n{args.output_dir}")

    print()


if __name__ == "__main__":
    main()
