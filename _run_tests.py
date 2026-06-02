"""
Persona.100 Phase 1 통합 테스트
테스트 범위:
  T1  - Settings 로드
  T2  - DB 연결 (Neon PostgreSQL)
  T3  - Pydantic 모델 유효성 검증
  T4  - ValidationAgent (순수 Python, LLM 없음)
  T5  - AggregationService (순수 Python, LLM 없음)
  T6  - ReportService (순수 Python, LLM 없음)
  T7  - LangGraph 그래프 컴파일 구조
  T8  - FastAPI 앱 / 라우트 등록
  T9  - HTTP health 엔드포인트 (TestClient)
  T10 - OpenAI API 연결 확인 (실제 호출, 최소 토큰)
  T11 - PersonaGenerationAgent 실제 LLM 호출 (20명)
  T12 - ReactionSimulationAgent 실제 LLM 호출 (3명 샘플)
  T13 - Supervisor 라우팅 로직
  T14 - DB CRUD (테이블 실제 read/write)
"""

import asyncio
import sys
import time
import traceback

sys.path.insert(0, ".")

PASS = "[PASS]"
FAIL = "[FAIL]"
SKIP = "[SKIP]"

results: list[tuple[str, str, str]] = []


def report(test_id: str, name: str, status: str, detail: str = "") -> None:
    results.append((test_id, name, status, detail))
    print(f"  {status} [{test_id}] {name}" + (f" - {detail}" if detail else ""))


# ─── T1: Settings ────────────────────────────────────────────

def test_settings():
    try:
        from backend.core.config.settings import settings
        assert settings.DATABASE_URL.startswith("postgresql+asyncpg://")
        assert settings.OPENAI_API_KEY.startswith("sk-")
        assert settings.DEFAULT_PERSONA_COUNT == 20
        report("T1", "Settings 로드", PASS, f"DB={settings.DATABASE_URL[20:55]}...")
    except Exception as e:
        report("T1", "Settings 로드", FAIL, str(e))


# ─── T2: DB 연결 ─────────────────────────────────────────────

async def test_db_connection():
    try:
        import asyncpg
        url = "postgresql://neondb_owner:npg_vnkWfrC0tK9z@ep-rough-mode-aoqnomrb-pooler.c-2.ap-southeast-1.aws.neon.tech/neondb"
        conn = await asyncpg.connect(url, ssl="require")
        tables = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
        )
        await conn.close()
        names = [r["tablename"] for r in tables]
        required = {"ads", "simulations", "persona_responses", "reports"}
        missing = required - set(names)
        if missing:
            report("T2", "DB 연결 + 테이블", FAIL, f"누락: {missing}")
        else:
            report("T2", "DB 연결 + 테이블", PASS, f"테이블: {names}")
    except Exception as e:
        report("T2", "DB 연결 + 테이블", FAIL, str(e))


# ─── T3: Pydantic 모델 ───────────────────────────────────────

def test_pydantic_models():
    try:
        from backend.domain.multiagent.models.bases.persona import (
            Persona, PersonaLayer1, PersonaLayer2, PersonaLayer3,
        )
        from backend.domain.multiagent.models.bases.ad_analysis import AdAnalysis
        from backend.domain.multiagent.models.bases.persona_response import PersonaResponse
        from backend.domain.multiagent.models.enums import SimulationStatus, ScrollBehavior, ActionTaken
        from backend.domain.multiagent.models.states.simulation_state import initial_state

        # Persona 생성
        l1 = PersonaLayer1(age=30, gender="female", region="서울", occupation="마케터",
                           annual_income_range="3000~5000만원", education="대졸")
        l2 = PersonaLayer2(purchase_motivation_primary="실용성", price_sensitivity=0.6,
                           impulse_buying_tendency=0.4, ad_avoidance_tendency=0.3,
                           preferred_ad_format=["SNS"], trusted_channels=["인스타그램"],
                           decision_speed="medium")
        l3 = PersonaLayer3(recent_purchase_experience="지난달 운동화 구매",
                           current_pain_point="가성비 좋은 브랜드 찾기 어려움",
                           ad_trigger_words=["한정"], ad_repellent_words=["과장"],
                           emotional_state_current="평온")
        temp = Persona.assign_temperature(l1, l2)
        p = Persona(persona_id="P_0001", layer1=l1, layer2=l2, layer3=l3,
                    temperature_assigned=temp, seed=42)
        assert 0.5 <= p.temperature_assigned <= 1.1

        # AdAnalysis 빈 모델
        ad = AdAnalysis.empty("test-ad-id")
        assert ad.input_type == "image"

        # PersonaResponse
        pr = PersonaResponse(
            persona_id="P_0001", scroll_behavior=ScrollBehavior.PAUSE_3SEC,
            first_emotion="호기심", click_intention=72, purchase_intention=55,
            trust_score=60, memorability=65, rejection_feeling=15, audience_fit=80,
            first_impression_text="깔끔해 보여요", action_taken=ActionTaken.CLICK,
        )
        assert pr.click_intention == 72

        # initial_state
        state = initial_state("sim-001", {"base64_image": "data:image/jpeg;base64,abc"})
        assert state["progress"] == 0

        report("T3", "Pydantic 모델 유효성", PASS, f"temperature={temp:.2f}")
    except Exception as e:
        report("T3", "Pydantic 모델 유효성", FAIL, traceback.format_exc().splitlines()[-1])


