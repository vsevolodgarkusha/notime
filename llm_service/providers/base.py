from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMResponse:
    """Standardized response from LLM providers."""
    content: str
    model: str
    provider: str
    usage: Optional[dict] = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    This interface allows switching between different LLM providers
    (Groq, Gemini, OpenAI) without changing the business logic.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging and identification."""
        pass

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Default model to use for this provider."""
        pass

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        json_mode: bool = False,
    ) -> LLMResponse:
        """Generate a response from the LLM.

        Args:
            system_prompt: System instructions for the model.
            user_prompt: User's message.
            model: Override the default model.
            temperature: Sampling temperature (0.0 to 1.0).
            json_mode: If True, expect JSON output.

        Returns:
            LLMResponse with the generated content.

        Raises:
            Exception: If the API call fails.
        """
        pass

    @abstractmethod
    async def transcribe_audio(
        self,
        audio_data: bytes,
        filename: str = "audio.ogg",
    ) -> str:
        """Transcribe audio to text.

        Args:
            audio_data: Raw audio bytes.
            filename: Name hint for the audio format.

        Returns:
            Transcribed text.

        Raises:
            NotImplementedError: If provider doesn't support transcription.
            Exception: If the API call fails.
        """
        pass
