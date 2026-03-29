DEFAULT_TIMEOUT: int = 10
DEFAULT_ALGO: str = "sha256"
DEFAULT_DELAY: int = 0
DEFAULT_USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) "
    "Gecko/20100101 Firefox/115.0"
)

# Cap response reads at 50 MB to prevent memory exhaustion
MAX_RESPONSE_BYTES: int = 52_428_800
# Default ceiling on images processed per run
MAX_IMAGES: int = 500

ANSI_BOLD_RED: str    = "\033[1;31m"
ANSI_BOLD_YELLOW: str = "\033[1;33m"
ANSI_RESET: str       = "\033[0m"