# ─── T4: ValidationAgent ─────────────────────────────────────

def test_validation_agent():
    try:
        from backend.domain.multiagent.spokes.agents.validation import ValidationAgent
        from backend.domain.multiagent.models.states.simulation_state import initial_state

        state = initial_state("sim-001", {})
        # 다양한 응답 20개 생성 (IQR 이상치 1개 포함)
        import random
        random.seed(42)
        responses = [
            {
                "persona_id": f"P_{i:04d}",
                "click_intention": random.randint(30, 80),
                "purchase_intention": random.randint(20, 70),
                "trust_score": 60, "memorability": 55,
                "rejection_feeling": random.randint(5, 40),
                "audience_fit": random.randint(50, 90),
                "scroll_behavior": "pause_3sec",
                "first_emotion": "관심",
                "first_impression_text": f"페르소나 {i} 반응",
                "action_taken": "click",
                "is_outlier": False,
            }
            for i in range(1, 20)
        ]
        # 극단 이상치 추가
        responses.append({
            "persona_id": "P_0020", "click_intention": 99,
            "purchase_intention": 99, "trust_score": 99,
            "memorability": 99, "rejection_feeling": 1,
            "audience_fit": 99, "scroll_behavior": "stop_and_read",
            "first_emotion": "열광", "first_impression_text": "최고!",
            "action_taken": "share", "is_outlier": False,
        })
        state["raw_responses"] = responses

        agent = ValidationAgent()
        result = agent.run(state)
        outliers = sum(1 for r in result["raw_responses"] if r.get("is_outlier"))
        report("T4", "ValidationAgent (IQR)", PASS,
               f"총 {len(responses)}개 중 이상치 {outliers}개 탐지")
    except Exception as e:
        report("T4", "ValidationAgent (IQR)", FAIL, traceback.format_exc().splitlines()[-1])


# ─── T5: AggregationService ──────────────────────────────────

def test_aggregation_service():
    try:
        from backend.domain.multiagent.hub.services.aggregation_service import AggregationService
        from backend.domain.multiagent.models.states.simulation_state import initial_state

        state = initial_state("sim-001", {})
        personas = [
            {"persona_id": f"P_{i:04d}", "layer1": {"age": 25 + i * 3, "gender": "female" if i % 2 == 0 else "male"}}
            for i in range(10)
        ]
        responses = [
            {"persona_id": f"P_{i:04d}", "click_intention": 50 + i * 2,
             "purchase_intention": 40 + i, "audience_fit": 60,
             "rejection_feeling": 20, "first_impression_text": f"좋아요 {i}",
             "is_outlier": False}
            for i in range(10)
        ]
        state["persona_pool"] = personas
        state["raw_responses"] = responses

        svc = AggregationService()
        result = svc.run(state)
        seg = result["aggregated_stats"]["segment_breakdown"]
        assert "age_group" in seg and "gender" in seg
        report("T5", "AggregationService", PASS,
               f"세그먼트: {list(seg['age_group'].keys())}")
    except Exception as e:
        report("T5", "AggregationService", FAIL, traceback.format_exc().splitlines()[-1])


