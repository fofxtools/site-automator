import pytest
from unittest.mock import Mock, patch

from site_automator.llm import (
    OpenAIClient,
    OllamaClient,
    get_llm_client,
    _parse_max_tokens,
)


class TestParseMaxTokens:
    """Test _parse_max_tokens helper."""

    @patch("site_automator.llm.os.getenv")
    def test_empty_string_returns_none(self, mock_getenv):
        """Test empty string returns None."""
        mock_getenv.return_value = ""
        assert _parse_max_tokens() is None

    @patch("site_automator.llm.os.getenv")
    def test_zero_returns_none(self, mock_getenv):
        """Test zero returns None."""
        mock_getenv.return_value = "0"
        assert _parse_max_tokens() is None

    @patch("site_automator.llm.os.getenv")
    def test_valid_integer(self, mock_getenv):
        """Test valid integer is parsed."""
        mock_getenv.return_value = "100"
        assert _parse_max_tokens() == 100

    @patch("site_automator.llm.os.getenv")
    def test_invalid_integer_raises(self, mock_getenv):
        """Test invalid integer raises ValueError."""
        mock_getenv.return_value = "not_a_number"
        with pytest.raises(ValueError):
            _parse_max_tokens()


class TestOpenAIClientInit:
    """Test OpenAIClient.__init__."""

    def test_init_stores_params(self):
        """Test that parameters are stored correctly."""
        client = OpenAIClient(api_key="test_key", model="gpt-4", max_tokens=100)

        assert client.api_key == "test_key"
        assert client.model == "gpt-4"
        assert client.max_tokens == 100
        assert client._client is None


class TestOpenAIClientFromEnv:
    """Test OpenAIClient.from_env."""

    @patch("site_automator.llm._parse_max_tokens")
    @patch("site_automator.llm.os.getenv")
    def test_from_env_success(self, mock_getenv, mock_parse):
        """Test from_env with all required vars."""
        mock_getenv.side_effect = lambda key: {
            "OPENAI_API_KEY": "test_key",
            "LLM_MODEL": "gpt-4",
        }.get(key)
        mock_parse.return_value = 50

        client = OpenAIClient.from_env()

        assert client.api_key == "test_key"
        assert client.model == "gpt-4"
        assert client.max_tokens == 50

    @patch("site_automator.llm.os.getenv")
    def test_from_env_missing_api_key(self, mock_getenv):
        """Test from_env raises when OPENAI_API_KEY missing."""
        mock_getenv.return_value = None

        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            OpenAIClient.from_env()

    @patch("site_automator.llm.os.getenv")
    def test_from_env_missing_model(self, mock_getenv):
        """Test from_env raises when LLM_MODEL missing."""
        mock_getenv.side_effect = lambda key: {
            "OPENAI_API_KEY": "test_key",
            "LLM_MODEL": None,
        }.get(key)

        with pytest.raises(ValueError, match="LLM_MODEL"):
            OpenAIClient.from_env()


