import os
from typing import Optional
from .base import LLMProvider
from .groq_provider import GroqProvider
from .gemini_provider import GeminiProvider
from .openai_provider import OpenAIProvider


PROVIDERS = {
    "groq": GroqProvider,
    "gemini": GeminiProvider,
    "openai": OpenAIProvider,
}


def get_provider(name: Optional[str] = None) -> LLMProvider:
    """Get an LLM provider by name.

    Args:
        name: Provider name ('groq', 'gemini', 'openai').
              If None, uses LLM_PROVIDER env var, defaults to 'groq'.

    Returns:
        Configured LLMProvider instance.

    Raises:
        ValueError: If provider name is not recognized.
    """
    provider_name = (name or os.getenv("LLM_PROVIDER", "groq")).lower()

    if provider_name not in PROVIDERS:
        raise ValueError(
            f"Unknown provider: {provider_name}. "
            f"Available: {', '.join(PROVIDERS.keys())}"
        )

    return PROVIDERS[provider_name]()


def get_all_providers() -> dict[str, LLMProvider]:
    """Get all available providers (only those with API keys configured).

    Returns:
        Dict of provider name to provider instance.
    """
    available = {}

    # Check which providers have API keys configured
    if os.getenv("GROQ_API_KEY"):
        available["groq"] = GroqProvider()
    if os.getenv("GEMINI_API_KEY"):
        available["gemini"] = GeminiProvider()
    if os.getenv("OPENAI_API_KEY"):
        available["openai"] = OpenAIProvider()

    return available
