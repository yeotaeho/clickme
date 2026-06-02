from pydantic import BaseModel, field_validator


class PersonaGenerationRequest(BaseModel):
    count: int = 20
    age_range: list[int] = [20, 50]  # [min, max]
    gender_ratio: dict[str, float] = {"male": 0.5, "female": 0.5}
    occupation_types: list[str] = []
    income_range: str = "중산층"
    target_description: str = ""  # 자유 텍스트 타깃 설명

    @field_validator("count")
    @classmethod
    def validate_count(cls, v: int) -> int:
        if not 1 <= v <= 200:
            raise ValueError("1~200 범위여야 합니다")
        return v

    @field_validator("age_range")
    @classmethod
    def validate_age_range(cls, v: list[int]) -> list[int]:
        if len(v) != 2 or v[0] >= v[1]:
            raise ValueError("[min, max] 형식, min < max")
        return v


class PersonaPoolResponse(BaseModel):
    pool_id: str
    personas: list[dict]  # list[Persona.model_dump()]
    count: int
    message: str = "페르소나 풀 생성 완료"
