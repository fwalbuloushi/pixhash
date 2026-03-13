#!/usr/bin/env python3
import argparse
import logging
import os
import socket
import sys
from urllib.error import HTTPError, URLError

from pixhash.constants import (
    ANSI_BOLD_RED, ANSI_BOLD_YELLOW, ANSI_RESET,
    DEFAULT_ALGO, DEFAULT_DELAY, DEFAULT_TIMEOUT, DEFAULT_USER_AGENT,
)
from pixhash.extractor import ImageURLExtractor, STYLE_URL_PATTERN
from pixhash.fetcher import Fetcher
from pixhash.logger import write_log

logging.basicConfig(format="%(message)s", level=logging.ERROR)


def ensure_writable_dir(path: str) -> None:
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as e:
        sys.exit(f"{ANSI_BOLD_RED}[#] Error:{ANSI_RESET} Could not create directory {path!r}: {e.strerror}")
    if not os.access(path, os.W_OK):
        sys.exit(f"{ANSI_BOLD_RED}[#] Error:{ANSI_RESET} No write permission in {path!r}. Please choose a different directory.")


def print_header() -> None:
    print(f"{ANSI_BOLD_RED}[#]{ANSI_RESET} Pixhash v1.1.0")
    print(f"{ANSI_BOLD_RED}[#]{ANSI_RESET} https://github.com/fwalbuloushi/pixhash")
    print(f"{ANSI_BOLD_RED}[#]{ANSI_RESET} CTI tool to extract and hash images from websites")


def main() -> None:
    parser = argparse.ArgumentParser(
        add_help=True,
        description=f"{ANSI_BOLD_RED}Pixhash v1.1.0{ANSI_RESET} – CTI tool to extract and hash images from websites",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-t", "--timeout", type=int, default=DEFAULT_TIMEOUT, help="Network timeout in seconds")
    parser.add_argument("--algo", choices=["sha256", "sha1", "md5"], default=DEFAULT_ALGO, help="Hash algorithm to use")
    parser.add_argument("--user-agent", "-U", dest="user_agent", default=DEFAULT_USER_AGENT, help="Custom User-Agent string")
    parser.add_argument("--delay", type=int, default=DEFAULT_DELAY, help="Seconds to wait between each HTTP request")
    parser.add_argument("--download", action="store_true", help="Download files to disk as you hash them (requires -o)")
    parser.add_argument("-o", "--output-dir", dest="output_dir", default=None, help="Directory to save downloaded images and/or log file")
    parser.add_argument("target", metavar="URL", type=str, nargs="?", help="URL to scan (must begin with http or https)")
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

    for css_url in extractor.css_links:
        try:
            text = fetcher.fetch_text(css_url)
            for ref in STYLE_URL_PATTERN.findall(text):
                extractor._add(ref)
        except (HTTPError, URLError, socket.timeout):
            continue

    results = []

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

    if results and args.output_dir:
        write_log(args.output_dir, args.target, args.algo, ua, results, args.download)
        if args.download:
            print(f"\nAll downloaded images and log file saved into:\n{args.output_dir}")
        else:
            print(f"\nHash results and log file saved into:\n{args.output_dir}")

    print()


if __name__ == "__main__":
    main()
