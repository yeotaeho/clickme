import json

import numpy as np
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.core.config.settings import settings
from backend.domain.multiagent.models.states.simulation_state import SimulationState
from backend.domain.multiagent.spokes.infra.anthropic_client import anthropic_client
from backend.domain.multiagent.spokes.infra.openai_client import LLMClientError


def _compute_metrics(valid_responses: list[dict], bias: float) -> dict:
    """성과 지표를 공식 기반으로 산출 (LLM 불필요)."""
    clicks = [r["click_intention"] for r in valid_responses]
    purchases = [r["purchase_intention"] for r in valid_responses]
    trusts = [r["trust_score"] for r in valid_responses]
    fits = [r["audience_fit"] for r in valid_responses]
    first_impressions = [r.get("memorability", 50) for r in valid_responses]
    rejections = [r["rejection_feeling"] for r in valid_responses]

    ctr_raw = (
        float(np.mean(clicks)) * 0.5
        + float(np.mean(first_impressions)) * 0.3
        + float(np.mean(fits)) * 0.2
    )
    ctr_corrected = max(0.0, ctr_raw - bias)
    purchase_intent = max(0.0, float(np.mean(purchases)) * 0.6 + float(np.mean(trusts)) * 0.4 - bias)
    audience_fit = float(np.mean(fits))
    rejection_rate = len([r for r in valid_responses if r["rejection_feeling"] > 60]) / len(valid_responses)
    confidence = max(0.0, 1.0 - float(np.std(clicks)) / 100)

    return {
        "ctr_raw": round(ctr_raw, 1),
        "ctr_corrected": round(ctr_corrected, 1),
        "purchase_intent": round(purchase_intent, 1),
        "audience_fit": round(audience_fit, 1),
        "rejection_rate": round(rejection_rate, 3),
        "confidence_score": round(confidence, 3),
    }


_PERCENTILE_SYSTEM = """
당신은 마케팅 성과 지표 해석 전문가입니다.
제공된 수치 지표를 보고 한국 광고 시장 기준으로 percentile을 해석하세요.
반드시 JSON으로만 응답하세요.

{
  "ctr_percentile": "상위 X% (예: 상위 25%)",
  "purchase_percentile": "상위 X%",
  "overall_score": 0~100,
  "verdict": "pass|fail|borderline",
  "verdict_reason": "판정 이유 한 문장"
}

기준:
- overall_score 70이상 → pass
- 50~69 → borderline
- 50미만 → fail
"""


class PredictionAgent:
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10), reraise=True)
    async def _interpret_percentile(self, metrics: dict) -> dict:
        return await anthropic_client.chat_completion(
            messages=[
                {"role": "system", "content": _PERCENTILE_SYSTEM},
                {"role": "user", "content": json.dumps(metrics, ensure_ascii=False)},
            ],
            model="claude-haiku-4-5-20251001",
            temperature=0.3,
        )

    async def run(self, state: SimulationState) -> SimulationState:
        responses = state.get("raw_responses", [])
        valid = [r for r in responses if not r.get("is_outlier")]

        if not valid:
            state["errors"].append({"type": "no_valid_responses", "detail": "유효 응답 없음", "persona_id": None})
            return state

        bias = settings.BIAS_CORRECTION_DEFAULT
        metrics = _compute_metrics(valid, bias)

        try:
            interpretation = await self._interpret_percentile(metrics)
        except LLMClientError as e:
            logger.warning("Percentile 해석 실패 — 기본값 사용", error=str(e))
            interpretation = {
                "ctr_percentile": "측정 불가",
                "purchase_percentile": "측정 불가",
                "overall_score": int(metrics["ctr_corrected"]),
                "verdict": "borderline",
                "verdict_reason": "해석 서비스 일시 불가",
            }

        state["performance_predictions"] = {
            **metrics,
            **interpretation,
            "outliers_excluded": sum(1 for r in responses if r.get("is_outlier")),
            "persona_count_valid": len(valid),
        }
        state["progress"] = 80
        logger.info("성과 예측 완료", overall=interpretation.get("overall_score"))
        return state
