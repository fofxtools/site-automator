import logging
import os
from unittest.mock import patch

from site_automator.utils import (
    parse_numbered_list,
    clean_llm_text,
    parse_bool,
    configure_logging,
)


class TestParseNumberedList:
    def test_basic(self):
        text = "1. First\n2. Second\n3. Third"
        assert parse_numbered_list(text) == ["First", "Second", "Third"]

    def test_ignores_non_numbered_lines(self):
        text = "Here are titles:\n\n1. Real title\nrandom junk\n2. Another title\n"
        assert parse_numbered_list(text) == ["Real title", "Another title"]

    def test_separators(self):
        assert parse_numbered_list("1) Paren") == ["Paren"]
        assert parse_numbered_list("1- Hyphen") == ["Hyphen"]
        assert parse_numbered_list("1: Colon") == ["Colon"]
        assert parse_numbered_list("1\u2014 Emdash") == ["Emdash"]

    def test_strips_whitespace(self):
        text = "  1.  Padded item  \n"
        assert parse_numbered_list(text) == ["Padded item"]

    def test_empty_input(self):
        assert parse_numbered_list("") == []


class TestCleanLlmText:
    def test_smart_quotes_and_dashes(self):
        text = "\u201cIt\u2019s an em\u2014dash\u201d"
        assert clean_llm_text(text) == '"It\'s an em-dash"'

    def test_zero_width_characters_stripped(self):
        text = "hello\u200bworld\ufeff"
        assert clean_llm_text(text) == "helloworld"

    def test_plain_ascii_unchanged(self):
        text = "Nothing special here."
        assert clean_llm_text(text) == "Nothing special here."

    def test_empty_input(self):
        assert clean_llm_text("") == ""


class TestParseBool:
    def test_truthy_values(self):
        for val in ("true", "True", "TRUE", "1", "yes", "y", "Y"):
            assert parse_bool(val) is True

    def test_falsy_values(self):
        for val in ("false", "0", "no", "n", "anything", ""):
            assert parse_bool(val) is False

    def test_none(self):
        assert parse_bool(None) is False

    def test_whitespace_stripped(self):
        assert parse_bool("  true  ") is True
        assert parse_bool("  false  ") is False


class TestConfigureLogging:
    def test_basic_configuration(self):
        """Test basic logging configuration with defaults."""
        # Reset logging to ensure clean state
        logging.root.handlers = []

        configure_logging()

        # Verify root logger is configured
        assert logging.root.level == logging.INFO
        assert len(logging.root.handlers) > 0

        # Verify paramiko and httpx are silenced
        assert logging.getLogger("paramiko").level == logging.WARNING
        assert logging.getLogger("httpx").level == logging.WARNING

    def test_custom_console_level(self):
        """Test configuring custom console level."""
        # Reset logging
        logging.root.handlers = []

        configure_logging(console_level="DEBUG")

        assert logging.root.level == logging.DEBUG

    def test_env_var_log_level(self):
        """Test LOG_LEVEL environment variable is respected."""
        # Reset logging
        logging.root.handlers = []

        with patch.dict(os.environ, {"LOG_LEVEL": "WARNING"}):
            configure_logging()
            assert logging.root.level == logging.WARNING

    def test_silence_flags(self):
        """Test that silence flags work correctly."""
        # Reset logging
        logging.root.handlers = []

        # Test with silence flags disabled
        configure_logging(silence_paramiko=False, silence_httpx=False)

        # Loggers should not be at WARNING level (would be at root level)
        # We just verify the function doesn't crash and runs successfully
        assert logging.root.level == logging.INFO
