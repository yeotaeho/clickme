import numpy as np
from loguru import logger

from backend.domain.multiagent.models.states.simulation_state import SimulationState

_AI_DISCLOSURE_PATTERNS = [
    "ai로서", "인공지능", "언어 모델", "llm", "저는 ai",
    "as an ai", "i am an ai", "language model",
]

_MARKETING_JARGON = [
    "roi", "roas", "ctr", "cpc", "전환율", "퍼널", "리텐션",
    "온보딩", "a/b 테스트", "kpi", "usp", "캠페인 최적화",
    "타깃 세그먼트", "브랜드 포지셔닝", "소구점",
]


def detect_persona_drift(response: dict) -> bool:
    """AI 자기노출 또는 마케팅 전문 용어 과다 사용 감지."""
    text = " ".join([
        response.get("first_impression_text", ""),
        response.get("main_concern", "") or "",
        response.get("first_emotion", ""),
    ]).lower()
    if any(p in text for p in _AI_DISCLOSURE_PATTERNS):
        return True
    return sum(1 for w in _MARKETING_JARGON if w in text) >= 3


class ValidationAgent:
    """IQR 방식 이상치 탐지 + 페르소나 품질 검증."""

    def run(self, state: SimulationState) -> SimulationState:
        responses = state.get("raw_responses", [])
        if not responses:
            state["errors"].append({"type": "no_responses", "detail": "검증할 응답 없음", "persona_id": None})
            return state

        # IQR 이상치 탐지 (click_intention 기준)
        scores = np.array([r["click_intention"] for r in responses], dtype=float)
        q1, q3 = np.percentile(scores, [25, 75])
        iqr = q3 - q1
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr

        for r in responses:
            if not lower <= r["click_intention"] <= upper:
                r["is_outlier"] = True

        # T3: 페르소나 이탈 감지 — IQR 이후, valid 리스트 계산 이전
        drift_count = 0
        for r in responses:
            if not r.get("is_outlier") and detect_persona_drift(r):
                r["is_outlier"] = True
                drift_count += 1
                state["errors"].append({
                    "type": "persona_drift",
                    "detail": "AI 자기노출 또는 마케팅 전문 용어 과다",
                    "persona_id": r.get("persona_id"),
                })

        if responses and (drift_count / len(responses)) > 0.10:
            logger.warning("T3: 페르소나 이탈률 10% 초과", drift_count=drift_count, total=len(responses))

        outlier_count = sum(1 for r in responses if r.get("is_outlier"))
        valid = [r for r in responses if not r.get("is_outlier")]

        # T1: Persona Collapse 감지
        if len(valid) >= 3:
            valid_scores = [r["click_intention"] for r in valid]
            std_val = float(np.std(valid_scores))
            if std_val < 15:
                logger.warning("T1: Persona Collapse 감지", std=std_val)
                state["errors"].append({
                    "type": "persona_collapse",
                    "detail": f"click_intention std={std_val:.1f} < 15",
                    "persona_id": None,
                })

        # T2: 긍정 편향 감지
        if valid:
            negative_ratio = len([r for r in valid if r["click_intention"] < 40]) / len(valid)
            if negative_ratio < 0.15:
                logger.warning("T2: 긍정 편향 과도", negative_ratio=negative_ratio)
                state["errors"].append({
                    "type": "positive_bias",
                    "detail": f"부정 반응 비율={negative_ratio:.1%} < 15%",
                    "persona_id": None,
                })

        state["raw_responses"] = responses
        state["progress"] = 70
        logger.info("검증 완료", total=len(responses), outliers=outlier_count, valid=len(valid))
        return state
