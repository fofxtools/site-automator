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
