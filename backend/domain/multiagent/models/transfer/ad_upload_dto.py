from pydantic import BaseModel, field_validator


class AdUploadRequest(BaseModel):
    base64_image: str  # "data:image/jpeg;base64,..." 또는 순수 base64
    filename: str
    campaign_context: str = ""  # 캠페인 배경 정보 (선택)

    @field_validator("base64_image")
    @classmethod
    def normalize_base64(cls, v: str) -> str:
        if v.startswith("data:"):
            return v
        return f"data:image/jpeg;base64,{v}"

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        allowed = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
        suffix = "." + v.rsplit(".", 1)[-1].lower() if "." in v else ""
        if suffix not in allowed:
            raise ValueError(f"허용 형식: {allowed}")
        return v


class AdUploadResponse(BaseModel):
    ad_id: str
    analysis: dict  # AdAnalysis.model_dump()
    message: str = "광고 소재 분석 완료"
