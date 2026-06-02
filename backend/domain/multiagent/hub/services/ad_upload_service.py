import base64
import uuid
from dataclasses import dataclass

from fastapi import HTTPException, UploadFile
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.multiagent.hub.repositories.simulation_repository import AdORM
from backend.domain.multiagent.models.states.simulation_state import initial_state
from backend.domain.multiagent.models.transfer.ad_upload_dto import AdUploadResponse
from backend.domain.multiagent.spokes.agents.ad_understanding import AdUnderstandingAgent

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
EXTENSION_TO_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10MB

_ad_agent = AdUnderstandingAgent()


@dataclass(frozen=True)
class PreparedAdImage:
    """업로드 파일에서 추출한 Vision API용 이미지 페이로드."""

    filename: str
    base64_image: str  # data:image/...;base64,...
    content_type: str
    size_bytes: int


def _normalize_filename(filename: str | None) -> str:
    name = (filename or "upload.jpg").strip()
    if not name or name.endswith("/"):
        return "upload.jpg"
    suffix = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"허용 이미지 형식: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    return name


def bytes_to_data_url(image_bytes: bytes, filename: str) -> str:
    """이미지 바이트 → OpenAI Vision용 data URL base64 문자열."""
    filename = _normalize_filename(filename)
    suffix = "." + filename.rsplit(".", 1)[-1].lower()
    mime = EXTENSION_TO_MIME[suffix]
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{encoded}"


async def prepare_image_from_upload(file: UploadFile) -> PreparedAdImage:
    """multipart 업로드 파일을 읽어 filename·base64 data URL을 생성한다."""
    if not file.content_type or not file.content_type.startswith("image/"):
        logger.warning("비이미지 Content-Type", content_type=file.content_type)

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="빈 파일입니다")
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"파일 크기 제한 초과 (최대 {MAX_IMAGE_BYTES // (1024 * 1024)}MB)",
        )

    filename = _normalize_filename(file.filename)
    base64_image = bytes_to_data_url(raw, filename)
    suffix = "." + filename.rsplit(".", 1)[-1].lower()
    content_type = file.content_type or EXTENSION_TO_MIME[suffix]

    logger.info(
        "이미지 base64 인코딩 완료",
        filename=filename,
        size_bytes=len(raw),
        content_type=content_type,
    )
    return PreparedAdImage(
        filename=filename,
        base64_image=base64_image,
        content_type=content_type,
        size_bytes=len(raw),
    )


async def upload_and_analyze(
    db: AsyncSession,
    *,
    base64_image: str,
    filename: str,
    campaign_context: str = "",
) -> AdUploadResponse:
    """base64 data URL + filename으로 Vision 분석 후 DB에 저장."""
    filename = _normalize_filename(filename)
    if not base64_image.startswith("data:"):
        base64_image = bytes_to_data_url(
            base64.b64decode(base64_image.split(",")[-1] if "," in base64_image else base64_image),
            filename,
        )

    ad_id = str(uuid.uuid4())
    state = initial_state(
        simulation_id="",
        ad_input={
            "base64_image": base64_image,
            "filename": filename,
            "campaign_context": campaign_context,
        },
    )
    state = await _ad_agent.run(state)
    analysis = dict(state["ad_analysis"])
    analysis["ad_id"] = ad_id

    db.add(
        AdORM(
            id=ad_id,
            input_type="image",
            analysis_result=analysis,
            campaign_context=campaign_context,
        )
    )
    await db.flush()

    return AdUploadResponse(ad_id=ad_id, analysis=analysis)


async def upload_file_and_analyze(
    db: AsyncSession,
    file: UploadFile,
    campaign_context: str = "",
) -> AdUploadResponse:
    """파일 업로드 → base64 생성 → Vision 분석."""
    prepared = await prepare_image_from_upload(file)
    return await upload_and_analyze(
        db,
        base64_image=prepared.base64_image,
        filename=prepared.filename,
        campaign_context=campaign_context,
    )
