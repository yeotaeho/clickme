from fastapi import BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.multiagent.hub.services import simulation_service
from backend.domain.multiagent.models.transfer.simulation_dto import (
    SimulationCreateRequest,
    SimulationCreateResponse,
    SimulationReport,
    SimulationStatusResponse,
)


class SimulationRouter:
    """요청 유효성 검사 후 서비스 레이어로 위임하는 라우팅 레이어."""

    async def create_and_run(
        self,
        request: SimulationCreateRequest,
        ad_input: dict,
        background_tasks: BackgroundTasks,
        db: AsyncSession,
    ) -> SimulationCreateResponse:
        if not request.ad_id:
            raise HTTPException(status_code=400, detail="ad_id가 필요합니다")

        response = await simulation_service.create_simulation(request, db)
        await db.commit()

        background_tasks.add_task(
            simulation_service.run_simulation_background,
            simulation_id=response.simulation_id,
            ad_input={**ad_input, "persona_config": request.persona_config},
        )
        return response

    async def get_status(self, simulation_id: str, db: AsyncSession) -> SimulationStatusResponse:
        try:
            return await simulation_service.get_simulation_status(simulation_id, db)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    async def get_report(self, simulation_id: str, db: AsyncSession) -> SimulationReport:
        try:
            return await simulation_service.get_simulation_report(simulation_id, db)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))


simulation_router = SimulationRouter()