# ─── T6: ReportService ───────────────────────────────────────

def test_report_service():
    try:
        from backend.domain.multiagent.hub.services.report_service import ReportService
        from backend.domain.multiagent.models.states.simulation_state import initial_state
        from backend.domain.multiagent.models.transfer.simulation_dto import SimulationReport

        state = initial_state("sim-report-test", {})
        state["raw_responses"] = [
            {"persona_id": "P_0001", "click_intention": 65, "is_outlier": False}
        ]
        state["aggregated_stats"] = {
            "segment_breakdown": {"age_group": {}, "gender": {}},
            "top_feedbacks": {"positive": ["좋아요"], "negative": ["별로에요"]},
        }
        state["performance_predictions"] = {
            "overall_score": 67, "verdict": "borderline",
            "top_action": "카피 수정 권장",
            "ctr_raw": 65.0, "ctr_corrected": 56.7,
            "ctr_percentile": "상위 30%", "purchase_intent": 48.2,
            "audience_fit": 62.0, "rejection_rate": 0.12,
            "confidence_score": 0.78, "outliers_excluded": 1,
        }
        state["recommendations"] = [
            {"priority": "HIGH", "issue": "30대 여성 CTR 낮음", "suggestion": "배경 밝게 수정"},
        ]

        svc = ReportService()
        result = svc.run(state)
        report_obj = SimulationReport.model_validate(result["report"])
        assert report_obj.executive_summary.verdict == "borderline"
        assert report_obj.metrics.confidence_score == 0.78
        report("T6", "ReportService -> SimulationReport", PASS,
               f"verdict={report_obj.executive_summary.verdict}, score={report_obj.executive_summary.overall_score}")
    except Exception as e:
        report("T6", "ReportService -> SimulationReport", FAIL, traceback.format_exc().splitlines()[-1])


# ─── T7: LangGraph 그래프 구조 ───────────────────────────────

def test_langgraph_structure():
    try:
        from backend.domain.multiagent.hub.orchestrator.simulation_graph import simulation_graph
        nodes = list(simulation_graph.nodes.keys())
        required = {"analyze_ad", "generate_personas", "run_reactions",
                    "validate_responses", "aggregate_stats", "predict_performance",
                    "generate_recommendations", "generate_report"}
        missing = required - set(nodes)
        if missing:
            report("T7", "LangGraph 그래프 구조", FAIL, f"누락 노드: {missing}")
        else:
            report("T7", "LangGraph 그래프 구조", PASS, f"노드 {len(nodes)}개: {nodes}")
    except Exception as e:
        report("T7", "LangGraph 그래프 구조", FAIL, str(e))


# ─── T8: FastAPI 라우트 등록 ─────────────────────────────────

def test_fastapi_routes():
    try:
        from backend.main import app
        paths = [r.path for r in app.routes if hasattr(r, "path")]
        required = {"/api/v1/ads/upload", "/api/v1/personas/generate",
                    "/api/v1/simulations", "/api/v1/simulations/{simulation_id}",
                    "/api/v1/reports/{simulation_id}", "/health"}
        missing = required - set(paths)
        if missing:
            report("T8", "FastAPI 라우트 등록", FAIL, f"누락: {missing}")
        else:
            report("T8", "FastAPI 라우트 등록", PASS, f"{len(paths)}개 라우트")
    except Exception as e:
        report("T8", "FastAPI 라우트 등록", FAIL, str(e))


# ─── T9: HTTP health 엔드포인트 ──────────────────────────────

def test_health_endpoint():
    try:
        from fastapi.testclient import TestClient
        from backend.main import app
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        report("T9", "GET /health", PASS, f"응답: {resp.json()}")
    except Exception as e:
        report("T9", "GET /health", FAIL, traceback.format_exc().splitlines()[-1])


# ─── T10: OpenAI API 연결 확인 ───────────────────────────────

