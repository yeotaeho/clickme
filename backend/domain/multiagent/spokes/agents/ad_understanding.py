import uuid

from loguru import logger
from pydantic import ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.domain.multiagent.models.bases.ad_analysis import AdAnalysis
from backend.domain.multiagent.models.states.simulation_state import SimulationState
from backend.domain.multiagent.spokes.infra.openai_client import LLMClientError, openai_client

_SYSTEM = """
당신은 광고 소재 분석 전문가입니다.
제공된 광고 이미지를 분석하고 반드시 아래 JSON 스키마로만 응답하세요.

{
  "confidence_score": 0.0~1.0,
  "text_analysis": {
    "headline": "주 헤드라인 텍스트",
    "cta": "CTA 버튼/문구",
    "usp_extracted": ["핵심 가치 1", "핵심 가치 2"],
    "pain_point_addressed": "광고가 해결하는 소비자 페인포인트",
    "body_copy": ["서브 카피 1"],
    "emotional_keywords": ["감성 키워드"]
  },
  "visual_analysis": {
    "dominant_colors": ["#색상코드"],
    "emotional_tone": "warm|cool|neutral|energetic|calm",
    "layout_type": "minimal|busy|balanced|text-heavy|image-heavy",
    "image_quality": "high|medium|low"
  },
  "strategic_analysis": {
    "target_demographic": "주요 타깃 소비자 설명",
    "purchase_stage_target": "awareness|consideration|conversion",
    "brand_tone": "브랜드 톤앤매너"
  }
}
"""

_USER = "위 광고 이미지를 분석하여 JSON으로 응답하세요."


class AdUnderstandingAgent:
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10), reraise=True)
    async def _call_vision(self, base64_image: str) -> dict:
        return await openai_client.vision_completion(
            system_prompt=_SYSTEM,
            user_prompt=_USER,
            base64_image=base64_image,
            model="gpt-4o",
        )

    async def run(self, state: SimulationState) -> SimulationState:
        cached = state["ad_input"].get("ad_analysis_cached")
        if cached:
            state["ad_analysis"] = dict(cached)
            state["progress"] = max(state.get("progress", 0), 15)
            logger.info("캐시된 광고 분석 사용", ad_id=cached.get("ad_id"))
            return state

        ad_id = str(uuid.uuid4())
        base64_image = state["ad_input"].get("base64_image", "")

        try:
            raw = await self._call_vision(base64_image)
            raw = self._normalize_vision_payload(raw)
            analysis = AdAnalysis(
                ad_id=ad_id,
                input_type="image",
                **raw,
            )
            state["ad_analysis"] = analysis.model_dump()
            state["progress"] = 15
            logger.info("광고 분석 완료", ad_id=ad_id, confidence=raw.get("confidence_score"))
        except ValidationError as e:
            logger.error("광고 분석 응답 검증 실패 — 빈 분석으로 진행", error=str(e))
            state["errors"].append({"type": "ad_analysis_validation_failed", "detail": str(e), "persona_id": None})
            state["ad_analysis"] = AdAnalysis.empty(ad_id).model_dump()
        except LLMClientError as e:
            logger.error("광고 분석 실패 — 빈 분석으로 진행", error=str(e))
            state["errors"].append({"type": "ad_analysis_failed", "detail": str(e), "persona_id": None})
            state["ad_analysis"] = AdAnalysis.empty(ad_id).model_dump()

        return state

    @staticmethod
    def _normalize_vision_payload(raw: dict) -> dict:
        """LLM의 null/누락 응답을 AdAnalysis 스키마에 맞게 보정."""
        if not isinstance(raw, dict):
            return {}

        text = raw.get("text_analysis") or {}
        visual = raw.get("visual_analysis") or {}
        strategic = raw.get("strategic_analysis") or {}

        text["headline"] = text.get("headline") or ""
        text["cta"] = text.get("cta") or ""
        text["usp_extracted"] = text.get("usp_extracted") or []
        text["pain_point_addressed"] = text.get("pain_point_addressed") or ""
        text["body_copy"] = text.get("body_copy") or []
        text["emotional_keywords"] = text.get("emotional_keywords") or []

        visual["dominant_colors"] = visual.get("dominant_colors") or []
        visual["emotional_tone"] = visual.get("emotional_tone") or "neutral"
        visual["layout_type"] = visual.get("layout_type") or "balanced"
        visual["image_quality"] = visual.get("image_quality") or "high"

        strategic["target_demographic"] = strategic.get("target_demographic") or "일반 소비자"
        strategic["purchase_stage_target"] = strategic.get("purchase_stage_target") or "awareness"
        strategic["brand_tone"] = strategic.get("brand_tone") or ""

        raw["confidence_score"] = raw.get("confidence_score") if raw.get("confidence_score") is not None else 0.0
        raw["text_analysis"] = text
        raw["visual_analysis"] = visual
        raw["strategic_analysis"] = strategic
        return raw
