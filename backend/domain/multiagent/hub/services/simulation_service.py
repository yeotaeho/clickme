import uuid

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.multiagent.hub.repositories.simulation_repository import SimulationRepository
from backend.domain.multiagent.models.enums import SimulationStatus
from backend.domain.multiagent.models.states.simulation_state import initial_state
from backend.domain.multiagent.models.transfer.simulation_dto import (
    SimulationCreateRequest,
    SimulationCreateResponse,
    SimulationReport,
    SimulationStatusResponse,
)

repo = SimulationRepository()


async def create_simulation(
    request: SimulationCreateRequest,
    db: AsyncSession,
) -> SimulationCreateResponse:
    sim = await repo.create(db, ad_id=request.ad_id, persona_count=request.persona_count)
    logger.info("시뮬레이션 생성", simulation_id=sim.id)
    return SimulationCreateResponse(simulation_id=sim.id)


async def run_simulation_background(
    simulation_id: str,
    ad_input: dict,
) -> None:
    """BackgroundTasks에서 실행되는 LangGraph 그래프 실행 함수."""
    from backend.core.database import async_session_factory
    from backend.domain.multiagent.hub.orchestrator.simulation_graph import simulation_graph

    async with async_session_factory() as db:
        try:
            await repo.update_status(db, simulation_id, SimulationStatus.RUNNING, progress=5)
            await db.commit()

            state = initial_state(simulation_id=simulation_id, ad_input=ad_input)
            final_state = await simulation_graph.ainvoke(state)

            async with async_session_factory() as db2:
                await repo.save_persona_responses(db2, simulation_id, final_state.get("raw_responses", []))
                await repo.save_report(db2, simulation_id, final_state.get("report", {}))
                await repo.update_status(db2, simulation_id, SimulationStatus.COMPLETED, progress=100)
                await db2.commit()

            logger.info("시뮬레이션 완료", simulation_id=simulation_id)
        except Exception as e:
            logger.error("시뮬레이션 실패", simulation_id=simulation_id, error=str(e))
            async with async_session_factory() as db3:
                await repo.update_status(db3, simulation_id, SimulationStatus.FAILED)
                await db3.commit()


async def get_simulation_status(simulation_id: str, db: AsyncSession) -> SimulationStatusResponse:
    sim = await repo.get_by_id(db, simulation_id)
    if not sim:
        raise ValueError(f"시뮬레이션 없음: {simulation_id}")
    return SimulationStatusResponse(
        simulation_id=simulation_id,
        status=SimulationStatus(sim.status),
        progress=sim.progress,
    )


async def get_simulation_report(simulation_id: str, db: AsyncSession) -> SimulationReport:
    report_orm = await repo.get_report(db, simulation_id)
    if not report_orm:
        raise ValueError(f"리포트 없음: {simulation_id}")
    return SimulationReport.model_validate(report_orm.report_data)
