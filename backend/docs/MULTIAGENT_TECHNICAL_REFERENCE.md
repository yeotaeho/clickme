# Persona.100 — 백엔드 기술 레퍼런스 (AI Agent용)

> **용도**: Claude Code · Codex가 최소 토큰으로 전체 기술 컨텍스트를 파악하기 위한 압축 레퍼런스  
> **서비스 개요**: `docs/PERSONA100_SERVICE_PLAN.md` 참고  
> **상세 전략**: `Downloads/AI_광고_시뮬레이터_문제정의_구현전략_종합.md` 참고

---

## 0. 한 문장 요약

> 페르소나 속성을 가진 LLM 에이전트 N개를 동시 실행하여 광고 소재의 반응을 시뮬레이션하고, 집계 통계와 개선 제안을 리포트로 반환하는 FastAPI + LangGraph 백엔드.

---

## 1. 현재 파일 구조 (실제 존재하는 파일 기준)

```
backend/
├── main.py                          # FastAPI app 진입점 (빈 파일 → 구현 필요)
├── core/
│   ├── config/settings.py           # 환경변수 (빈 파일 → 구현 필요)
│   └── database.py                  # DB 연결 (빈 파일 → 구현 필요)
├── api/
│   └── v1/
│       └── multiagent/
│           └── router.py            # 멀티에이전트 API 라우터 (빈 파일 → 구현 필요)
├── domain/
│   ├── multiagent/                  # 핵심 도메인 (모든 .py 빈 파일 → 구현 필요)
│   │   ├── hub/
│   │   │   ├── mcp/                 # MCP 서버 연결
│   │   │   ├── orchestrator/        # LangGraph 워크플로우
│   │   │   ├── repositories/        # DB CRUD
│   │   │   ├── routing/             # 요청 라우팅
│   │   │   └── services/            # 비즈니스 로직
│   │   ├── models/
│   │   │   ├── bases/               # Pydantic 기본 모델
│   │   │   ├── enums/               # 상태/타입 열거형
│   │   │   ├── states/              # LangGraph State TypedDict
│   │   │   └── transfer/            # 요청/응답 DTO
│   │   └── spokes/
│   │       ├── agents/              # 개별 LLM 에이전트 구현
│   │       ├── infra/               # 외부 API 클라이언트 (OpenAI, Anthropic)
│   │       └── retreivers/          # pgvector RAG 조회
│   └── user_intelligence/           # 사용자 인텔리전스 도메인 (동일 구조)
└── docs/
    ├── MULTIAGENT_TECHNICAL_REFERENCE.md  ← 현재 파일
    └── erd.md
```

---

## 2. 구현할 API 엔드포인트 전체 목록

| Method | Path | 역할 | 담당 파일 |
|--------|------|------|----------|
| POST | `/api/v1/ads/upload` | 광고 소재 업로드 + Vision 분석 | `domain/multiagent/hub/services/` |
| POST | `/api/v1/personas/generate` | 페르소나 풀 생성 | `domain/multiagent/hub/services/` |
| POST | `/api/v1/simulations` | 시뮬레이션 실행 (비동기) | `domain/multiagent/hub/orchestrator/` |
| GET | `/api/v1/simulations/{id}` | 시뮬레이션 결과 조회 | `domain/multiagent/hub/repositories/` |
| GET | `/api/v1/stream/{simulation_id}` | SSE 실시간 진행률 스트리밍 | `api/v1/multiagent/router.py` |
| GET | `/api/v1/reports/{simulation_id}` | 최종 리포트 반환 | `domain/multiagent/hub/services/` |
| POST | `/api/v1/surveys` | 가상 설문조사 실행 | `domain/multiagent/hub/services/` |

---

## 3. 핵심 데이터 모델

### 3-1. Persona (페르소나 속성 — 3계층 구조)