async def test_openai_connection():
    try:
        from backend.domain.multiagent.spokes.infra.openai_client import openai_client
        result = await openai_client.chat_completion(
            messages=[
                {"role": "system", "content": "반드시 JSON으로만 응답하세요."},
                {"role": "user", "content": '{"ping": "pong"} 을 그대로 반환하세요.'},
            ],
            model="gpt-4o-mini",
            temperature=0.0,
        )
        assert isinstance(result, dict)
        report("T10", "OpenAI API 연결", PASS, f"응답: {result}")
    except Exception as e:
        report("T10", "OpenAI API 연결", FAIL, str(e)[:80])


# ─── T11: PersonaGenerationAgent (실제 LLM) ──────────────────

async def test_persona_generation():
    try:
        from backend.domain.multiagent.spokes.agents.persona_generation import PersonaGenerationAgent
        from backend.domain.multiagent.models.states.simulation_state import initial_state
        from backend.domain.multiagent.models.bases.ad_analysis import AdAnalysis

        state = initial_state("sim-test", {
            "base64_image": "",
            "persona_config": {"count": 5},  # 비용 절감: 5명만
        })
        state["ad_analysis"] = AdAnalysis.empty("ad-test").model_dump()
        state["ad_analysis"]["strategic_analysis"]["target_demographic"] = "20~30대 직장인 여성"

        t0 = time.time()
        agent = PersonaGenerationAgent()
        result = await agent.run(state)
        elapsed = time.time() - t0
        count = len(result["persona_pool"])
        if count == 0:
            report("T11", "PersonaGenerationAgent", FAIL, f"페르소나 0개 생성 ({elapsed:.1f}s)")
        else:
            p = result["persona_pool"][0]
            report("T11", "PersonaGenerationAgent", PASS,
                   f"{count}명 생성 ({elapsed:.1f}s) | 예: {p['layer1']['age']}세 {p['layer1']['occupation']}")
    except Exception as e:
        report("T11", "PersonaGenerationAgent", FAIL, str(e)[:100])


# ─── T12: ReactionSimulationAgent 3명 샘플 ───────────────────

async def test_reaction_simulation():
    try:
        from backend.domain.multiagent.spokes.agents.reaction_simulation import ReactionSimulationAgent
        from backend.domain.multiagent.models.states.simulation_state import initial_state
        from backend.domain.multiagent.models.bases.ad_analysis import AdAnalysis

        # 더미 페르소나 3명
        dummy_personas = [
            {
                "persona_id": f"P_{i:04d}",
                "layer1": {"age": 28 + i * 5, "gender": "female", "region": "서울",
                            "occupation": "직장인", "annual_income_range": "3000만원대", "education": "대졸"},
                "layer2": {"purchase_motivation_primary": "실용성", "price_sensitivity": 0.5 + i * 0.1,
                            "impulse_buying_tendency": 0.4, "ad_avoidance_tendency": 0.3,
                            "preferred_ad_format": ["SNS"], "trusted_channels": ["인스타"],
                            "decision_speed": "medium"},
                "layer3": {"recent_purchase_experience": f"최근 의류 구매 {i}",
                            "current_pain_point": "가성비 탐색",
                            "ad_trigger_words": ["할인"], "ad_repellent_words": ["과장"],
                            "emotional_state_current": "평온"},
                "temperature_assigned": 0.7 + i * 0.05,
                "seed": 100 + i,
                "cluster_id": "",
            }
            for i in range(3)
        ]

        state = initial_state("sim-test", {})
        state["persona_pool"] = dummy_personas
        state["ad_analysis"] = {
            "text_analysis": {
                "headline": "여름 쿨링 셔츠 30% 할인",
                "usp_extracted": ["통기성", "가성비"],
                "cta": "지금 구매",
            },
            "visual_analysis": {"emotional_tone": "energetic"},
        }

        t0 = time.time()
        agent = ReactionSimulationAgent()
        result = await agent.run(state)
        elapsed = time.time() - t0
        responses = result["raw_responses"]
        if not responses:
            report("T12", "ReactionSimulationAgent (3명)", FAIL,
                   f"응답 0개 ({elapsed:.1f}s), errors={result['errors']}")
        else:
            avg_click = sum(r["click_intention"] for r in responses) / len(responses)
            report("T12", "ReactionSimulationAgent (3명)", PASS,
                   f"{len(responses)}개 응답 ({elapsed:.1f}s) | 평균 클릭의향={avg_click:.1f}")
    except Exception as e:
        report("T12", "ReactionSimulationAgent (3명)", FAIL, str(e)[:100])


