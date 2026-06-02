from pydantic import BaseModel, field_validator

from backend.domain.multiagent.models.enums import ActionTaken, ScrollBehavior


class PersonaResponse(BaseModel):
    persona_id: str
    scroll_behavior: ScrollBehavior
    first_emotion: str
    click_intention: int  # 0~100
    purchase_intention: int  # 0~100
    trust_score: int  # 0~100
    memorability: int  # 0~100
    rejection_feeling: int  # 0~100
    audience_fit: int  # 0~100
    first_impression_text: str
    main_concern: str | None = None
    action_taken: ActionTaken
    is_outlier: bool = False

    @field_validator(
        "click_intention",
        "purchase_intention",
        "trust_score",
        "memorability",
        "rejection_feeling",
        "audience_fit",
    )
    @classmethod
    def validate_score(cls, v: int) -> int:
        if not 0 <= v <= 100:
            raise ValueError("0~100 범위여야 합니다")
        return v
