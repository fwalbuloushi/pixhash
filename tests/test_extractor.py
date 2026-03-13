import unittest
from pixhash.extractor import ImageURLExtractor


BASE = "https://www.wikipedia.org"


def extract(html: str, base: str = BASE) -> set:
    e = ImageURLExtractor(base)
    e.feed(html)
    return e.urls


class TestImgTag(unittest.TestCase):
    def test_img_src(self):
        urls = extract('<img src="/static/images/wikipedia-logo.png">')
        self.assertIn("https://www.wikipedia.org/static/images/wikipedia-logo.png", urls)

    def test_img_absolute_src(self):
        urls = extract('<img src="https://upload.wikimedia.org/wikipedia/commons/logo.png">')
        self.assertIn("https://upload.wikimedia.org/wikipedia/commons/logo.png", urls)

    def test_img_srcset(self):
        urls = extract('<img srcset="/static/images/logo.png 1x, /static/images/logo@2x.png 2x">')
        self.assertIn("https://www.wikipedia.org/static/images/logo.png", urls)
        self.assertIn("https://www.wikipedia.org/static/images/logo@2x.png", urls)

    def test_source_tag(self):
        urls = extract('<source src="/portal/wikipedia.org/assets/img/Wikipedia-logo-v2.png">')
        self.assertIn("https://www.wikipedia.org/portal/wikipedia.org/assets/img/Wikipedia-logo-v2.png", urls)


class TestMetaAndIcons(unittest.TestCase):
    def test_og_image(self):
        urls = extract('<meta property="og:image" content="https://upload.wikimedia.org/wikipedia/commons/og.jpg">')
        self.assertIn("https://upload.wikimedia.org/wikipedia/commons/og.jpg", urls)

    def test_favicon(self):
        urls = extract('<link rel="icon" href="/static/favicon/wikipedia.ico">')
        self.assertIn("https://www.wikipedia.org/static/favicon/wikipedia.ico", urls)

    def test_apple_touch_icon(self):
        urls = extract('<link rel="apple-touch-icon" href="/static/apple-touch/wikipedia.png">')
        self.assertIn("https://www.wikipedia.org/static/apple-touch/wikipedia.png", urls)


class TestInlineStyle(unittest.TestCase):
    def test_inline_style_url(self):
        urls = extract('<div style="background: url(\'/portal/wikipedia.org/assets/img/sprite.svg\')"></div>')
        self.assertIn("https://www.wikipedia.org/portal/wikipedia.org/assets/img/sprite.svg", urls)

    def test_style_tag(self):
        urls = extract("<style>body { background: url('/portal/wikipedia.org/assets/img/sprite.svg'); }</style>")
        self.assertIn("https://www.wikipedia.org/portal/wikipedia.org/assets/img/sprite.svg", urls)


class TestCSSLinks(unittest.TestCase):
    def test_stylesheet_collected(self):
        e = ImageURLExtractor(BASE)
        e.feed('<link rel="stylesheet" href="/portal/wikipedia.org/assets/css/bootstrap.min.css">')
        self.assertIn("https://www.wikipedia.org/portal/wikipedia.org/assets/css/bootstrap.min.css", e.css_links)

    def test_non_stylesheet_not_collected(self):
        e = ImageURLExtractor(BASE)
        e.feed('<link rel="canonical" href="/wiki/Main_Page">')
        self.assertEqual(e.css_links, [])


class TestFiltering(unittest.TestCase):
    def test_non_image_extension_filtered(self):
        urls = extract('<img src="/portal/wikipedia.org/assets/js/index.js">')
        self.assertEqual(urls, set())

    def test_data_uri_filtered(self):
        urls = extract('<img src="data:image/png;base64,abc123">')
        self.assertEqual(urls, set())

    def test_extensionless_url_allowed(self):
        urls = extract('<img src="https://upload.wikimedia.org/wikipedia/commons/thumb/image-endpoint">')
        self.assertIn("https://upload.wikimedia.org/wikipedia/commons/thumb/image-endpoint", urls)


if __name__ == "__main__":
    unittest.main()
