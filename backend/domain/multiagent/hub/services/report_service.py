from backend.domain.multiagent.models.enums import SimulationStatus
from backend.domain.multiagent.models.states.simulation_state import SimulationState
from backend.domain.multiagent.models.transfer.simulation_dto import (
    ActionItem,
    ExecutiveSummary,
    SimulationMetrics,
    SimulationReport,
    TopFeedbacks,
)


class ReportService:
    def run(self, state: SimulationState) -> SimulationState:
        predictions = state.get("performance_predictions", {})
        aggregated = state.get("aggregated_stats", {})
        feedbacks = aggregated.get("top_feedbacks", {})
        responses = [r for r in state.get("raw_responses", []) if not r.get("is_outlier")]

        executive = ExecutiveSummary(
            overall_score=predictions.get("overall_score", 0),
            verdict=predictions.get("verdict", "borderline"),
            top_action=predictions.get("top_action", "개선안을 확인하세요"),
        )

        metrics = SimulationMetrics(
            ctr_prediction={
                "raw": predictions.get("ctr_raw", 0.0),
                "corrected": predictions.get("ctr_corrected", 0.0),
                "percentile": predictions.get("ctr_percentile", "측정 불가"),
            },
            purchase_intent=predictions.get("purchase_intent", 0.0),
            audience_fit=predictions.get("audience_fit", 0.0),
            rejection_rate=predictions.get("rejection_rate", 0.0),
            confidence_score=predictions.get("confidence_score", 0.0),
        )

        action_items = [
            ActionItem(**item) for item in state.get("recommendations", [])
            if isinstance(item, dict) and all(k in item for k in ("priority", "issue", "suggestion"))
        ]

        report = SimulationReport(
            simulation_id=state["simulation_id"],
            status=SimulationStatus.COMPLETED,
            executive_summary=executive,
            metrics=metrics,
            segment_breakdown=aggregated.get("segment_breakdown", {}),
            top_feedbacks=TopFeedbacks(
                positive=feedbacks.get("positive", []),
                negative=feedbacks.get("negative", []),
            ),
            action_items=action_items,
            outliers_excluded=predictions.get("outliers_excluded", 0),
            persona_count_valid=len(responses),
            reliability_notes=aggregated.get("age_reliability", {}),
        )

        state["report"] = report.model_dump()
        state["progress"] = 100
        return state
