"""LLM client implementations for OpenAI and Ollama."""

import logging
import os
from typing import Any

import ollama
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables once at module import
load_dotenv()

logger = logging.getLogger(__name__)


def _parse_max_tokens() -> int | None:
    """Parse LLM_MAX_TOKENS environment variable.

    Returns:
        Max tokens as int, or None if unset/empty/0

    Raises:
        ValueError: If LLM_MAX_TOKENS is not a valid integer
    """
    max_tokens_str = os.getenv("LLM_MAX_TOKENS", "").strip()
    if not max_tokens_str:
        return None

    max_tokens = int(max_tokens_str)  # Fail fast if not an integer
    return None if max_tokens == 0 else max_tokens


class OpenAIClient:
    """OpenAI API client using the Responses API."""

    api_key: str
    model: str
    max_tokens: int | None
    _client: OpenAI | None

    def __init__(self, api_key: str, model: str, max_tokens: int | None = None) -> None:
        """Initialize OpenAI client.

        Args:
            api_key: OpenAI API key
            model: Model name (e.g., "gpt-4.1-nano")
            max_tokens: Maximum tokens to generate (None for backend default)
        """
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self._client: OpenAI | None = None

    @classmethod
    def from_env(cls) -> "OpenAIClient":
        """Create OpenAI client from environment variables.

        Expects environment variables:
            - OPENAI_API_KEY: OpenAI API key
            - LLM_MODEL: Model name (e.g., "gpt-4.1-nano")
            - LLM_MAX_TOKENS: Max tokens (optional, empty or 0 = unset)

        Returns:
            OpenAIClient instance

        Raises:
            ValueError: If required environment variables are missing
        """
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        model = os.getenv("LLM_MODEL")
        if not model:
            raise ValueError("LLM_MODEL environment variable is required")

        max_tokens = _parse_max_tokens()

        return cls(api_key=api_key, model=model, max_tokens=max_tokens)

    def _get_client(self) -> OpenAI:
        """Get or create OpenAI client instance.

        Returns:
            OpenAI client instance
        """
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key)

        return self._client

    def generate_completion(self, prompt: str) -> str:
        """Generate text completion from prompt using OpenAI Responses API.

        Args:
            prompt: Input prompt

        Returns:
            Generated text
        """
        client = self._get_client()

        try:
            if self.max_tokens is not None:
                response = client.responses.create(
                    model=self.model,
                    input=prompt,
                    max_output_tokens=self.max_tokens,
                )
            else:
                response = client.responses.create(
                    model=self.model,
                    input=prompt,
                )

            return response.output_text or ""
        except Exception:
            logger.exception("OpenAI API error")
            raise

    def generate_chat(self, messages: list[dict[str, Any]]) -> str:
        """Generate chat response from messages using OpenAI Responses API.

        Args:
            messages: List of message dicts with 'role' and 'content' keys

        Returns:
            Generated text
        """
        client = self._get_client()

        try:
            if self.max_tokens is not None:
                response = client.responses.create(
                    model=self.model,
                    input=messages,  # type: ignore[arg-type]
                    max_output_tokens=self.max_tokens,
                )
            else:
                response = client.responses.create(
                    model=self.model,
                    input=messages,  # type: ignore[arg-type]
                )

            return response.output_text or ""
        except Exception:
            logger.exception("OpenAI API error")
            raise


class OllamaClient:
    """Ollama client using ollama.chat."""

    model: str
    max_tokens: int | None

    def __init__(self, model: str, max_tokens: int | None = None) -> None:
        """Initialize Ollama client.

        Args:
            model: Model name (e.g., "llama3.1:8b")
            max_tokens: Maximum tokens to generate (None for backend default)
        """
        self.model = model
        self.max_tokens = max_tokens

    @classmethod
    def from_env(cls) -> "OllamaClient":
        """Create Ollama client from environment variables.

        Expects environment variables:
            - LLM_MODEL: Model name (e.g., "llama3.1:8b")
            - LLM_MAX_TOKENS: Max tokens (optional, empty or 0 = unset)

        Returns:
            OllamaClient instance

        Raises:
            ValueError: If required environment variables are missing
        """
        model = os.getenv("LLM_MODEL")
        if not model:
            raise ValueError("LLM_MODEL environment variable is required")

        max_tokens = _parse_max_tokens()

        return cls(model=model, max_tokens=max_tokens)

    def generate_completion(self, prompt: str) -> str:
        """Generate text completion from prompt using ollama.generate.

        Args:
            prompt: Input prompt

        Returns:
            Generated text
        """
        try:
            if self.max_tokens is not None:
                response = ollama.generate(
                    model=self.model,
                    prompt=prompt,
                    options={"num_predict": self.max_tokens},
                )
            else:
                response = ollama.generate(
                    model=self.model,
                    prompt=prompt,
                )

            return response["response"] or ""
        except Exception:
            logger.exception("Ollama API error")
            raise

    def generate_chat(self, messages: list[dict[str, Any]]) -> str:
        """Generate chat response from messages using ollama.chat.

        Args:
            messages: List of message dicts with 'role' and 'content' keys

        Returns:
            Generated text
        """
        try:
            if self.max_tokens is not None:
                response = ollama.chat(
                    model=self.model,
                    messages=messages,
                    options={"num_predict": self.max_tokens},
                )
            else:
                response = ollama.chat(
                    model=self.model,
                    messages=messages,
                )

            return response["message"]["content"] or ""
        except Exception:
            logger.exception("Ollama API error")
            raise


def get_llm_client() -> OpenAIClient | OllamaClient:
    """Factory function to get LLM client based on LLM_PROVIDER.

    Expects environment variables:
        - LLM_PROVIDER: "openai" or "ollama"
        - Additional variables required by the selected provider

    Returns:
        LLM client instance (OpenAIClient or OllamaClient)

    Raises:
        ValueError: If LLM_PROVIDER is missing or invalid
    """
    provider = os.getenv("LLM_PROVIDER")
    if not provider:
        raise ValueError("LLM_PROVIDER environment variable is required")

    provider = provider.lower()

    if provider == "openai":
        return OpenAIClient.from_env()
    elif provider == "ollama":
        return OllamaClient.from_env()
    else:
        raise ValueError(
            f"Invalid LLM_PROVIDER: {provider}. Must be 'openai' or 'ollama'"
        )
