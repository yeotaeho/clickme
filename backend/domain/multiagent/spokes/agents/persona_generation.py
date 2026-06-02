import json
import uuid

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.domain.multiagent.models.bases.persona import Persona
from backend.domain.multiagent.models.states.simulation_state import SimulationState
from backend.domain.multiagent.spokes.infra.openai_client import LLMClientError, openai_client

_SYSTEM = """
당신은 마케팅 타깃 소비자 페르소나 생성 전문가입니다.
요청된 수량만큼 다양한 소비자 페르소나를 생성하세요.

[절대 규칙]
- 반드시 JSON 배열로만 응답하세요: {"personas": [...]}
- 각 페르소나는 아래 스키마를 정확히 따르세요
- 페르소나 간 다양성을 최대화하세요 (나이, 직업, 성향 골고루 분포)
- layer3.recent_purchase_experience는 구체적인 서사로 작성 (동질화 방지)

페르소나 스키마:
{
  "layer1": {
    "age": 정수,
    "gender": "male|female",
    "region": "지역명",
    "occupation": "직업",
    "annual_income_range": "소득구간",
    "education": "학력"
  },
  "layer2": {
    "purchase_motivation_primary": "주요 구매 동기",
    "price_sensitivity": 0.0~1.0,
    "impulse_buying_tendency": 0.0~1.0,
    "ad_avoidance_tendency": 0.0~1.0,
    "preferred_ad_format": ["선호 광고 형식"],
    "trusted_channels": ["신뢰 채널"],
    "decision_speed": "fast|medium|slow"
  },
  "layer3": {
    "recent_purchase_experience": "최근 구매 경험 (구체적 서사)",
    "current_pain_point": "현재 불편/결핍",
    "ad_trigger_words": ["반응하는 키워드"],
    "ad_repellent_words": ["거부감 키워드"],
    "emotional_state_current": "현재 감정 상태"
  }
}
"""


class PersonaGenerationAgent:
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10), reraise=True)
    async def _call_llm(self, user_prompt: str) -> dict:
        return await openai_client.chat_completion(
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            model="gpt-4o-mini",
            temperature=0.9,  # 다양성 극대화
        )

    async def run(self, state: SimulationState) -> SimulationState:
        ad_analysis = state.get("ad_analysis", {})
        target = ad_analysis.get("strategic_analysis", {}).get("target_demographic", "일반 소비자")
        persona_config = state["ad_input"].get("persona_config", {})
        count = persona_config.get("count", 20)

        user_prompt = (
            f"타깃 소비자: {target}\n"
            f"페르소나 수: {count}명\n"
            f"추가 조건: {json.dumps(persona_config, ensure_ascii=False)}\n\n"
            f"위 조건에 맞는 {count}명의 페르소나를 JSON으로 생성하세요."
        )

        try:
            raw = await self._call_llm(user_prompt)
            raw_personas = raw.get("personas", [])

            personas: list[dict] = []
            for idx, p_data in enumerate(raw_personas):
                try:
                    layer1_data = p_data["layer1"]
                    layer2_data = p_data["layer2"]

                    from backend.domain.multiagent.models.bases.persona import (
                        PersonaLayer1,
                        PersonaLayer2,
                    )

                    layer1 = PersonaLayer1(**layer1_data)
                    layer2 = PersonaLayer2(**layer2_data)
                    temperature = Persona.assign_temperature(layer1, layer2)

                    persona = Persona(
                        persona_id=f"P_{idx + 1:04d}",
                        layer1=layer1,
                        layer2=layer2,
                        layer3=p_data["layer3"],
                        temperature_assigned=temperature,
                        seed=hash(f"{uuid.uuid4()}") % 10000,
                    )
                    personas.append(persona.model_dump())
                except Exception as e:
                    logger.warning("페르소나 파싱 실패", idx=idx, error=str(e))

            state["persona_pool"] = personas
            state["progress"] = 30
            logger.info("페르소나 생성 완료", count=len(personas))
        except LLMClientError as e:
            logger.error("페르소나 생성 실패", error=str(e))
            state["errors"].append({"type": "persona_generation_failed", "detail": str(e), "persona_id": None})

        return state
