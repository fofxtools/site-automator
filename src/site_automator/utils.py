import logging
import os
import re

_NUMBERED_LINE_RE = re.compile(
    r"""
    ^\s*            # leading whitespace
    (\d+)           # number
    [\.\)\-—:]      # separator: ., ), -, —, :
    \s*             # optional space
    (.+?)           # content
    \s*$            # trailing whitespace
""",
    re.VERBOSE,
)


def parse_numbered_list(text: str) -> list[str]:
    """Parse a numbered list into a list of strings.

    Ignores lines that do not match a numbered format.
    """
    items: list[str] = []

    for line in text.splitlines():
        match = _NUMBERED_LINE_RE.match(line)
        if match:
            items.append(match.group(2).strip())

    return items


def clean_llm_text(text: str) -> str:
    """Clean LLM-generated text by replacing common Unicode characters
    with ASCII equivalents.

    This is a deterministic, character-level cleanup step intended to
    remove common AI-generated typography (smart quotes, dashes, ellipsis,
    bullets, etc.) without changing meaning or structure.
    """

    if not text:
        return text

    replacements = {
        "\u2019": "'",  # ’ right single quote
        "\u2018": "'",  # ‘ left single quote
        "\u201c": '"',  # “ left double quote
        "\u201d": '"',  # ” right double quote
        "\u2013": "-",  # – en dash
        "\u2014": "-",  # — em dash
        "\u2026": "...",  # … ellipsis
        "\u2022": "-",  # • bullet
        "\u00a0": " ",  # non-breaking space
        "\u00ab": '"',  # « left angle quote
        "\u00bb": '"',  # » right angle quote
        "\u2039": "'",  # ‹ left single angle quote
        "\u203a": "'",  # › right single angle quote
        "\u2032": "'",  # ′ prime
        "\u2033": '"',  # ″ double prime
        "\u200b": "",  # zero-width space
        "\u200c": "",  # zero-width non-joiner
        "\u200d": "",  # zero-width joiner
        "\ufeff": "",  # BOM / zero-width no-break space
    }

    for src, dst in replacements.items():
        text = text.replace(src, dst)

    return text


def parse_bool(value: str | None) -> bool:
    if not value:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y"}


def configure_logging(
    console_level: str | None = None,
    format_string: str | None = None,
    silence_paramiko: bool = True,
    silence_httpx: bool = True,
) -> None:
    """Configure logging with console output and optional file logging.

    Args:
        console_level: Console log level (defaults to LOG_LEVEL env var or INFO)
        format_string: Log format string (defaults to standard format)
        silence_paramiko: Whether to silence paramiko's noisy INFO logs
        silence_httpx: Whether to silence httpx's noisy INFO logs
    """
    # Determine console level from parameter or environment variable
    if console_level is None:
        console_level = os.getenv("LOG_LEVEL", "INFO").upper()
    else:
        console_level = console_level.upper()

    # Use default format if not specified
    if format_string is None:
        format_string = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"

    # Configure basic logging
    logging.basicConfig(level=console_level, format=format_string)

    # File logging (if configured via environment)
    log_file = os.getenv("LOG_FILE")
    if log_file:
        log_file_level = os.getenv("LOG_FILE_LEVEL", "ERROR").upper()
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_file_level)
        file_handler.setFormatter(logging.Formatter(format_string))
        logging.getLogger().addHandler(file_handler)

    # Silence noisy third-party loggers
    if silence_paramiko:
        logging.getLogger("paramiko").setLevel(logging.WARNING)
    if silence_httpx:
        logging.getLogger("httpx").setLevel(logging.WARNING)


def validate_domain(domain: str) -> None:
    """Validate domain name.

    Args:
        domain: Domain name to validate

    Raises:
        ValueError: If domain is invalid (empty, contains whitespace, path traversal, or null bytes)
    """
    if not domain:
        raise ValueError("Invalid domain")
    if domain != domain.strip():
        raise ValueError("Invalid domain")
    if domain.startswith(".") or domain.endswith("."):
        raise ValueError("Invalid domain")
    if "/" in domain or ".." in domain or "\x00" in domain:
        raise ValueError("Invalid domain")


def is_local_domain(domain: str) -> bool:
    """Check if domain is a local development domain.

    Returns True if:
    - Domain is exactly "localhost"
    - Domain TLD matches a local-only extension (.test, .local, .localhost, .internal)

    Args:
        domain: Domain name to check

    Returns:
        True if domain is local, False otherwise
    """
    # Check if domain is exactly "localhost"
    if domain == "localhost":
        return True

    # Local-only TLDs (reserved for local development/testing)
    local_tlds = [".test", ".local", ".localhost", ".internal"]

    # Check if domain ends with any local TLD
    return any(domain.endswith(tld) for tld in local_tlds)
