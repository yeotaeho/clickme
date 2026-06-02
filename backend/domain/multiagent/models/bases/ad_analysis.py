from pydantic import BaseModel, field_validator


class TextAnalysis(BaseModel):
    headline: str
    cta: str
    usp_extracted: list[str]
    pain_point_addressed: str
    body_copy: list[str] = []
    emotional_keywords: list[str] = []


class VisualAnalysis(BaseModel):
    dominant_colors: list[str]
    emotional_tone: str
    layout_type: str
    image_quality: str = "high"


class StrategicAnalysis(BaseModel):
    target_demographic: str
    purchase_stage_target: str  # "awareness" | "consideration" | "conversion"
    brand_tone: str = ""


class AdAnalysis(BaseModel):
    ad_id: str
    input_type: str = "image"
    confidence_score: float  # 0.0~1.0

    text_analysis: TextAnalysis
    visual_analysis: VisualAnalysis
    strategic_analysis: StrategicAnalysis

    @field_validator("confidence_score")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("0.0~1.0 범위여야 합니다")
        return v

    @classmethod
    def empty(cls, ad_id: str) -> "AdAnalysis":
        return cls(
            ad_id=ad_id,
            input_type="image",
            confidence_score=0.0,
            text_analysis=TextAnalysis(
                headline="",
                cta="",
                usp_extracted=[],
                pain_point_addressed="",
            ),
            visual_analysis=VisualAnalysis(
                dominant_colors=[],
                emotional_tone="neutral",
                layout_type="unknown",
            ),
            strategic_analysis=StrategicAnalysis(
                target_demographic="일반 소비자",
                purchase_stage_target="awareness",
            ),
        )