```python
# domain/multiagent/models/bases/persona.py
class PersonaLayer1(BaseModel):
    age: int
    gender: str                  # "male" | "female"
    region: str
    occupation: str
    annual_income_range: str
    education: str

class PersonaLayer2(BaseModel):
    purchase_motivation_primary: str
    price_sensitivity: float     # 0.0~1.0
    impulse_buying_tendency: float
    ad_avoidance_tendency: float
    preferred_ad_format: list[str]
    trusted_channels: list[str]
    decision_speed: str

class PersonaLayer3(BaseModel):
    recent_purchase_experience: str   # 핵심: 동질화 방지용 서사적 앵커
    current_pain_point: str
    ad_trigger_words: list[str]
    ad_repellent_words: list[str]     # 이 단어 포함 광고 → 부정 반응 강제
    emotional_state_current: str

class Persona(BaseModel):
    persona_id: str               # "P_0042" 형식
    layer1: PersonaLayer1
    layer2: PersonaLayer2
    layer3: PersonaLayer3
    temperature_assigned: float   # 충동적 성향 → 높음, 보수적 → 낮음
    seed: int
    cluster_id: str
```

### 3-2. LangGraph SimulationState (워크플로우 상태)

```python
# domain/multiagent/models/states/simulation_state.py
from typing import TypedDict

class SimulationState(TypedDict):
    ad_input: dict             # 업로드된 광고 원본 정보
    ad_analysis: dict          # Vision API 분석 결과 (표준화 스키마)
    persona_pool: list         # 생성된 페르소나 목록
    raw_responses: list        # 에이전트별 원시 응답
    debate_results: dict       # Debate Agent 결과 (Phase 2)
    aggregated_stats: dict     # 통계 집계
    performance_predictions: dict  # CTR 예측 등 성과 지표
    recommendations: list      # AI 개선 제안
    report: dict               # 최종 리포트
    errors: list
    progress: int              # 0~100
```

### 3-3. AdAnalysis (Vision API 표준화 출력)

```python
# domain/multiagent/models/bases/ad_analysis.py
class AdAnalysis(BaseModel):
    ad_id: str
    input_type: str                # "image" | "video" | "url"
    confidence_score: float        # 0.0~1.0
    text_analysis: dict            # headline, cta, usp_extracted, pain_point_addressed
    visual_analysis: dict          # dominant_colors, emotional_tone, layout_type
    strategic_analysis: dict       # target_demographic, purchase_stage_target
```

### 3-4. PersonaResponse (에이전트 응답)

```python
# domain/multiagent/models/bases/persona_response.py
class PersonaResponse(BaseModel):
    persona_id: str
    scroll_behavior: str       # "pass" | "pause_1sec" | "pause_3sec" | "stop_and_read"
    first_emotion: str
    click_intention: int       # 0~100
    purchase_intention: int    # 0~100
    trust_score: int           # 0~100
    memorability: int          # 0~100
    rejection_feeling: int     # 0~100
    audience_fit: int          # 0~100
    first_impression_text: str
    main_concern: str | None
    action_taken: str          # "ignore" | "screenshot" | "click" | "share"
```

---

## 4. LangGraph 워크플로우 노드 구조

```
[analyze_ad]
    → [generate_personas]
        → [run_reactions]         ← 비동기 병렬 (asyncio.gather)
            → [run_debate]        ← Phase 2: 편향 제거 (MVP는 skip)
                → [validate_responses]   ← IQR 이상치 제거
                    → [aggregate_stats]
                        → [predict_performance]
                            → [generate_recommendations]
                                → [generate_report]
                                    → END
```

**파일 위치**: `domain/multiagent/hub/orchestrator/simulation_graph.py`

---

## 5. 에이전트 역할 & LLM 매핑