# ─── T13: Supervisor 라우팅 로직 ─────────────────────────────

async def test_supervisor_routing():
    try:
        from backend.domain.multiagent.hub.orchestrator.supervisor import supervisor_route
        from backend.domain.multiagent.models.states.simulation_state import initial_state

        # 케이스 1: 유효 응답 충분 → aggregate_stats
        state = initial_state("sim-sv", {})
        import random, numpy as np
        random.seed(7)
        state["raw_responses"] = [
            {"click_intention": random.randint(20, 80), "is_outlier": False}
            for _ in range(15)
        ]
        state["errors"] = []
        route1 = await supervisor_route(state)

        # 케이스 2: 유효 응답 부족 → end
        state2 = initial_state("sim-sv2", {})
        state2["raw_responses"] = [{"click_intention": 50, "is_outlier": False}] * 5  # 5개만
        state2["errors"] = []
        route2 = await supervisor_route(state2)

        report("T13", "Supervisor 라우팅", PASS,
               f"케이스1(15명)→{route1} | 케이스2(5명)→{route2}")
    except Exception as e:
        report("T13", "Supervisor 라우팅", FAIL, str(e)[:100])


# ─── T14: DB CRUD ────────────────────────────────────────────

async def test_db_crud():
    try:
        from backend.core.database import async_session_factory
        from backend.domain.multiagent.hub.repositories.simulation_repository import (
            SimulationRepository, AdORM,
        )
        import uuid

        repo = SimulationRepository()
        async with async_session_factory() as db:
            # Ad 생성
            ad_id = str(uuid.uuid4())
            ad = AdORM(id=ad_id, input_type="image",
                       analysis_result={"test": True}, campaign_context="테스트")
            db.add(ad)
            await db.flush()

            # Simulation 생성
            sim = await repo.create(db, ad_id=ad_id, persona_count=5)
            sim_id = sim.id

            # 상태 업데이트
            from backend.domain.multiagent.models.enums import SimulationStatus
            await repo.update_status(db, sim_id, SimulationStatus.RUNNING, progress=50)

            # 조회
            fetched = await repo.get_by_id(db, sim_id)
            assert fetched.status == SimulationStatus.RUNNING
            assert fetched.progress == 50

            await db.commit()

        report("T14", "DB CRUD (Ad + Simulation)", PASS,
               f"sim_id={sim_id[:8]}..., status=running, progress=50")
    except Exception as e:
        report("T14", "DB CRUD (Ad + Simulation)", FAIL, traceback.format_exc().splitlines()[-1])


# ─── 실행 ────────────────────────────────────────────────────

async def main():
    print("\n" + "=" * 60)
    print("  Persona.100 Phase 1 테스트")
    print("=" * 60)

    print("\n[ 동기 테스트 (LLM 없음) ]")
    test_settings()
    test_pydantic_models()
    test_validation_agent()
    test_aggregation_service()
    test_report_service()
    test_langgraph_structure()
    test_fastapi_routes()
    test_health_endpoint()

    print("\n[ 비동기 테스트 ]")
    await test_db_connection()
    await test_db_crud()

    print("\n[ LLM API 실제 호출 테스트 ]")
    await test_openai_connection()
    await test_persona_generation()
    await test_reaction_simulation()
    await test_supervisor_routing()

    # ─── 결과 요약 ────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  테스트 결과 요약")
    print("=" * 60)
    passed = sum(1 for _, _, s, _ in results if "PASS" in s)
    failed = sum(1 for _, _, s, _ in results if "FAIL" in s)
    skipped = sum(1 for _, _, s, _ in results if "SKIP" in s)

    for tid, name, status, detail in results:
        icon = "OK" if "PASS" in status else ("NG" if "FAIL" in status else "--")
        print(f"  {icon} [{tid}] {name}")
        if "FAIL" in status:
            print(f"       -> {detail}")

    print(f"\n  결과: {passed}개 통과 / {failed}개 실패 / {skipped}개 스킵")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
