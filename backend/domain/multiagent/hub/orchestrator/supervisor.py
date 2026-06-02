import json

import numpy as np
from loguru import logger

from backend.domain.multiagent.models.states.simulation_state import SimulationState
from backend.domain.multiagent.spokes.infra.openai_client import LLMClientError, openai_client

_SUPERVISOR_SYSTEM = """
당신은 AI 시뮬레이션 품질 감독관입니다.
제공된 검증 결과 JSON을 보고 다음 처리 단계를 결정하세요.
반드시 JSON으로만 응답하세요.

{
  "next_node": "aggregate_stats | retry_reactions | end",
  "reason": "판단 이유 한 문장"
}

판단 기준 (순서대로 적용):
1. valid_count < 10 → "end" (유효 응답 부족, 신뢰할 수 없는 결과)
2. error_rate > 0.5 → "end" (오류율 과다, API 문제 가능성)
3. collapse_detected = true AND retry_count < 2 → "retry_reactions" (페르소나 동질화, 재시도 권장)
4. 그 외 → "aggregate_stats" (정상 진행)
"""


async def supervisor_route(state: SimulationState) -> str:
    """Supervisor LLM이 validate_responses 이후 라우팅을 결정한다."""
    responses = state.get("raw_responses", [])
    valid = [r for r in responses if not r.get("is_outlier")]

    collapse_detected = False
    if len(valid) >= 3:
        scores = [r["click_intention"] for r in valid]
        collapse_detected = bool(np.std(scores) < 15)

    error_rate = len(state.get("errors", [])) / max(len(responses), 1)

    summary = {
        "valid_count": len(valid),
        "total_count": len(responses),
        "error_count": len(state.get("errors", [])),
        "error_rate": round(error_rate, 3),
        "collapse_detected": collapse_detected,
        "retry_count": state.get("retry_count", 0),
    }

    logger.info("Supervisor 판단 중", **summary)

    try:
        result = await openai_client.chat_completion(
            messages=[
                {"role": "system", "content": _SUPERVISOR_SYSTEM},
                {"role": "user", "content": json.dumps(summary, ensure_ascii=False)},
            ],
            model="gpt-4o-mini",
            temperature=0.0,  # 라우팅 결정은 deterministic
        )
        next_node = result.get("next_node", "aggregate_stats")
        reason = result.get("reason", "")
        logger.info("Supervisor 결정", next_node=next_node, reason=reason)
    except LLMClientError as e:
        # LLM 실패 시 규칙 기반 폴백
        logger.warning("Supervisor LLM 실패 — 규칙 기반 라우팅 사용", error=str(e))
        if len(valid) < 10:
            next_node = "end"
        elif collapse_detected and state.get("retry_count", 0) < 2:
            next_node = "retry_reactions"
        else:
            next_node = "aggregate_stats"

    return next_node