class TestOpenAIClientGenerate:
    """Test OpenAIClient.generate."""

    @patch("site_automator.llm.OpenAI")
    def test_generate_without_max_tokens(self, mock_openai_class):
        """Test generate without max_tokens."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        mock_response = Mock()
        mock_response.output_text = "Hello"
        mock_client.responses.create.return_value = mock_response

        client = OpenAIClient(api_key="key", model="gpt-4", max_tokens=None)
        result = client.generate("test prompt")

        assert result == "Hello"
        mock_client.responses.create.assert_called_once_with(
            model="gpt-4",
            input="test prompt",
        )

    @patch("site_automator.llm.OpenAI")
    def test_generate_with_max_tokens(self, mock_openai_class):
        """Test generate with max_tokens."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        mock_response = Mock()
        mock_response.output_text = "Hello"
        mock_client.responses.create.return_value = mock_response

        client = OpenAIClient(api_key="key", model="gpt-4", max_tokens=50)
        result = client.generate("test prompt")

        assert result == "Hello"
        mock_client.responses.create.assert_called_once_with(
            model="gpt-4",
            input="test prompt",
            max_output_tokens=50,
        )

    @patch("site_automator.llm.OpenAI")
    def test_generate_empty_response(self, mock_openai_class):
        """Test generate returns empty string when output_text is None."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        mock_response = Mock()
        mock_response.output_text = None
        mock_client.responses.create.return_value = mock_response

        client = OpenAIClient(api_key="key", model="gpt-4")
        result = client.generate("test")

        assert result == ""


class TestOllamaClientInit:
    """Test OllamaClient.__init__."""

    def test_init_stores_params(self):
        """Test that parameters are stored correctly."""
        client = OllamaClient(model="llama3.1:8b", max_tokens=100)

        assert client.model == "llama3.1:8b"
        assert client.max_tokens == 100


class TestOllamaClientFromEnv:
    """Test OllamaClient.from_env."""

    @patch("site_automator.llm._parse_max_tokens")
    @patch("site_automator.llm.os.getenv")
    def test_from_env_success(self, mock_getenv, mock_parse):
        """Test from_env with all required vars."""
        mock_getenv.return_value = "llama3.1:8b"
        mock_parse.return_value = 50

        client = OllamaClient.from_env()

        assert client.model == "llama3.1:8b"
        assert client.max_tokens == 50

    @patch("site_automator.llm.os.getenv")
    def test_from_env_missing_model(self, mock_getenv):
        """Test from_env raises when LLM_MODEL missing."""
        mock_getenv.return_value = None

        with pytest.raises(ValueError, match="LLM_MODEL"):
            OllamaClient.from_env()


class TestOllamaClientGenerate:
    """Test OllamaClient.generate."""

    @patch("site_automator.llm.ollama.chat")
    def test_generate_without_max_tokens(self, mock_chat):
        """Test generate without max_tokens."""
        mock_chat.return_value = {"message": {"content": "Hello from Ollama"}}

        client = OllamaClient(model="llama3.1:8b", max_tokens=None)
        result = client.generate("test prompt")

        assert result == "Hello from Ollama"
        mock_chat.assert_called_once_with(
            model="llama3.1:8b",
            messages=[{"role": "user", "content": "test prompt"}],
        )

    @patch("site_automator.llm.ollama.chat")
    def test_generate_with_max_tokens(self, mock_chat):
        """Test generate with max_tokens."""
        mock_chat.return_value = {"message": {"content": "Hello"}}

        client = OllamaClient(model="llama3.1:8b", max_tokens=50)
        result = client.generate("test prompt")

        assert result == "Hello"
        mock_chat.assert_called_once_with(
            model="llama3.1:8b",
            messages=[{"role": "user", "content": "test prompt"}],
            options={"num_predict": 50},
        )

    @patch("site_automator.llm.ollama.chat")
    def test_generate_empty_response(self, mock_chat):
        """Test generate returns empty string when content is None."""
        mock_chat.return_value = {"message": {"content": None}}

        client = OllamaClient(model="llama3.1:8b")
        result = client.generate("test")

        assert result == ""


class TestGetLlmClient:
    """Test get_llm_client factory."""

    @patch("site_automator.llm.OpenAIClient.from_env")
    @patch("site_automator.llm.os.getenv")
    def test_get_openai_client(self, mock_getenv, mock_from_env):
        """Test factory returns OpenAI client."""
        mock_getenv.return_value = "openai"
        mock_client = Mock()
        mock_from_env.return_value = mock_client

        result = get_llm_client()

        assert result == mock_client
        mock_from_env.assert_called_once()

    @patch("site_automator.llm.OllamaClient.from_env")
    @patch("site_automator.llm.os.getenv")
    def test_get_ollama_client(self, mock_getenv, mock_from_env):
        """Test factory returns Ollama client."""
        mock_getenv.return_value = "ollama"
        mock_client = Mock()
        mock_from_env.return_value = mock_client

        result = get_llm_client()

        assert result == mock_client
        mock_from_env.assert_called_once()

    @patch("site_automator.llm.os.getenv")
    def test_missing_provider_raises(self, mock_getenv):
        """Test missing LLM_PROVIDER raises ValueError."""
        mock_getenv.return_value = None

        with pytest.raises(ValueError, match="LLM_PROVIDER"):
            get_llm_client()

    @patch("site_automator.llm.os.getenv")
    def test_invalid_provider_raises(self, mock_getenv):
        """Test invalid LLM_PROVIDER raises ValueError."""
        mock_getenv.return_value = "invalid"

        with pytest.raises(ValueError, match="Invalid LLM_PROVIDER"):
            get_llm_client()
