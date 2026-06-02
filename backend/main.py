from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from backend.api.v1.multiagent.router import router as multiagent_router
from backend.core.config.settings import settings
from backend.core.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Persona.100 API 서버 시작")
    # 개발 환경: 테이블 자동 생성 (운영은 alembic 사용)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("DB 테이블 초기화 완료")
    yield
    logger.info("서버 종료")
    await engine.dispose()


app = FastAPI(
    title="Persona.100 API",
    description="100개 LLM 에이전트로 광고 소재를 사전 평가하는 B2B SaaS 백엔드",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(multiagent_router)


@app.get("/health", tags=["system"])
async def health() -> dict:
    return {"status": "ok", "service": "persona100-api"}


@app.get("/", tags=["system"])
async def root() -> dict:
    return {"message": "Persona.100 API", "docs": "/docs"}
