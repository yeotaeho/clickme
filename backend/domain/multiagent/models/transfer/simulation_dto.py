from pydantic import BaseModel

from backend.domain.multiagent.models.enums import SimulationStatus


class SimulationCreateRequest(BaseModel):
    ad_id: str
    persona_count: int = 20
    persona_config: dict = {}  # PersonaGenerationRequest 파라미터 (선택)


class SimulationStatusResponse(BaseModel):
    simulation_id: str
    status: SimulationStatus
    progress: int  # 0~100
    message: str = ""


class ExecutiveSummary(BaseModel):
    overall_score: int  # 0~100
    verdict: str  # "pass" | "fail" | "borderline"
    top_action: str


class SimulationMetrics(BaseModel):
    ctr_prediction: dict  # {"raw": float, "corrected": float, "percentile": str}
    purchase_intent: float
    audience_fit: float
    rejection_rate: float
    confidence_score: float


class TopFeedbacks(BaseModel):
    positive: list[str]
    negative: list[str]


class ActionItem(BaseModel):
    priority: str  # "HIGH" | "MID" | "LOW"
    issue: str
    suggestion: str


class SimulationReport(BaseModel):
    simulation_id: str
    status: SimulationStatus
    disclaimer: str = (
        "본 결과는 AI 시뮬레이션 기반 예측입니다. 실제 성과와 ±20~30% 오차 가능."
    )
    executive_summary: ExecutiveSummary
    metrics: SimulationMetrics
    segment_breakdown: dict  # {"age_group": {...}, "gender": {...}}
    top_feedbacks: TopFeedbacks
    action_items: list[ActionItem]
    outliers_excluded: int
    persona_count_valid: int


class SimulationCreateResponse(BaseModel):
    simulation_id: str
    status: SimulationStatus = SimulationStatus.PENDING
    message: str = "시뮬레이션이 시작되었습니다"
