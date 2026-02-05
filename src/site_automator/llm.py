"""LLM client implementations for OpenAI and Ollama."""

import asyncio
import logging
import os
from typing import Any

import ollama
from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI

from site_automator.utils import clean_llm_text, parse_numbered_list

_DEFAULT_MAX_CONCURRENCY = 10

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


def _parse_temperature() -> float | None:
    """Parse LLM_TEMPERATURE environment variable.

    Returns:
        Temperature as float, or None if unset/empty

    Raises:
        ValueError: If LLM_TEMPERATURE is not a valid float
    """
    val = os.getenv("LLM_TEMPERATURE", "").strip()
    if not val:
        return None
    return float(val)


def _parse_max_concurrency() -> int:
    """Parse LLM_MAX_CONCURRENCY environment variable.

    Returns:
        Max concurrency as int (defaults to 10)

    Raises:
        ValueError: If LLM_MAX_CONCURRENCY is not a valid positive integer
    """
    val = os.getenv("LLM_MAX_CONCURRENCY", "").strip()
    if not val:
        return _DEFAULT_MAX_CONCURRENCY

    n = int(val)
    if n < 1:
        raise ValueError(f"LLM_MAX_CONCURRENCY must be >= 1, got {n}")
    return n


class OpenAIClient:
    """OpenAI API client using the Chat Completions API."""

    api_key: str
    model: str
    max_tokens: int | None
    temperature: float | None
    base_url: str | None
    _client: OpenAI | None

    def __init__(
        self,
        api_key: str,
        model: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
        base_url: str | None = None,
    ) -> None:
        """Initialize OpenAI client.

        Args:
            api_key: OpenAI API key
            model: Model name (e.g., "gpt-4.1-nano")
            max_tokens: Maximum tokens to generate (None for backend default)
            temperature: Sampling temperature (None for backend default)
            base_url: Base URL for API (None for OpenAI default)
        """
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.base_url = base_url
        self._client: OpenAI | None = None

    @classmethod
    def from_env(cls, provider: str) -> "OpenAIClient":
        """Create OpenAI client from environment variables using provider prefix.

        Reads {PROVIDER}_API_KEY, {PROVIDER}_MODEL, and optionally
        {PROVIDER}_BASE_URL based on the provider name.

        Args:
            provider: Provider name (e.g., "openai", "groq", "deepinfra")

        Returns:
            OpenAIClient instance

        Raises:
            ValueError: If required environment variables are missing
        """
        prefix = provider.upper()

        api_key = os.getenv(f"{prefix}_API_KEY")
        if not api_key:
            raise ValueError(f"{prefix}_API_KEY environment variable is required")

        model = os.getenv(f"{prefix}_MODEL")
        if not model:
            raise ValueError(f"{prefix}_MODEL environment variable is required")

        max_tokens = _parse_max_tokens()
        temperature = _parse_temperature()
        base_url = os.getenv(f"{prefix}_BASE_URL") or None

        return cls(
            api_key=api_key,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            base_url=base_url,
        )

    def _get_client(self) -> OpenAI:
        """Get or create OpenAI client instance.

        Returns:
            OpenAI client instance
        """
        if self._client is None:
            if self.base_url is not None:
                self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            else:
                self._client = OpenAI(api_key=self.api_key)

        return self._client

    def _build_kwargs(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        """Build kwargs dict for chat.completions.create."""
        kwargs: dict[str, Any] = {"model": self.model, "messages": messages}
        if self.max_tokens is not None:
            kwargs["max_tokens"] = self.max_tokens
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        return kwargs

    def generate_completion(self, prompt: str) -> str:
        """Generate text completion from prompt using OpenAI Chat Completions API.

        Args:
            prompt: Input prompt

        Returns:
            Generated text
        """
        client = self._get_client()
        kwargs = self._build_kwargs([{"role": "user", "content": prompt}])

        try:
            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message.content or ""
        except Exception:
            logger.exception("OpenAI API error")
            raise

    def generate_chat(self, messages: list[dict[str, Any]]) -> str:
        """Generate chat response from messages using OpenAI Chat Completions API.

        Args:
            messages: List of message dicts with 'role' and 'content' keys

        Returns:
            Generated text
        """
        client = self._get_client()
        kwargs = self._build_kwargs(messages)

        try:
            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message.content or ""
        except Exception:
            logger.exception("OpenAI API error")
            raise

    async def _generate_completion_async(self, client: AsyncOpenAI, prompt: str) -> str:
        """Async version of generate_completion."""
        kwargs = self._build_kwargs([{"role": "user", "content": prompt}])
        try:
            response = await client.chat.completions.create(**kwargs)
            return response.choices[0].message.content or ""
        except Exception:
            logger.exception("OpenAI API error")
            raise

    async def _generate_chat_async(
        self, client: AsyncOpenAI, messages: list[dict[str, Any]]
    ) -> str:
        """Async version of generate_chat."""
        kwargs = self._build_kwargs(messages)
        try:
            response = await client.chat.completions.create(**kwargs)
            return response.choices[0].message.content or ""
        except Exception:
            logger.exception("OpenAI API error")
            raise

    def generate_completion_bulk(self, prompts: list[str]) -> list[str | None]:
        """Generate completions for multiple prompts concurrently.

        Args:
            prompts: List of input prompts

        Returns:
            List of generated texts (or None for failures), in the same order
            as prompts. Failures are logged individually.
        """
        semaphore = asyncio.Semaphore(_parse_max_concurrency())

        async def _limited(client: AsyncOpenAI, prompt: str) -> str:
            async with semaphore:
                return await self._generate_completion_async(client, prompt)

        async def _run() -> list[str | None]:
            async with AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            ) as client:
                raw = await asyncio.gather(
                    *[_limited(client, p) for p in prompts], return_exceptions=True
                )
                return [None if isinstance(r, BaseException) else r for r in raw]

        return asyncio.run(_run())

    def generate_chat_bulk(
        self, message_lists: list[list[dict[str, Any]]]
    ) -> list[str | None]:
        """Generate chat responses for multiple message lists concurrently.

        Args:
            message_lists: List of message lists

        Returns:
            List of generated texts (or None for failures), in the same order
            as message_lists. Failures are logged individually.
        """
        semaphore = asyncio.Semaphore(_parse_max_concurrency())

        async def _limited(client: AsyncOpenAI, messages: list[dict[str, Any]]) -> str:
            async with semaphore:
                return await self._generate_chat_async(client, messages)

        async def _run() -> list[str | None]:
            async with AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            ) as client:
                raw = await asyncio.gather(
                    *[_limited(client, m) for m in message_lists],
                    return_exceptions=True,
                )
                return [None if isinstance(r, BaseException) else r for r in raw]

        return asyncio.run(_run())


