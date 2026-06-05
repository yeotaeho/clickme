from collections import defaultdict

import numpy as np

from backend.domain.multiagent.models.bases.persona import get_age_reliability
from backend.domain.multiagent.models.states.simulation_state import SimulationState


def _age_group(age: int) -> str:
    if age < 25:
        return "20대 초반"
    if age < 30:
        return "20대 후반"
    if age < 40:
        return "30대"
    if age < 50:
        return "40대"
    return "50대 이상"


class AggregationService:
    def run(self, state: SimulationState) -> SimulationState:
        responses = [r for r in state.get("raw_responses", []) if not r.get("is_outlier")]
        persona_pool = {p["persona_id"]: p for p in state.get("persona_pool", [])}

        if not responses:
            state["aggregated_stats"] = {}
            return state

        # 연령대별 집계
        age_groups: dict[str, list] = defaultdict(list)
        gender_groups: dict[str, list] = defaultdict(list)
        age_reliability: dict[str, str] = {}

        for r in responses:
            persona = persona_pool.get(r["persona_id"])
            if persona:
                age = persona["layer1"]["age"]
                gender = persona["layer1"]["gender"]
                group = _age_group(age)
                age_groups[group].append(r)
                gender_groups[gender].append(r)
                if group not in age_reliability:
                    age_reliability[group] = get_age_reliability(age)

        def group_stats(group_responses: list[dict]) -> dict:
            if not group_responses:
                return {}
            return {
                "click_intention_avg": round(float(np.mean([r["click_intention"] for r in group_responses])), 1),
                "purchase_intention_avg": round(float(np.mean([r["purchase_intention"] for r in group_responses])), 1),
                "audience_fit_avg": round(float(np.mean([r["audience_fit"] for r in group_responses])), 1),
                "count": len(group_responses),
            }

        # 긍정/부정 피드백 수집
        positive = [
            r["first_impression_text"]
            for r in sorted(responses, key=lambda x: x["click_intention"], reverse=True)
            if r.get("first_impression_text") and r["click_intention"] >= 60
        ][:5]

        negative = [
            r["first_impression_text"]
            for r in sorted(responses, key=lambda x: x["rejection_feeling"], reverse=True)
            if r.get("first_impression_text") and r["rejection_feeling"] >= 50
        ][:5]

        state["aggregated_stats"] = {
            "segment_breakdown": {
                "age_group": {k: group_stats(v) for k, v in age_groups.items()},
                "gender": {k: group_stats(v) for k, v in gender_groups.items()},
            },
            "top_feedbacks": {"positive": positive, "negative": negative},
            "total_valid": len(responses),
            "age_reliability": age_reliability,
        }
        state["progress"] = 75
        return state
