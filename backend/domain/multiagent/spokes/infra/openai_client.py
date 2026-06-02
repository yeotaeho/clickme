import json

from loguru import logger
from openai import AsyncOpenAI, APIError, RateLimitError

from backend.core.config.settings import settings


class LLMClientError(Exception):
    pass


class OpenAIMCPClient:
    """OpenAI API를 MCP 스타일 표준 인터페이스로 래핑한 클라이언트."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def chat_completion(
        self,
        messages: list[dict],
        model: str = "gpt-4o-mini",
        response_format: dict | None = None,
        temperature: float = 0.7,
        seed: int | None = None,
    ) -> dict:
        """표준 채팅 완성 호출."""
        try:
            kwargs: dict = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "response_format": response_format or {"type": "json_object"},
            }
            if seed is not None:
                kwargs["seed"] = seed

            response = await self._client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content or "{}"
            return json.loads(content)
        except RateLimitError as e:
            logger.warning("OpenAI RateLimit 초과", model=model, error=str(e))
            raise LLMClientError(f"RateLimit: {e}") from e
        except APIError as e:
            logger.error("OpenAI API 오류", model=model, error=str(e))
            raise LLMClientError(f"APIError: {e}") from e

    async def vision_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        base64_image: str,
        model: str = "gpt-4o",
    ) -> dict:
        """Vision API 호출 (base64 이미지 직접 전달)."""
        # data URL 형식 보장
        if not base64_image.startswith("data:"):
            base64_image = f"data:image/jpeg;base64,{base64_image}"

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": base64_image, "detail": "high"},
                    },
                ],
            },
        ]
        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
            return json.loads(content)
        except RateLimitError as e:
            logger.warning("OpenAI Vision RateLimit", error=str(e))
            raise LLMClientError(f"RateLimit: {e}") from e
        except APIError as e:
            logger.error("OpenAI Vision API 오류", error=str(e))
            raise LLMClientError(f"APIError: {e}") from e


openai_client = OpenAIMCPClient()
