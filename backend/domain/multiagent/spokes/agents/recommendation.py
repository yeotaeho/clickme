import json

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.domain.multiagent.models.states.simulation_state import SimulationState
from backend.domain.multiagent.spokes.infra.anthropic_client import anthropic_client
from backend.domain.multiagent.spokes.infra.openai_client import LLMClientError

_SYSTEM = """
당신은 퍼포먼스 마케팅 전문 컨설턴트입니다.
시뮬레이션 결과를 바탕으로 광고 개선 액션 아이템을 생성하세요.

[출력 규칙]
- 반드시 JSON으로만 응답하세요
- HIGH 우선순위 최대 3개, MID 최대 3개, LOW 최대 2개
- 각 item은 구체적이고 즉시 실행 가능한 수준으로

{
  "action_items": [
    {
      "priority": "HIGH|MID|LOW",
      "issue": "문제점 한 문장",
      "suggestion": "개선 방법 한 문장 (구체적)"
    }
  ],
  "top_action": "가장 중요한 액션 1가지 요약"
}
"""


class RecommendationAgent:
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10), reraise=True)
    async def _call_llm(self, user_content: str) -> dict:
        return await anthropic_client.chat_completion(
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_content},
            ],
            model="claude-sonnet-4-6",
            temperature=0.5,
        )

    async def run(self, state: SimulationState) -> SimulationState:
        predictions = state.get("performance_predictions", {})
        aggregated = state.get("aggregated_stats", {})
        responses = [r for r in state.get("raw_responses", []) if not r.get("is_outlier")]

        # 부정 피드백 상위 5개 추출
        negative_feedbacks = sorted(
            [r.get("first_impression_text", "") for r in responses if r.get("rejection_feeling", 0) > 50],
            key=len,
            reverse=True,
        )[:5]

        user_content = json.dumps(
            {
                "performance_metrics": predictions,
                "segment_breakdown": aggregated.get("segment_breakdown", {}),
                "negative_feedbacks": negative_feedbacks,
                "top_concerns": [r.get("main_concern") for r in responses if r.get("main_concern")][:5],
            },
            ensure_ascii=False,
        )

        try:
            result = await self._call_llm(user_content)
            state["recommendations"] = result.get("action_items", [])
            if "top_action" in result:
                state.setdefault("performance_predictions", {})["top_action"] = result["top_action"]
            state["progress"] = 90
            logger.info("개선안 생성 완료", count=len(state["recommendations"]))
        except LLMClientError as e:
            logger.error("개선안 생성 실패", error=str(e))
            state["errors"].append({"type": "recommendation_failed", "detail": str(e), "persona_id": None})
            state["recommendations"] = []

        return state
