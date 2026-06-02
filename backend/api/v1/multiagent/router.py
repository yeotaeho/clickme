import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.domain.multiagent.hub.repositories.simulation_repository import AdORM
from backend.domain.multiagent.hub.routing.simulation_router import simulation_router
from backend.domain.multiagent.hub.services import ad_upload_service
from backend.domain.multiagent.models.states.simulation_state import initial_state
from backend.domain.multiagent.models.transfer.ad_upload_dto import AdUploadRequest, AdUploadResponse
from backend.domain.multiagent.models.transfer.persona_dto import PersonaGenerationRequest, PersonaPoolResponse
from backend.domain.multiagent.models.transfer.simulation_dto import (
    SimulationCreateRequest,
    SimulationCreateResponse,
    SimulationReport,
    SimulationStatusResponse,
)
from backend.domain.multiagent.spokes.agents.persona_generation import PersonaGenerationAgent

router = APIRouter(prefix="/api/v1", tags=["multiagent"])

_persona_agent = PersonaGenerationAgent()


@router.post(
    "/ads/upload",
    response_model=AdUploadResponse,
    summary="광고 이미지 파일 업로드 + Vision 분석",
    description="multipart/form-data: `file`(이미지), `campaign_context`(선택). 서버에서 base64를 생성합니다.",
)
async def upload_ad(
    file: UploadFile = File(..., description="광고 배너 이미지 (.jpg, .png, .webp, .gif)"),
    campaign_context: str = Form("", description="캠페인 배경 설명"),
    db: AsyncSession = Depends(get_db),
) -> AdUploadResponse:
    return await ad_upload_service.upload_file_and_analyze(db, file, campaign_context)


@router.post(
    "/ads/upload/json",
    response_model=AdUploadResponse,
    summary="광고 소재 업로드 (JSON base64, 레거시/테스트용)",
)
async def upload_ad_json(
    body: AdUploadRequest,
    db: AsyncSession = Depends(get_db),
) -> AdUploadResponse:
    return await ad_upload_service.upload_and_analyze(
        db,
        base64_image=body.base64_image,
        filename=body.filename,
        campaign_context=body.campaign_context,
    )


@router.post("/personas/generate", response_model=PersonaPoolResponse, summary="페르소나 풀 생성")
async def generate_personas(body: PersonaGenerationRequest) -> PersonaPoolResponse:
    pool_id = str(uuid.uuid4())
    state = initial_state(simulation_id="", ad_input={"persona_config": body.model_dump()})
    state = await _persona_agent.run(state)
    return PersonaPoolResponse(
        pool_id=pool_id,
        personas=state["persona_pool"],
        count=len(state["persona_pool"]),
    )


@router.post("/simulations", response_model=SimulationCreateResponse, summary="시뮬레이션 실행")
async def create_simulation(
    body: SimulationCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> SimulationCreateResponse:
    result = await db.execute(select(AdORM).where(AdORM.id == body.ad_id))
    ad_orm = result.scalar_one_or_none()
    if not ad_orm:
        raise HTTPException(status_code=404, detail=f"광고 없음: {body.ad_id}")

    ad_input = {
        "base64_image": "",
        "ad_analysis_cached": ad_orm.analysis_result,
        "persona_config": {"count": body.persona_count, **body.persona_config},
    }

    return await simulation_router.create_and_run(body, ad_input, background_tasks, db)


@router.get(
    "/simulations/{simulation_id}",
    response_model=SimulationStatusResponse,
    summary="시뮬레이션 상태 조회",
)
async def get_simulation_status(
    simulation_id: str,
    db: AsyncSession = Depends(get_db),
) -> SimulationStatusResponse:
    return await simulation_router.get_status(simulation_id, db)


@router.get(
    "/reports/{simulation_id}",
    response_model=SimulationReport,
    summary="최종 리포트 조회",
)
async def get_report(
    simulation_id: str,
    db: AsyncSession = Depends(get_db),
) -> SimulationReport:
    return await simulation_router.get_report(simulation_id, db)
