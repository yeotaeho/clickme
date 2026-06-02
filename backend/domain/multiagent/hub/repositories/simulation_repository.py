import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, Integer, DateTime, Boolean
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.database import Base
from backend.domain.multiagent.models.enums import SimulationStatus


# ─── ORM 모델 ────────────────────────────────────────────────


class AdORM(Base):
    __tablename__ = "ads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    input_type: Mapped[str] = mapped_column(String(20), default="image")
    analysis_result: Mapped[dict] = mapped_column(JSONB, nullable=True)
    campaign_context: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SimulationORM(Base):
    __tablename__ = "simulations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ad_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=SimulationStatus.PENDING)
    persona_count: Mapped[int] = mapped_column(Integer, default=20)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    results_summary: Mapped[dict] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PersonaResponseORM(Base):
    __tablename__ = "persona_responses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    simulation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    persona_id: Mapped[str] = mapped_column(String(20), nullable=False)
    response_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_outlier: Mapped[bool] = mapped_column(Boolean, default=False)


class ReportORM(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    simulation_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    report_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    pdf_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ─── 저장소 ──────────────────────────────────────────────────


class SimulationRepository:
    async def create(self, db: AsyncSession, ad_id: str, persona_count: int) -> SimulationORM:
        sim = SimulationORM(
            id=str(uuid.uuid4()),
            ad_id=ad_id,
            persona_count=persona_count,
        )
        db.add(sim)
        await db.flush()
        return sim

    async def update_status(
        self,
        db: AsyncSession,
        simulation_id: str,
        status: SimulationStatus,
        progress: int | None = None,
    ) -> None:
        values: dict = {"status": status}
        if progress is not None:
            values["progress"] = progress
        if status == SimulationStatus.COMPLETED:
            values["completed_at"] = datetime.now(timezone.utc)
        await db.execute(
            update(SimulationORM).where(SimulationORM.id == simulation_id).values(**values)
        )

    async def save_report(self, db: AsyncSession, simulation_id: str, report_data: dict) -> None:
        report = ReportORM(simulation_id=simulation_id, report_data=report_data)
        db.add(report)
        await db.flush()

    async def get_by_id(self, db: AsyncSession, simulation_id: str) -> SimulationORM | None:
        result = await db.execute(select(SimulationORM).where(SimulationORM.id == simulation_id))
        return result.scalar_one_or_none()

    async def get_report(self, db: AsyncSession, simulation_id: str) -> ReportORM | None:
        result = await db.execute(select(ReportORM).where(ReportORM.simulation_id == simulation_id))
        return result.scalar_one_or_none()

    async def save_persona_responses(
        self, db: AsyncSession, simulation_id: str, responses: list[dict]
    ) -> None:
        for r in responses:
            orm = PersonaResponseORM(
                simulation_id=simulation_id,
                persona_id=r.get("persona_id", ""),
                response_data=r,
                is_outlier=r.get("is_outlier", False),
            )
            db.add(orm)
        await db.flush()

    async def get_status(self, simulation_id: str) -> dict:
        from backend.core.database import async_session_factory
        async with async_session_factory() as db:
            sim = await self.get_by_id(db, simulation_id)
            if not sim:
                return {"error": "not_found"}
            return {"simulation_id": simulation_id, "status": sim.status, "progress": sim.progress}