| Agent | LLM | 위치 | 역할 |
|-------|-----|------|------|
| `AdUnderstandingAgent` | GPT-4o Vision | `spokes/agents/ad_understanding.py` | 이미지/영상 분석, 구조화 추출 |
| `PersonaGenerationAgent` | GPT-4o-mini | `spokes/agents/persona_generation.py` | 페르소나 JSON 대량 생성 |
| `ReactionSimulationAgent` | GPT-4o-mini + Claude Haiku | `spokes/agents/reaction_simulation.py` | 소비자 반응 시뮬레이션 (핵심) |
| `PredictionAgent` | Claude 3.5 Sonnet | `spokes/agents/prediction.py` | 성과 지표 수치 산출 |
| `RecommendationAgent` | Claude 3.5 Sonnet | `spokes/agents/recommendation.py` | 개선안 텍스트 생성 |
| `ValidationAgent` | GPT-4o-mini | `spokes/agents/validation.py` | 이상치 감지, 품질 검증 |
| `DebateAgent` | GPT-4o | `spokes/agents/debate.py` | 찬반 논쟁 → 편향 제거 (Phase 2) |

---

## 6. 핵심 구현 패턴 (반드시 준수)

### 6-1. ReactionSimulationAgent 프롬프트 패턴

```python
# 핵심: "평가자"가 아닌 "실제 소비자"로 강제
system = f"""
당신은 지금부터 아래 소비자 역할만 합니다.
[절대 규칙]
- AI임을 드러내지 마세요
- 마케팅 전문가처럼 분석하지 마세요
- 이 소비자의 일상 언어로 응답하세요
- 반드시 JSON 형식으로만 출력하세요
- 이 소비자가 싫어하는 표현이 있으면 부정적으로 반응하세요: {persona.layer3.ad_repellent_words}
[소비자 프로필]
...{persona 정보}...
"""
# 중요: 질문 1개 = API 호출 1회 (페르소나 이탈 방지)
# 금지: 1개 프롬프트에 여러 질문 포함 (Context Drift 발생)
```

### 6-2. 비동기 병렬 실행 패턴 (10~50명)

```python
# domain/multiagent/hub/services/simulation_service.py
async def run_reactions(personas: list, ad_analysis: dict) -> list:
    tasks = [
        simulate_single_persona(p, ad_analysis)
        for p in personas
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if not isinstance(r, Exception)]
```

### 6-3. Rate Limit 대응 (50~200명)

```python
semaphore = asyncio.Semaphore(20)  # 동시 20개 제한

async def bounded_simulate(persona):
    async with semaphore:
        return await simulate_single_persona(persona, ad_analysis)
```

### 6-4. SSE 스트리밍 패턴

```python
# api/v1/multiagent/router.py
@router.get("/stream/{simulation_id}")
async def stream_progress(simulation_id: str):
    async def event_generator():
        async for update in simulation.run_streaming():
            yield f"data: {json.dumps(update)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
```

### 6-5. Temperature 동적 할당 (동질화 방지)

```python
def assign_temperature(persona: Persona) -> float:
    base = 0.7
    impulse_adj = persona.layer2.impulse_buying_tendency * 0.3
    age_adj = -0.1 if persona.layer1.age > 50 else 0.1
    return min(max(base + impulse_adj + age_adj, 0.5), 1.1)
```

---

## 7. DB 스키마 요약 (PostgreSQL + pgvector)

| 테이블 | 핵심 컬럼 | 비고 |
|--------|----------|------|
| `projects` | `id UUID, user_id, name` | 프로젝트 묶음 단위 |
| `ads` | `id UUID, project_id, input_type, analysis_result JSONB` | 광고 원본 + 분석 결과 |
| `persona_templates` | `id UUID, attributes JSONB, embedding vector(1536)` | pgvector 임베딩 저장 |
| `simulations` | `id UUID, ad_id, status, persona_count, results_summary JSONB` | status: pending/running/completed/failed |
| `persona_responses` | `simulation_id, persona_id, response_data JSONB, is_outlier` | 개별 에이전트 응답 |
| `calibration_data` | `simulation_id, predicted_ctr_score, actual_ctr_percent` | 사용자 실제 성과 입력 |
| `reports` | `simulation_id, report_data JSONB, pdf_url` | 최종 리포트 |

