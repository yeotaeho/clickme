from pydantic import BaseModel, field_validator


class PersonaLayer1(BaseModel):
    age: int
    gender: str  # "male" | "female"
    region: str
    occupation: str
    annual_income_range: str
    education: str


class PersonaLayer2(BaseModel):
    purchase_motivation_primary: str
    price_sensitivity: float  # 0.0~1.0
    impulse_buying_tendency: float  # 0.0~1.0
    ad_avoidance_tendency: float  # 0.0~1.0
    preferred_ad_format: list[str]
    trusted_channels: list[str]
    decision_speed: str  # "fast" | "medium" | "slow"

    @field_validator("price_sensitivity", "impulse_buying_tendency", "ad_avoidance_tendency")
    @classmethod
    def validate_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("0.0~1.0 범위여야 합니다")
        return v


class PersonaLayer3(BaseModel):
    recent_purchase_experience: str  # 동질화 방지용 서사적 앵커
    current_pain_point: str
    ad_trigger_words: list[str]
    ad_repellent_words: list[str]  # 이 단어 포함 광고 → 부정 반응 강제
    emotional_state_current: str


AGE_RELIABILITY_MAP: dict[tuple[int, int], str] = {
    (0, 19): "very_low",
    (20, 39): "high",
    (40, 49): "medium",
    (50, 59): "low",
    (60, 99): "very_low",
}


def get_age_reliability(age: int) -> str:
    for (low, high), level in AGE_RELIABILITY_MAP.items():
        if low <= age <= high:
            return level
    return "unknown"


class Persona(BaseModel):
    persona_id: str  # "P_0042" 형식
    layer1: PersonaLayer1
    layer2: PersonaLayer2
    layer3: PersonaLayer3
    temperature_assigned: float
    seed: int
    cluster_id: str = ""

    @classmethod
    def assign_temperature(cls, layer1: PersonaLayer1, layer2: PersonaLayer2) -> float:
        base = 0.7
        impulse_adj = layer2.impulse_buying_tendency * 0.3
        age_adj = -0.1 if layer1.age > 50 else 0.1
        return min(max(base + impulse_adj + age_adj, 0.5), 1.1)
