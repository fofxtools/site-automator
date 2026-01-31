import pytest
from unittest.mock import AsyncMock, Mock, patch

from site_automator.llm import (
    OpenAIClient,
    OllamaClient,
    get_llm_client,
    _parse_max_tokens,
    _parse_max_concurrency,
    generate_completion_clean,
    generate_chat_clean,
    generate_completion_bulk_clean,
    generate_chat_bulk_clean,
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


class TestParseMaxConcurrency:
    """Test _parse_max_concurrency helper."""

    @patch("site_automator.llm.os.getenv")
    def test_empty_returns_default(self, mock_getenv):
        mock_getenv.return_value = ""
        assert _parse_max_concurrency() == 10

    @patch("site_automator.llm.os.getenv")
    def test_valid_integer(self, mock_getenv):
        mock_getenv.return_value = "5"
        assert _parse_max_concurrency() == 5

    @patch("site_automator.llm.os.getenv")
    def test_zero_raises(self, mock_getenv):
        mock_getenv.return_value = "0"
        with pytest.raises(ValueError, match="must be >= 1"):
            _parse_max_concurrency()

    @patch("site_automator.llm.os.getenv")
    def test_negative_raises(self, mock_getenv):
        mock_getenv.return_value = "-1"
        with pytest.raises(ValueError, match="must be >= 1"):
            _parse_max_concurrency()

    @patch("site_automator.llm.os.getenv")
    def test_invalid_raises(self, mock_getenv):
        mock_getenv.return_value = "abc"
        with pytest.raises(ValueError):
            _parse_max_concurrency()


class TestOpenAIClientInit:
    """Test OpenAIClient.__init__."""

    def test_init_stores_params(self):
        """Test that parameters are stored correctly."""
        client = OpenAIClient(api_key="test_key", model="gpt-4", max_tokens=100)

        assert client.api_key == "test_key"
        assert client.model == "gpt-4"
        assert client.max_tokens == 100
        assert client.base_url is None
        assert client._client is None

    def test_init_stores_base_url(self):
        """Test that base_url parameter is stored correctly."""
        client = OpenAIClient(
            api_key="test_key", model="gpt-4", base_url="https://api.openrouter.ai/v1"
        )

        assert client.api_key == "test_key"
        assert client.model == "gpt-4"
        assert client.base_url == "https://api.openrouter.ai/v1"
        assert client._client is None


class TestOpenAIClientFromEnv:
    """Test OpenAIClient.from_env."""

    @patch("site_automator.llm._parse_max_tokens")
    @patch("site_automator.llm.os.getenv")
    def test_from_env_success(self, mock_getenv, mock_parse):
        """Test from_env with all required vars."""
        mock_getenv.side_effect = lambda key: {
            "LLM_API_KEY": "test_key",
            "LLM_MODEL": "gpt-4",
        }.get(key)
        mock_parse.return_value = 50

        client = OpenAIClient.from_env()

        assert client.api_key == "test_key"
        assert client.model == "gpt-4"
        assert client.max_tokens == 50
        assert client.base_url is None

    @patch("site_automator.llm._parse_max_tokens")
    @patch("site_automator.llm.os.getenv")
    def test_from_env_with_base_url(self, mock_getenv, mock_parse):
        """Test from_env with LLM_BASE_URL set."""
        mock_getenv.side_effect = lambda key: {
            "LLM_API_KEY": "test_key",
            "LLM_MODEL": "gpt-4",
            "LLM_BASE_URL": "https://api.openrouter.ai/v1",
        }.get(key)
        mock_parse.return_value = 50

        client = OpenAIClient.from_env()

        assert client.api_key == "test_key"
        assert client.model == "gpt-4"
        assert client.max_tokens == 50
        assert client.base_url == "https://api.openrouter.ai/v1"

    @patch("site_automator.llm._parse_max_tokens")
    @patch("site_automator.llm.os.getenv")
    def test_from_env_with_empty_base_url(self, mock_getenv, mock_parse):
        """Test from_env with empty LLM_BASE_URL."""
        mock_getenv.side_effect = lambda key: {
            "LLM_API_KEY": "test_key",
            "LLM_MODEL": "gpt-4",
            "LLM_BASE_URL": "",
        }.get(key)
        mock_parse.return_value = 50

        client = OpenAIClient.from_env()

        assert client.base_url is None

    @patch("site_automator.llm.os.getenv")
    def test_from_env_missing_api_key(self, mock_getenv):
        """Test from_env raises when LLM_API_KEY missing."""
        mock_getenv.return_value = None

        with pytest.raises(ValueError, match="LLM_API_KEY"):
            OpenAIClient.from_env()

    @patch("site_automator.llm.os.getenv")
    def test_from_env_missing_model(self, mock_getenv):
        """Test from_env raises when LLM_MODEL missing."""
        mock_getenv.side_effect = lambda key: {
            "LLM_API_KEY": "test_key",
            "LLM_MODEL": None,
        }.get(key)

        with pytest.raises(ValueError, match="LLM_MODEL"):
            OpenAIClient.from_env()


class TestOpenAIClientGenerateCompletion:
    """Test OpenAIClient.generate_completion."""

    @patch("site_automator.llm.OpenAI")
    def test_generate_completion_without_max_tokens(self, mock_openai_class):
        """Test generate_completion without max_tokens."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        mock_response = Mock()
        mock_response.output_text = "Hello"
        mock_client.responses.create.return_value = mock_response

        client = OpenAIClient(api_key="key", model="gpt-4", max_tokens=None)
        result = client.generate_completion("test prompt")

        assert result == "Hello"
        mock_client.responses.create.assert_called_once_with(
            model="gpt-4",
            input="test prompt",
        )

    @patch("site_automator.llm.OpenAI")
    def test_generate_completion_with_max_tokens(self, mock_openai_class):
        """Test generate_completion with max_tokens."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        mock_response = Mock()
        mock_response.output_text = "Hello"
        mock_client.responses.create.return_value = mock_response

        client = OpenAIClient(api_key="key", model="gpt-4", max_tokens=50)
        result = client.generate_completion("test prompt")

        assert result == "Hello"
        mock_client.responses.create.assert_called_once_with(
            model="gpt-4",
            input="test prompt",
            max_output_tokens=50,
        )

    @patch("site_automator.llm.OpenAI")
    def test_generate_completion_empty_response(self, mock_openai_class):
        """Test generate_completion returns empty string when output_text is None."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        mock_response = Mock()
        mock_response.output_text = None
        mock_client.responses.create.return_value = mock_response

        client = OpenAIClient(api_key="key", model="gpt-4")
        result = client.generate_completion("test")

        assert result == ""

    @patch("site_automator.llm.OpenAI")
    def test_generate_completion_with_base_url(self, mock_openai_class):
        """Test that base_url is passed to OpenAI client when set."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        mock_response = Mock()
        mock_response.output_text = "Hello"
        mock_client.responses.create.return_value = mock_response

        client = OpenAIClient(
            api_key="key", model="gpt-4", base_url="https://api.openrouter.ai/v1"
        )
        result = client.generate_completion("test")

        assert result == "Hello"
        mock_openai_class.assert_called_once_with(
            api_key="key", base_url="https://api.openrouter.ai/v1"
        )

    @patch("site_automator.llm.OpenAI")
    def test_generate_completion_without_base_url(self, mock_openai_class):
        """Test that base_url is not passed to OpenAI client when None."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        mock_response = Mock()
        mock_response.output_text = "Hello"
        mock_client.responses.create.return_value = mock_response

        client = OpenAIClient(api_key="key", model="gpt-4", base_url=None)
        result = client.generate_completion("test")

        assert result == "Hello"
        mock_openai_class.assert_called_once_with(api_key="key")


class TestOpenAIClientGenerateChat:
    """Test OpenAIClient.generate_chat."""

    @patch("site_automator.llm.OpenAI")
    def test_generate_chat_without_max_tokens(self, mock_openai_class):
        """Test generate_chat without max_tokens."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        mock_response = Mock()
        mock_response.output_text = "Hello from chat"
        mock_client.responses.create.return_value = mock_response

        client = OpenAIClient(api_key="key", model="gpt-4", max_tokens=None)
        messages = [{"role": "user", "content": "test message"}]
        result = client.generate_chat(messages)

        assert result == "Hello from chat"
        mock_client.responses.create.assert_called_once_with(
            model="gpt-4",
            input=messages,
        )

    @patch("site_automator.llm.OpenAI")
    def test_generate_chat_with_max_tokens(self, mock_openai_class):
        """Test generate_chat with max_tokens."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        mock_response = Mock()
        mock_response.output_text = "Hello"
        mock_client.responses.create.return_value = mock_response

        client = OpenAIClient(api_key="key", model="gpt-4", max_tokens=50)
        messages = [{"role": "user", "content": "test"}]
        result = client.generate_chat(messages)

        assert result == "Hello"
        mock_client.responses.create.assert_called_once_with(
            model="gpt-4",
            input=messages,
            max_output_tokens=50,
        )


class TestOpenAIClientGenerateCompletionBulk:
    """Test OpenAIClient.generate_completion_bulk."""

    @patch("site_automator.llm._parse_max_concurrency", return_value=10)
    @patch("site_automator.llm.AsyncOpenAI")
    def test_returns_results_in_order(self, mock_async_class, _mock_conc):
        mock_client = AsyncMock()
        mock_async_class.return_value = mock_client

        resp1 = Mock(output_text="Result 1")
        resp2 = Mock(output_text="Result 2")
        resp3 = Mock(output_text="Result 3")
        mock_client.responses.create = AsyncMock(side_effect=[resp1, resp2, resp3])

        client = OpenAIClient(api_key="key", model="gpt-4")
        results = client.generate_completion_bulk(["p1", "p2", "p3"])

        assert results == ["Result 1", "Result 2", "Result 3"]
        assert mock_client.responses.create.call_count == 3

    @patch("site_automator.llm._parse_max_concurrency", return_value=10)
    @patch("site_automator.llm.AsyncOpenAI")
    def test_empty_list(self, mock_async_class, _mock_conc):
        client = OpenAIClient(api_key="key", model="gpt-4")
        assert client.generate_completion_bulk([]) == []

    @patch("site_automator.llm._parse_max_concurrency", return_value=10)
    @patch("site_automator.llm.AsyncOpenAI")
    def test_partial_failure_returns_none(self, mock_async_class, _mock_conc):
        mock_client = AsyncMock()
        mock_async_class.return_value = mock_client

        resp1 = Mock(output_text="Result 1")
        mock_client.responses.create = AsyncMock(
            side_effect=[resp1, RuntimeError("API down"), Mock(output_text="Result 3")]
        )

        client = OpenAIClient(api_key="key", model="gpt-4")
        results = client.generate_completion_bulk(["p1", "p2", "p3"])

        assert results == ["Result 1", None, "Result 3"]


class TestOpenAIClientGenerateChatBulk:
    """Test OpenAIClient.generate_chat_bulk."""

    @patch("site_automator.llm._parse_max_concurrency", return_value=10)
    @patch("site_automator.llm.AsyncOpenAI")
    def test_returns_results_in_order(self, mock_async_class, _mock_conc):
        mock_client = AsyncMock()
        mock_async_class.return_value = mock_client

        resp1 = Mock(output_text="Chat 1")
        resp2 = Mock(output_text="Chat 2")
        mock_client.responses.create = AsyncMock(side_effect=[resp1, resp2])

        client = OpenAIClient(api_key="key", model="gpt-4")
        msgs = [
            [{"role": "user", "content": "a"}],
            [{"role": "user", "content": "b"}],
        ]
        results = client.generate_chat_bulk(msgs)

        assert results == ["Chat 1", "Chat 2"]
        assert mock_client.responses.create.call_count == 2

    @patch("site_automator.llm._parse_max_concurrency", return_value=10)
    @patch("site_automator.llm.AsyncOpenAI")
    def test_partial_failure_returns_none(self, mock_async_class, _mock_conc):
        mock_client = AsyncMock()
        mock_async_class.return_value = mock_client

        mock_client.responses.create = AsyncMock(
            side_effect=[Mock(output_text="Chat 1"), RuntimeError("fail")]
        )

        client = OpenAIClient(api_key="key", model="gpt-4")
        msgs = [
            [{"role": "user", "content": "a"}],
            [{"role": "user", "content": "b"}],
        ]
        results = client.generate_chat_bulk(msgs)

        assert results == ["Chat 1", None]


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


class TestOllamaClientGenerateCompletion:
    """Test OllamaClient.generate_completion."""

    @patch("site_automator.llm.ollama.generate")
    def test_generate_completion_without_max_tokens(self, mock_generate):
        """Test generate_completion without max_tokens."""
        mock_generate.return_value = {"response": "Hello from Ollama"}

        client = OllamaClient(model="llama3.1:8b", max_tokens=None)
        result = client.generate_completion("test prompt")

        assert result == "Hello from Ollama"
        mock_generate.assert_called_once_with(
            model="llama3.1:8b",
            prompt="test prompt",
        )

    @patch("site_automator.llm.ollama.generate")
    def test_generate_completion_with_max_tokens(self, mock_generate):
        """Test generate_completion with max_tokens."""
        mock_generate.return_value = {"response": "Hello"}

        client = OllamaClient(model="llama3.1:8b", max_tokens=50)
        result = client.generate_completion("test prompt")

        assert result == "Hello"
        mock_generate.assert_called_once_with(
            model="llama3.1:8b",
            prompt="test prompt",
            options={"num_predict": 50},
        )

    @patch("site_automator.llm.ollama.generate")
    def test_generate_completion_empty_response(self, mock_generate):
        """Test generate_completion returns empty string when response is None."""
        mock_generate.return_value = {"response": None}

        client = OllamaClient(model="llama3.1:8b")
        result = client.generate_completion("test")

        assert result == ""


class TestOllamaClientGenerateChat:
    """Test OllamaClient.generate_chat."""

    @patch("site_automator.llm.ollama.chat")
    def test_generate_chat_without_max_tokens(self, mock_chat):
        """Test generate_chat without max_tokens."""
        mock_chat.return_value = {"message": {"content": "Hello from chat"}}

        client = OllamaClient(model="llama3.1:8b", max_tokens=None)
        messages = [{"role": "user", "content": "test message"}]
        result = client.generate_chat(messages)

        assert result == "Hello from chat"
        mock_chat.assert_called_once_with(
            model="llama3.1:8b",
            messages=messages,
        )

    @patch("site_automator.llm.ollama.chat")
    def test_generate_chat_with_max_tokens(self, mock_chat):
        """Test generate_chat with max_tokens."""
        mock_chat.return_value = {"message": {"content": "Hello"}}

        client = OllamaClient(model="llama3.1:8b", max_tokens=50)
        messages = [{"role": "user", "content": "test"}]
        result = client.generate_chat(messages)

        assert result == "Hello"
        mock_chat.assert_called_once_with(
            model="llama3.1:8b",
            messages=messages,
            options={"num_predict": 50},
        )

    @patch("site_automator.llm.ollama.chat")
    def test_generate_chat_empty_response(self, mock_chat):
        """Test generate_chat returns empty string when content is None."""
        mock_chat.return_value = {"message": {"content": None}}

        client = OllamaClient(model="llama3.1:8b")
        messages = [{"role": "user", "content": "test"}]
        result = client.generate_chat(messages)

        assert result == ""


class TestOllamaClientGenerateCompletionBulk:
    """Test OllamaClient.generate_completion_bulk."""

    @patch("site_automator.llm.ollama.generate")
    def test_returns_results_in_order(self, mock_generate):
        mock_generate.side_effect = [
            {"response": "Ollama 1"},
            {"response": "Ollama 2"},
        ]

        client = OllamaClient(model="llama3.1:8b")
        results = client.generate_completion_bulk(["p1", "p2"])

        assert results == ["Ollama 1", "Ollama 2"]
        assert mock_generate.call_count == 2

    @patch("site_automator.llm.ollama.generate")
    def test_empty_list(self, mock_generate):
        client = OllamaClient(model="llama3.1:8b")
        assert client.generate_completion_bulk([]) == []
        mock_generate.assert_not_called()

    @patch("site_automator.llm.ollama.generate")
    def test_partial_failure_returns_none(self, mock_generate):
        mock_generate.side_effect = [
            {"response": "Ollama 1"},
            RuntimeError("fail"),
            {"response": "Ollama 3"},
        ]

        client = OllamaClient(model="llama3.1:8b")
        results = client.generate_completion_bulk(["p1", "p2", "p3"])

        assert results == ["Ollama 1", None, "Ollama 3"]


class TestOllamaClientGenerateChatBulk:
    """Test OllamaClient.generate_chat_bulk."""

    @patch("site_automator.llm.ollama.chat")
    def test_returns_results_in_order(self, mock_chat):
        mock_chat.side_effect = [
            {"message": {"content": "Chat A"}},
            {"message": {"content": "Chat B"}},
        ]

        client = OllamaClient(model="llama3.1:8b")
        msgs = [
            [{"role": "user", "content": "a"}],
            [{"role": "user", "content": "b"}],
        ]
        results = client.generate_chat_bulk(msgs)

        assert results == ["Chat A", "Chat B"]
        assert mock_chat.call_count == 2

    @patch("site_automator.llm.ollama.chat")
    def test_partial_failure_returns_none(self, mock_chat):
        mock_chat.side_effect = [
            RuntimeError("fail"),
            {"message": {"content": "Chat B"}},
        ]

        client = OllamaClient(model="llama3.1:8b")
        msgs = [
            [{"role": "user", "content": "a"}],
            [{"role": "user", "content": "b"}],
        ]
        results = client.generate_chat_bulk(msgs)

        assert results == [None, "Chat B"]


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


class TestGenerateCompletionClean:
    """Test generate_completion_clean function."""

    @patch("site_automator.llm.get_llm_client")
    @patch("site_automator.llm.clean_llm_text")
    def test_calls_client_and_cleans(self, mock_clean, mock_get_client):
        """Test that it calls client and applies cleaning."""
        mock_client = Mock()
        mock_client.generate_completion.return_value = "raw\u2019text"
        mock_get_client.return_value = mock_client
        mock_clean.return_value = "raw'text"

        result = generate_completion_clean("test prompt")

        assert result == "raw'text"
        mock_get_client.assert_called_once()
        mock_client.generate_completion.assert_called_once_with("test prompt")
        mock_clean.assert_called_once_with("raw\u2019text")

    @patch("site_automator.llm.get_llm_client")
    def test_cleaning_applied(self, mock_get_client):
        """Test that cleaning is actually applied to output."""
        mock_client = Mock()
        # Return text with Unicode characters that should be cleaned
        mock_client.generate_completion.return_value = "It\u2019s a \u201ctest\u201d"
        mock_get_client.return_value = mock_client

        result = generate_completion_clean("test")

        # Verify cleaning was applied (smart quotes -> ASCII)
        assert result == 'It\'s a "test"'


class TestGenerateChatClean:
    """Test generate_chat_clean function."""

    @patch("site_automator.llm.get_llm_client")
    @patch("site_automator.llm.clean_llm_text")
    def test_calls_client_and_cleans(self, mock_clean, mock_get_client):
        """Test that it calls client and applies cleaning."""
        mock_client = Mock()
        mock_client.generate_chat.return_value = "raw\u2014text"
        mock_get_client.return_value = mock_client
        mock_clean.return_value = "raw-text"

        messages = [{"role": "user", "content": "test"}]
        result = generate_chat_clean(messages)

        assert result == "raw-text"
        mock_get_client.assert_called_once()
        mock_client.generate_chat.assert_called_once_with(messages)
        mock_clean.assert_called_once_with("raw\u2014text")

    @patch("site_automator.llm.get_llm_client")
    def test_cleaning_applied(self, mock_get_client):
        """Test that cleaning is actually applied to output."""
        mock_client = Mock()
        # Return text with Unicode characters that should be cleaned
        mock_client.generate_chat.return_value = "Hello\u2026 it\u2019s working"
        mock_get_client.return_value = mock_client

        messages = [{"role": "user", "content": "test"}]
        result = generate_chat_clean(messages)

        # Verify cleaning was applied (ellipsis and smart quote -> ASCII)
        assert result == "Hello... it's working"


class TestGenerateCompletionBulkClean:
    """Test generate_completion_bulk_clean function."""

    @patch("site_automator.llm.get_llm_client")
    @patch("site_automator.llm.clean_llm_text")
    def test_calls_bulk_and_cleans_each(self, mock_clean, mock_get_client):
        mock_client = Mock()
        mock_client.generate_completion_bulk.return_value = ["raw1", "raw2"]
        mock_get_client.return_value = mock_client
        mock_clean.side_effect = ["clean1", "clean2"]

        results = generate_completion_bulk_clean(["p1", "p2"])

        assert results == ["clean1", "clean2"]
        mock_client.generate_completion_bulk.assert_called_once_with(["p1", "p2"])
        assert mock_clean.call_count == 2

    @patch("site_automator.llm.get_llm_client")
    @patch("site_automator.llm.clean_llm_text")
    def test_none_passthrough(self, mock_clean, mock_get_client):
        mock_client = Mock()
        mock_client.generate_completion_bulk.return_value = ["raw1", None, "raw3"]
        mock_get_client.return_value = mock_client
        mock_clean.side_effect = ["clean1", "clean3"]

        results = generate_completion_bulk_clean(["p1", "p2", "p3"])

        assert results == ["clean1", None, "clean3"]
        assert mock_clean.call_count == 2


class TestGenerateChatBulkClean:
    """Test generate_chat_bulk_clean function."""

    @patch("site_automator.llm.get_llm_client")
    @patch("site_automator.llm.clean_llm_text")
    def test_calls_bulk_and_cleans_each(self, mock_clean, mock_get_client):
        mock_client = Mock()
        mock_client.generate_chat_bulk.return_value = ["raw1", "raw2"]
        mock_get_client.return_value = mock_client
        mock_clean.side_effect = ["clean1", "clean2"]

        msgs = [[{"role": "user", "content": "a"}], [{"role": "user", "content": "b"}]]
        results = generate_chat_bulk_clean(msgs)

        assert results == ["clean1", "clean2"]
        mock_client.generate_chat_bulk.assert_called_once_with(msgs)
        assert mock_clean.call_count == 2

    @patch("site_automator.llm.get_llm_client")
    @patch("site_automator.llm.clean_llm_text")
    def test_none_passthrough(self, mock_clean, mock_get_client):
        mock_client = Mock()
        mock_client.generate_chat_bulk.return_value = [None, "raw2"]
        mock_get_client.return_value = mock_client
        mock_clean.side_effect = ["clean2"]

        msgs = [[{"role": "user", "content": "a"}], [{"role": "user", "content": "b"}]]
        results = generate_chat_bulk_clean(msgs)

        assert results == [None, "clean2"]
        assert mock_clean.call_count == 1