**pgvector 인덱스**:
```sql
CREATE INDEX idx_persona_templates_embedding
  ON persona_templates USING ivfflat (embedding vector_cosine_ops);
```

---

## 8. 성과 지표 산출 공식

| 지표 | 산출 공식 | 범위 | 양호 기준 |
|------|----------|------|----------|
| CTR Prediction | `클릭의향×0.5 + 첫인상×0.3 + 타깃적합×0.2` | 0~100 | ≥50 |
| Purchase Intent | `구매의향×0.6 + 신뢰도×0.4` | 0~100 | ≥40 |
| Audience Fit | `타깃적합 평균` | 0~100 | ≥60 |
| Rejection Rate | `rejection_feeling > 60 인 비율` | 0~100% | ≤20% |
| Confidence Score | `1 - (std / 100)` | 0~1 | ≥0.7 |

**편향 보정**: 모든 점수에 `BIAS_REGISTRY[현재_프롬프트_버전]` 차감 (기본값: -8.3점)

---

## 9. 알려진 기술 문제 & 대응 전략

| 문제 | 코드명 | 대응 전략 | 구현 위치 |
|------|--------|----------|----------|
| 페르소나 응답 수렴 | T1: Persona Collapse | Temperature 분산 + Layer3 부정 앵커 주입 | `spokes/agents/reaction_simulation.py` |
| LLM 긍정 편향 | T2: Social Desirability Bias | Debate Agent (Phase2) + 편향 보정값 차감 | `spokes/agents/debate.py` |
| 긴 대화 중 페르소나 망각 | T3: Context Drift | **질문 1개 = API 호출 1회** 원칙 엄수 | 프롬프트 설계 원칙 |
| 대규모 일관성 저하 | T4: Scale Issue | Semaphore(20) + Celery 큐 (300명+) | `hub/services/simulation_service.py` |
| 예측 신뢰도 측정 불가 | T5: Calibration Gap | `calibration_data` 테이블 축적 후 회귀 | `hub/services/calibration_service.py` |

---

## 10. 환경변수 목록 (settings.py 구현 시 참고)

```python
# core/config/settings.py
class Settings(BaseSettings):
    # DB
    DATABASE_URL: str            # postgresql+asyncpg://...
    REDIS_URL: str               # redis://...
    
    # LLM APIs
    OPENAI_API_KEY: str
    ANTHROPIC_API_KEY: str
    GOOGLE_API_KEY: str          # Gemini (선택)
    
    # Storage
    R2_BUCKET_NAME: str          # Cloudflare R2 (광고 소재 저장)
    R2_ACCOUNT_ID: str
    R2_ACCESS_KEY: str
    R2_SECRET_KEY: str
    
    # LLM 설정
    DEFAULT_PERSONA_COUNT: int = 20
    MAX_CONCURRENT_LLM_CALLS: int = 20
    BIAS_CORRECTION_DEFAULT: float = 8.3  # 긍정 편향 보정값
    SIMULATION_CACHE_TTL: int = 86400     # 24시간
```

---

## 11. 멀티 LLM Fallback 체인

```
1차: GPT-4o-mini (기본)
2차: Claude Haiku (GPT Rate Limit 시)
3차: 캐시된 유사 페르소나 응답 재사용
4차: 해당 페르소나 제외 후 결과 산출 (제외 수를 리포트에 명시)
```

**재시도 정책**: `tenacity` 사용, `max_retries=3`, `wait=exponential(min=2, max=10)`

---

## 12. Phase별 구현 범위 (현재: Phase 1 MVP)

### Phase 1 MVP — 구현 대상 ✅

