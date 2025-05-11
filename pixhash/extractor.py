import os
import re
from html.parser import HTMLParser
from typing import List, Set
from urllib.parse import urljoin, urlparse

# Only these schemes are allowed
ALLOWED_SCHEMES = {"http", "https"}

# Whitelist of image file extensions; extensionless URLs remain allowed.
IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico",
    ".svg", ".webp", ".tiff", ".avif",
}

# Regex to pull out url(...) references from inline/CSS code
STYLE_URL_PATTERN = re.compile(
    r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)",
    re.IGNORECASE,
)


class ImageURLExtractor(HTMLParser):
    """
    Parses HTML (and inline <style> or <script>) for any image URLs,
    plus collects <link>ed CSS so the main script can scan them too.
    """

    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base: str = base_url
        self.urls: Set[str] = set()
        self.css_links: List[str] = []
        self._in_style: bool = False
        self._in_script: bool = False

    def handle_starttag(
        self, tag: str, attrs: List[tuple[str, str]]
    ) -> None:
        tag = tag.lower()
        a = dict(attrs)

        if tag in ("img", "source") and "src" in a:
            self._add(a["src"])
        if "srcset" in a:
            for part in a["srcset"].split(","):
                self._add(part.strip().split()[0])

        if tag == "link" and "rel" in a:
            rels = {r.lower() for r in a["rel"].split()}
            if (
                "stylesheet" in rels
                or ("preload" in rels and a.get("as", "").lower() == "style")
            ):
                href = urljoin(self.base, a.get("href", ""))
                if urlparse(href).scheme in ALLOWED_SCHEMES:
                    self.css_links.append(href)
            if any(r.endswith("icon") for r in rels) and "href" in a:
                self._add(a["href"])

        if (
            tag == "meta"
            and a.get("property", "").lower() == "og:image"
            and "content" in a
        ):
            self._add(a["content"])

        if "style" in a:
            for ref in STYLE_URL_PATTERN.findall(a["style"]):
                self._add(ref)

        if tag == "style":
            self._in_style = True
        if tag == "script" and "src" not in a:
            self._in_script = True

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "style":
            self._in_style = False
        if tag == "script":
            self._in_script = False

    def handle_data(self, data: str) -> None:
        if self._in_style or self._in_script:
            for ref in STYLE_URL_PATTERN.findall(data):
                self._add(ref)

    def _add(self, src: str) -> None:
        """
        Normalize & filter a raw URL fragment before adding.
        Skips any non-http(s) or non-image extension.
        """
        full = urljoin(self.base, src.strip())
        p = urlparse(full)
        if p.scheme not in ALLOWED_SCHEMES:
            return
        ext = os.path.splitext(p.path)[1].lower()
        if ext and ext not in IMAGE_EXTENSIONS:
            return
        self.urls.add(full)
