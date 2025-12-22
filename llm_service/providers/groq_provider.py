import os
from typing import Optional
from groq import Groq
from .base import LLMProvider, LLMResponse


class GroqProvider(LLMProvider):
    """Groq LLM provider implementation."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.getenv("GROQ_API_KEY")
        self._client = Groq(api_key=self._api_key)

    @property
    def name(self) -> str:
        return "groq"

    @property
    def default_model(self) -> str:
        return "llama-3.3-70b-versatile"

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        json_mode: bool = False,
    ) -> LLMResponse:
        model = model or self.default_model

        kwargs = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
        }

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        completion = self._client.chat.completions.create(**kwargs)

        return LLMResponse(
            content=completion.choices[0].message.content or "",
            model=model,
            provider=self.name,
            usage={
                "prompt_tokens": completion.usage.prompt_tokens if completion.usage else 0,
                "completion_tokens": completion.usage.completion_tokens if completion.usage else 0,
            }
        )

    async def transcribe_audio(
        self,
        audio_data: bytes,
        filename: str = "audio.ogg",
    ) -> str:
        transcription = self._client.audio.transcriptions.create(
            file=(filename, audio_data),
            model="whisper-large-v3",
            response_format="text"
        )
        return str(transcription).strip()