class OllamaClient:
    """Ollama client using ollama.chat."""

    model: str
    max_tokens: int | None
    temperature: float | None

    def __init__(
        self,
        model: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> None:
        """Initialize Ollama client.

        Args:
            model: Model name (e.g., "llama3.1:8b")
            max_tokens: Maximum tokens to generate (None for backend default)
            temperature: Sampling temperature (None for backend default)
        """
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    @classmethod
    def from_env(cls) -> "OllamaClient":
        """Create Ollama client from environment variables.

        Reads OLLAMA_MODEL for the model name.

        Returns:
            OllamaClient instance

        Raises:
            ValueError: If required environment variables are missing
        """
        model = os.getenv("OLLAMA_MODEL")
        if not model:
            raise ValueError("OLLAMA_MODEL environment variable is required")

        max_tokens = _parse_max_tokens()
        temperature = _parse_temperature()

        return cls(model=model, max_tokens=max_tokens, temperature=temperature)

    def _build_kwargs(self, **extra: Any) -> dict[str, Any]:
        """Build kwargs dict for Ollama API calls."""
        kwargs: dict[str, Any] = {"model": self.model, **extra}
        options: dict[str, Any] = {}
        if self.max_tokens is not None:
            options["num_predict"] = self.max_tokens
        if self.temperature is not None:
            options["temperature"] = self.temperature
        if options:
            kwargs["options"] = options
        return kwargs

    def generate_completion(self, prompt: str) -> str:
        """Generate text completion from prompt using ollama.generate.

        Args:
            prompt: Input prompt

        Returns:
            Generated text
        """
        try:
            kwargs = self._build_kwargs(prompt=prompt)
            response = ollama.generate(**kwargs)
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
            kwargs = self._build_kwargs(messages=messages)
            response = ollama.chat(**kwargs)
            return response["message"]["content"] or ""
        except Exception:
            logger.exception("Ollama API error")
            raise

    def generate_completion_bulk(self, prompts: list[str]) -> list[str | None]:
        """Generate completions for multiple prompts sequentially.

        Ollama runs locally on a single GPU and serializes requests,
        so concurrent calls add overhead without benefit.

        Args:
            prompts: List of input prompts

        Returns:
            List of generated texts (or None for failures), in the same order
            as prompts. Failures are logged individually.
        """
        results: list[str | None] = []
        for p in prompts:
            try:
                results.append(self.generate_completion(p))
            except Exception:
                results.append(None)
        return results

    def generate_chat_bulk(
        self, message_lists: list[list[dict[str, Any]]]
    ) -> list[str | None]:
        """Generate chat responses for multiple message lists sequentially.

        Ollama runs locally on a single GPU and serializes requests,
        so concurrent calls add overhead without benefit.

        Args:
            message_lists: List of message lists

        Returns:
            List of generated texts (or None for failures), in the same order
            as message_lists. Failures are logged individually.
        """
        results: list[str | None] = []
        for m in message_lists:
            try:
                results.append(self.generate_chat(m))
            except Exception:
                results.append(None)
        return results


def get_llm_client() -> OpenAIClient | OllamaClient:
    """Factory function to get LLM client based on LLM_PROVIDER.

    Expects environment variables:
        - LLM_PROVIDER: provider name (e.g. "openai", "groq", "deepinfra", "ollama")
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

    if provider == "ollama":
        return OllamaClient.from_env()
    else:
        return OpenAIClient.from_env(provider)


def generate_completion_clean(prompt: str) -> str:
    """Generate text completion from prompt and clean the output."""
    client = get_llm_client()
    raw = client.generate_completion(prompt)
    return clean_llm_text(raw)


def generate_chat_clean(messages: list[dict[str, Any]]) -> str:
    """Generate chat response from messages and clean the output."""
    client = get_llm_client()
    raw = client.generate_chat(messages)
    return clean_llm_text(raw)


def generate_completion_bulk_clean(prompts: list[str]) -> list[str | None]:
    """Generate completions for multiple prompts and clean each output.

    Returns None for any prompt that failed.
    """
    client = get_llm_client()
    results = client.generate_completion_bulk(prompts)
    return [clean_llm_text(r) if r is not None else None for r in results]


def generate_chat_bulk_clean(
    message_lists: list[list[dict[str, Any]]],
) -> list[str | None]:
    """Generate chat responses for multiple message lists and clean each output.

    Returns None for any message list that failed.
    """
    client = get_llm_client()
    results = client.generate_chat_bulk(message_lists)
    return [clean_llm_text(r) if r is not None else None for r in results]


def generate_list_items_bulk(prompts: list[str]) -> list[str]:
    """Generate and parse numbered lists from multiple prompts in bulk.

    Deduplicates items while preserving order.

    Args:
        prompts: List of prompts that should return numbered lists

    Returns:
        Flat list of unique parsed items from all prompts
    """
    results = generate_completion_bulk_clean(prompts)

    seen = set()
    items = []
    for result in results:
        if result is not None:
            parsed = parse_numbered_list(result)
            for item in parsed:
                if item not in seen:
                    seen.add(item)
                    items.append(item)

    return items
