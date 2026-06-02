import json

import anthropic
from loguru import logger

from backend.core.config.settings import settings
from backend.domain.multiagent.spokes.infra.openai_client import LLMClientError


class AnthropicMCPClient:
    """Anthropic API를 MCP 스타일 표준 인터페이스로 래핑한 클라이언트.

    OpenAIMCPClient와 동일한 chat_completion 시그니처를 유지해
    에이전트 레벨에서 교체 가능하도록 설계.
    """

    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def chat_completion(
        self,
        messages: list[dict],
        model: str = "claude-haiku-4-5-20251001",
        response_format: dict | None = None,
        temperature: float = 0.7,
        seed: int | None = None,
    ) -> dict:
        """표준 채팅 완성 호출 (JSON 응답 강제)."""
        # Anthropic은 system 메시지를 별도 파라미터로 받음
        system_content = ""
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            else:
                user_messages.append(msg)

        # JSON 강제 지시를 system에 추가
        json_instruction = "\n\n반드시 유효한 JSON 형식으로만 응답하세요."
        full_system = system_content + json_instruction

        try:
            response = await self._client.messages.create(
                model=model,
                max_tokens=4096,
                temperature=temperature,
                system=full_system,
                messages=user_messages,
            )
            content = response.content[0].text if response.content else "{}"
            # JSON 블록 추출 (마크다운 코드블록 대응)
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return json.loads(content.strip())
        except anthropic.RateLimitError as e:
            logger.warning("Anthropic RateLimit 초과", model=model, error=str(e))
            raise LLMClientError(f"RateLimit: {e}") from e
        except anthropic.APIStatusError as e:
            logger.error("Anthropic API 오류", model=model, status=e.status_code)
            raise LLMClientError(f"APIError: {e}") from e


anthropic_client = AnthropicMCPClient()
