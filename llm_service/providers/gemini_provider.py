import os
from typing import Optional
from .base import LLMProvider, LLMResponse


class GeminiProvider(LLMProvider):
    """Google Gemini LLM provider implementation."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.getenv("GEMINI_API_KEY")
        self._client = None
        self._model_instance = None

    def _ensure_client(self):
        if self._client is None:
            import google.generativeai as genai
            genai.configure(api_key=self._api_key)
            self._client = genai

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def default_model(self) -> str:
        return "gemini-2.0-flash-exp"

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        json_mode: bool = False,
    ) -> LLMResponse:
        self._ensure_client()
        model_name = model or self.default_model

        generation_config = {
            "temperature": temperature,
        }

        if json_mode:
            generation_config["response_mime_type"] = "application/json"

        model_instance = self._client.GenerativeModel(
            model_name=model_name,
            generation_config=generation_config,
            system_instruction=system_prompt,
        )

        response = model_instance.generate_content(user_prompt)

        return LLMResponse(
            content=response.text or "",
            model=model_name,
            provider=self.name,
            usage={
                "prompt_tokens": response.usage_metadata.prompt_token_count if response.usage_metadata else 0,
                "completion_tokens": response.usage_metadata.candidates_token_count if response.usage_metadata else 0,
            }
        )

    async def transcribe_audio(
        self,
        audio_data: bytes,
        filename: str = "audio.ogg",
    ) -> str:
        raise NotImplementedError("Gemini does not support direct audio transcription. Use Groq or OpenAI instead.")