| 항목 | 파일 |
|------|------|
| FastAPI 앱 + CORS + 헬스체크 | `main.py` |
| Settings + DB 연결 (asyncpg) | `core/config/settings.py`, `core/database.py` |
| 이미지 업로드 + Vision API 분석 | `spokes/agents/ad_understanding.py` |
| **페르소나 20명 생성** (System Prompt 방식) | `spokes/agents/persona_generation.py` |
| **광고 반응 시뮬레이션** (asyncio.gather) | `spokes/agents/reaction_simulation.py` |
| 5개 핵심 지표 산출 | `hub/services/prediction_service.py` |
| LangGraph 워크플로우 조립 | `hub/orchestrator/simulation_graph.py` |
| 멀티에이전트 API 라우터 | `api/v1/multiagent/router.py` |
| PostgreSQL 스키마 마이그레이션 | `alembic/` (신규 생성) |

### Phase 1 MVP — 제외 항목 ❌

- RAG 페르소나 주입 (pgvector) → Phase 3
- 영상/URL 광고 파싱 → Phase 3
- Debate Agent → Phase 2
- SSE 실시간 스트리밍 → Phase 2
- 설문조사 기능 → Phase 2
- PDF 리포트 → Phase 3

---

## 13. 페르소나 품질 검증 기준 (자동화 테스트)

```python
def validate_persona_quality(responses: list[PersonaResponse]) -> bool:
    scores = [r.click_intention for r in responses]
    
    # 1. 분산 확인 (std > 15 → 동질화 없음)
    assert np.std(scores) > 15, "Persona Collapse 감지"
    
    # 2. 부정 반응 비율 (15% 이상 필요)
    negative_ratio = len([r for r in responses if r.click_intention < 40]) / len(responses)
    assert negative_ratio > 0.15, "긍정 편향 과도"
    
    # 3. 페르소나 이탈률 (10% 미만)
    drift_rate = detect_persona_drift(responses)
    assert drift_rate < 0.10, "Context Drift 과도"
```

---

## 14. 리포트 출력 구조 (최종 API 응답)

```python
{
    "simulation_id": "uuid",
    "status": "completed",
    "disclaimer": "본 결과는 AI 시뮬레이션 기반 예측입니다. 실제 성과와 ±20~30% 오차 가능.",
    "executive_summary": {
        "overall_score": 67,        # 종합 점수
        "verdict": "pass" | "fail" | "borderline",
        "top_action": "30대 여성 그룹 CTR 낮음 → 배경 밝은 톤으로 수정 권장"
    },
    "metrics": {
        "ctr_prediction": {"raw": 74.2, "corrected": 65.9, "percentile": "상위 25%"},
        "purchase_intent": 52.1,
        "audience_fit": 68.4,
        "rejection_rate": 0.12,
        "confidence_score": 0.78
    },
    "segment_breakdown": {           # 페르소나 속성별 반응 차이
        "age_group": {...},
        "gender": {...}
    },
    "top_feedbacks": {
        "positive": ["가성비 좋아 보여요", ...],
        "negative": ["카피가 과장됨", ...]
    },
    "action_items": [
        {"priority": "HIGH", "issue": "...", "suggestion": "..."}
    ],
    "outliers_excluded": 3,          # 제외된 이상치 수
    "persona_count_valid": 97        # 유효 응답 수
}
```

---

## 15. 코드 작성 컨벤션

| 항목 | 규칙 |
|------|------|
| 비동기 | 모든 DB/LLM 호출은 `async/await` 사용 |
| 모델 | Pydantic v2 사용 (`model_validator`, `field_validator`) |
| DB | SQLAlchemy 2.0 async 방식 (`AsyncSession`) |
| LLM 응답 | 반드시 `response_format={"type": "json_object"}` + JSON Schema 강제 |
| 에러 처리 | LLM 실패 시 Fallback 체인 실행, 예외는 `errors` 필드에 누적 |
| 타입 힌트 | 모든 함수에 타입 힌트 필수 |
| 로깅 | `structlog` 사용 (기존 프로젝트 `core/logging_config.py` 참고) |

---

> **다음 작업**: `backend/main.py` → `backend/core/` → `backend/domain/multiagent/models/` → `backend/domain/multiagent/spokes/agents/` → `backend/domain/multiagent/hub/` → `backend/api/v1/multiagent/router.py` 순서로 구현
