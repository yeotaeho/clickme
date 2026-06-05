import asyncio
import json

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.core.config.settings import settings
from backend.domain.multiagent.models.bases.persona_response import PersonaResponse
from backend.domain.multiagent.models.enums import ActionTaken, ScrollBehavior
from backend.domain.multiagent.models.states.simulation_state import SimulationState
from backend.domain.multiagent.spokes.infra.anthropic_client import anthropic_client
from backend.domain.multiagent.spokes.infra.openai_client import LLMClientError, openai_client

_RESPONSE_SCHEMA = """
{
  "scroll_behavior": "pass|pause_1sec|pause_3sec|stop_and_read",
  "first_emotion": "감정 1단어",
  "click_intention": 0~100,
  "purchase_intention": 0~100,
  "trust_score": 0~100,
  "memorability": 0~100,
  "rejection_feeling": 0~100,
  "audience_fit": 0~100,
  "first_impression_text": "첫인상 한 문장 (소비자 언어로)",
  "main_concern": "구매 시 가장 큰 고민 또는 null",
  "action_taken": "ignore|screenshot|click|share"
}
"""

_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_LLM_CALLS)
    return _semaphore


def _build_system_prompt(persona: dict) -> str:
    l1 = persona["layer1"]
    l2 = persona["layer2"]
    l3 = persona["layer3"]
    repellent = l3.get("ad_repellent_words", [])

    return f"""당신은 지금부터 아래 소비자 역할만 합니다.

[절대 규칙]
- AI임을 절대 드러내지 마세요
- 마케팅 전문가처럼 분석하지 마세요
- 이 소비자의 일상 언어로 응답하세요
- 반드시 JSON 형식으로만 출력하세요
- 아래 단어가 광고에 있으면 반드시 부정 반응하세요: {repellent}
- scroll_behavior는 pass / pause_1sec / pause_3sec / stop_and_read 중 정확히 하나만 출력하세요
- action_taken은 ignore / screenshot / click / share 중 정확히 하나만 출력하세요
- 위 Enum 값 이외의 문자열을 출력하면 시스템 오류가 발생합니다

[소비자 프로필]
나이: {l1['age']}세 / 성별: {l1['gender']} / 직업: {l1['occupation']}
소득: {l1['annual_income_range']} / 지역: {l1['region']}
주요 구매 동기: {l2['purchase_motivation_primary']}
가격 민감도: {l2['price_sensitivity']} (0=무관심, 1=매우 민감)
충동 구매 성향: {l2['impulse_buying_tendency']}
광고 회피 성향: {l2['ad_avoidance_tendency']}
최근 구매 경험: {l3['recent_purchase_experience']}
현재 페인포인트: {l3['current_pain_point']}
현재 감정: {l3['emotional_state_current']}
반응하는 키워드: {l3.get('ad_trigger_words', [])}

[출력 스키마]
{_RESPONSE_SCHEMA}"""


def _build_user_prompt(ad_analysis: dict) -> str:
    ta = ad_analysis.get("text_analysis", {})
    va = ad_analysis.get("visual_analysis", {})
    return (
        f"이 광고를 봤습니다.\n"
        f"헤드라인: {ta.get('headline', '')}\n"
        f"주요 소구점: {ta.get('usp_extracted', [])}\n"
        f"광고 분위기: {va.get('emotional_tone', '')}\n\n"
        f"지금 이 광고에 대한 당신의 반응을 JSON으로 응답하세요."
    )


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=5), reraise=True)
async def _call_openai(persona: dict, ad_analysis: dict) -> dict:
    system = _build_system_prompt(persona)
    user = _build_user_prompt(ad_analysis)
    return await openai_client.chat_completion(
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        model=settings.OPENAI_REACTION_MODEL,
        temperature=persona.get("temperature_assigned", 0.7),
        seed=persona.get("seed"),
    )


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=5), reraise=True)
async def _call_claude_haiku(persona: dict, ad_analysis: dict) -> dict:
    system = _build_system_prompt(persona)
    user = _build_user_prompt(ad_analysis)
    return await anthropic_client.chat_completion(
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        model=settings.ANTHROPIC_FALLBACK_MODEL,
        temperature=min(persona.get("temperature_assigned", 0.7), 1.0),
    )


async def _simulate_single(persona: dict, ad_analysis: dict) -> dict | None:
    persona_id = persona.get("persona_id", "unknown")
    async with _get_semaphore():
        try:
            raw = await _call_openai(persona, ad_analysis)
        except LLMClientError:
            logger.warning("OpenAI 폴백 → Claude Haiku", persona_id=persona_id)
            try:
                raw = await _call_claude_haiku(persona, ad_analysis)
            except LLMClientError as e:
                logger.error("에이전트 완전 실패 — 제외", persona_id=persona_id, error=str(e))
                return None

        try:
            response = PersonaResponse(
                persona_id=persona_id,
                scroll_behavior=ScrollBehavior(raw.get("scroll_behavior", "pass")),
                first_emotion=raw.get("first_emotion", "무관심"),
                click_intention=int(raw.get("click_intention", 0)),
                purchase_intention=int(raw.get("purchase_intention", 0)),
                trust_score=int(raw.get("trust_score", 50)),
                memorability=int(raw.get("memorability", 50)),
                rejection_feeling=int(raw.get("rejection_feeling", 0)),
                audience_fit=int(raw.get("audience_fit", 50)),
                first_impression_text=raw.get("first_impression_text", ""),
                main_concern=raw.get("main_concern"),
                action_taken=ActionTaken(raw.get("action_taken", "ignore")),
            )
            return response.model_dump()
        except Exception as e:
            logger.warning("응답 파싱 실패 — 제외", persona_id=persona_id, error=str(e))
            return None


class ReactionSimulationAgent:
    async def run(self, state: SimulationState) -> SimulationState:
        personas = state.get("persona_pool", [])
        ad_analysis = state.get("ad_analysis", {})

        if not personas:
            state["errors"].append({"type": "no_personas", "detail": "페르소나 풀이 비어 있음", "persona_id": None})
            return state

        tasks = [_simulate_single(p, ad_analysis) for p in personas]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        responses = []
        for r in results:
            if isinstance(r, Exception):
                state["errors"].append({"type": "reaction_exception", "detail": str(r), "persona_id": None})
            elif r is not None:
                responses.append(r)

        state["raw_responses"] = responses
        state["model_config"] = {
            "primary_model": settings.OPENAI_REACTION_MODEL,
            "fallback_model": settings.ANTHROPIC_FALLBACK_MODEL,
        }
        state["progress"] = 65
        logger.info("반응 시뮬레이션 완료", valid=len(responses), total=len(personas))
        return state
