# Persona.100 — Claude Code 컨텍스트 레퍼런스

## 프로젝트 한 문장 요약

> 100개 LLM 에이전트에게 광고 소재를 사전 평가시켜 실제 매체비 소진 전에 성과를 예측하는 B2B SaaS 플랫폼 (FastAPI + LangGraph 백엔드)

---

## 저장소 구조

```
roadmapaa/
├── backend/                          # 메인 Python 백엔드
│   ├── main.py                       # FastAPI 진입점 (현재 빈 파일)
│   ├── core/
│   │   ├── config/settings.py        # 환경변수 (빈 파일)
│   │   └── database.py               # PostgreSQL 연결 (빈 파일)
│   ├── api/v1/multiagent/router.py   # REST API 라우터 (빈 파일)
│   ├── domain/
│   │   ├── multiagent/               # 핵심 도메인 — 광고 시뮬레이션
│   │   │   ├── hub/
│   │   │   │   ├── mcp/              # MCP 서버 연결
│   │   │   │   ├── orchestrator/     # LangGraph 워크플로우
│   │   │   │   ├── repositories/     # DB CRUD
│   │   │   │   ├── routing/          # 요청 라우팅
│   │   │   │   └── services/         # 비즈니스 로직
│   │   │   ├── models/
│   │   │   │   ├── bases/            # Pydantic 기본 모델
│   │   │   │   ├── enums/            # 상태/타입 열거형
│   │   │   │   ├── states/           # LangGraph State TypedDict
│   │   │   │   └── transfer/         # 요청/응답 DTO
│   │   │   └── spokes/
│   │   │       ├── agents/           # 개별 LLM 에이전트
│   │   │       ├── infra/            # 외부 API 클라이언트
│   │   │       └── retreivers/       # pgvector RAG (오탈자 유지)
│   │   └── user_intelligence/        # 사용자 인텔리전스 도메인 (동일 구조)
│   └── docs/
│       ├── MULTIAGENT_TECHNICAL_REFERENCE.md   # 핵심 기술 레퍼런스
│       └── PHASE2_EXPANSION_REFERENCE.md        # Phase 2+ 확장 명세
└── docs/
    └── PERSONA100_SERVICE_PLAN.md    # 서비스 기획서 (비즈니스 컨텍스트)
```

**현재 상태**: Phase 1 MVP — 모든 `.py` 파일이 빈 파일이며 구현 대기 중.

---

## 기술 스택

| 레이어 | 기술 |
|--------|------|
| API 서버 | FastAPI 0.115+, Uvicorn, Pydantic v2 |
| AI 오케스트레이션 | LangGraph 0.0.40+, LangChain 0.1+ |
| LLM | OpenAI GPT-4o / GPT-4o-mini (기본), Claude Haiku (폴백), Groq |
| Vector DB | PostgreSQL + pgvector (임베딩), ChromaDB |
| DB ORM | SQLAlchemy 2.0 Async, Alembic 마이그레이션 |
| 캐시 | Upstash Redis |
| 스토리지 | Cloudflare R2 (광고 소재) |
| 문서 파싱 | LLama-Parse, PyMuPDF, Unstructured |
| 크롤링 | Playwright, BeautifulSoup4, aiohttp |
| 로깅 | Loguru (structlog 준용) |

---

## 구현 순서 (Phase 1 MVP)

아래 순서대로 구현한다. 파일이 없으면 신규 생성:

1. `backend/core/config/settings.py` — Pydantic `BaseSettings`
2. `backend/core/database.py` — asyncpg AsyncSession
3. `backend/domain/multiagent/models/` — Pydantic 모델 (bases → enums → states → transfer)
4. `backend/domain/multiagent/spokes/agents/` — 개별 LLM 에이전트
5. `backend/domain/multiagent/hub/` — 서비스·오케스트레이터·저장소
6. `backend/api/v1/multiagent/router.py` — API 라우터
7. `backend/main.py` — FastAPI 앱 조립
8. `alembic/` — DB 마이그레이션 (신규 생성)

### Phase 1 MVP 범위

**구현 대상**:
- FastAPI 앱 + CORS + 헬스체크
- Settings + DB 연결 (asyncpg)
- 이미지 업로드 + Vision API 분석 (`AdUnderstandingAgent`)
- 페르소나 20명 생성 (`PersonaGenerationAgent`)
- 광고 반응 시뮬레이션 (`ReactionSimulationAgent`, asyncio.gather)
- 5개 핵심 지표 산출 (`PredictionAgent`)
- LangGraph 워크플로우 조립 (`simulation_graph.py`)
- API 라우터 + PostgreSQL 스키마

**MVP 제외 (Phase 2+)**:
- SSE 실시간 스트리밍, Debate Agent, RAG 페르소나 주입
- 설문조사, 영상/URL 광고 파싱, PDF 리포트

---

## API 엔드포인트 전체 목록

| Method | Path | 역할 |
|--------|------|------|
| POST | `/api/v1/ads/upload` | 광고 소재 업로드 + Vision 분석 |
| POST | `/api/v1/personas/generate` | 페르소나 풀 생성 |
| POST | `/api/v1/simulations` | 시뮬레이션 실행 (비동기) |
| GET | `/api/v1/simulations/{id}` | 결과 조회 |
| GET | `/api/v1/stream/{simulation_id}` | SSE 진행률 스트리밍 (Phase 2) |
| GET | `/api/v1/reports/{simulation_id}` | 최종 리포트 |
| POST | `/api/v1/surveys` | 가상 설문조사 실행 (Phase 2) |

---

## 핵심 데이터 모델 요약

### Persona (3계층)
```python
Persona.layer1  # 인구통계: age, gender, region, occupation, annual_income_range, education
Persona.layer2  # 소비 성향: price_sensitivity, impulse_buying_tendency, ad_avoidance_tendency
Persona.layer3  # 내러티브: recent_purchase_experience, current_pain_point, ad_repellent_words
```
- `persona_id`: "P_0042" 형식
- `temperature_assigned`: 충동성 기반 동적 할당 (0.5~1.1)
- `seed`: 재현성 확보용

### SimulationState (LangGraph TypedDict)
```python
class SimulationState(TypedDict):
    ad_input, ad_analysis, persona_pool, raw_responses,
    debate_results, aggregated_stats, performance_predictions,
    recommendations, report, errors, progress  # 0~100
```

### PersonaResponse (에이전트 응답)
```python
# 핵심 필드
scroll_behavior: "pass" | "pause_1sec" | "pause_3sec" | "stop_and_read"
click_intention: int      # 0~100
purchase_intention: int   # 0~100
action_taken: "ignore" | "screenshot" | "click" | "share"
```

---

## LangGraph 워크플로우 노드 순서

```
analyze_ad → generate_personas → run_reactions (asyncio.gather 병렬)
  → validate_responses (IQR 이상치 제거)
    → aggregate_stats → predict_performance → generate_recommendations
      → generate_report → END
```

**파일**: `domain/multiagent/hub/orchestrator/simulation_graph.py`

---

## 에이전트 역할 & LLM 매핑

| Agent | LLM | 파일 위치 |
|-------|-----|----------|
| `AdUnderstandingAgent` | GPT-4o Vision | `spokes/agents/ad_understanding.py` |
| `PersonaGenerationAgent` | GPT-4o-mini | `spokes/agents/persona_generation.py` |
| `ReactionSimulationAgent` | GPT-4o-mini + Claude Haiku (폴백) | `spokes/agents/reaction_simulation.py` |
| `PredictionAgent` | Claude 3.5 Sonnet | `spokes/agents/prediction.py` |
| `RecommendationAgent` | Claude 3.5 Sonnet | `spokes/agents/recommendation.py` |
| `ValidationAgent` | GPT-4o-mini | `spokes/agents/validation.py` |
| `DebateAgent` | GPT-4o | `spokes/agents/debate.py` (Phase 2) |

---

## 코드 컨벤션 (반드시 준수)

| 항목 | 규칙 |
|------|------|
| 비동기 | 모든 DB/LLM 호출은 `async/await` |
| Pydantic | v2 사용 (`model_validator`, `field_validator`) |
| DB | SQLAlchemy 2.0 async (`AsyncSession`) |
| LLM 응답 | `response_format={"type": "json_object"}` + JSON Schema 강제 |
| 에러 처리 | LLM 실패 → Fallback 체인 → 예외를 `errors` 필드에 누적 |
| 타입 힌트 | 모든 함수에 필수 |
| 로깅 | `loguru` (`structlog` 스타일) |
| 재시도 | `tenacity`, `max_retries=3`, `wait=exponential(min=2, max=10)` |

---

## 핵심 구현 패턴

### ReactionSimulationAgent 프롬프트 (동질화 방지)
```python
system = f"""
당신은 지금부터 아래 소비자 역할만 합니다.
[절대 규칙]
- AI임을 드러내지 마세요
- 마케팅 전문가처럼 분석하지 마세요
- 이 소비자의 일상 언어로 응답하세요
- 반드시 JSON 형식으로만 출력하세요
- 싫어하는 표현이 있으면 부정적으로 반응하세요: {persona.layer3.ad_repellent_words}
"""
# 중요: 질문 1개 = API 호출 1회 (Context Drift 방지)
```

### 비동기 병렬 실행 (10~50명)
```python
results = await asyncio.gather(*[simulate_single_persona(p, ad) for p in personas], return_exceptions=True)
```

### Rate Limit 대응 (50~200명)
```python
semaphore = asyncio.Semaphore(20)  # MAX_CONCURRENT_LLM_CALLS = 20
```

### Temperature 동적 할당
```python
def assign_temperature(persona: Persona) -> float:
    base = 0.7
    impulse_adj = persona.layer2.impulse_buying_tendency * 0.3
    age_adj = -0.1 if persona.layer1.age > 50 else 0.1
    return min(max(base + impulse_adj + age_adj, 0.5), 1.1)
```

### 멀티 LLM Fallback 체인
```
1차: GPT-4o-mini → 2차: Claude Haiku → 3차: 캐시된 유사 페르소나 재사용 → 4차: 해당 페르소나 제외
```

---

## 성과 지표 산출 공식

| 지표 | 공식 | 양호 기준 |
|------|------|----------|
| CTR Prediction | `클릭의향×0.5 + 첫인상×0.3 + 타깃적합×0.2` | ≥50 |
| Purchase Intent | `구매의향×0.6 + 신뢰도×0.4` | ≥40 |
| Rejection Rate | `rejection_feeling > 60 비율` | ≤20% |
| Confidence Score | `1 - (std / 100)` | ≥0.7 |

**편향 보정**: 모든 점수에서 `BIAS_CORRECTION_DEFAULT = 8.3` 차감 (LLM 긍정 편향 보정)

---

## 알려진 기술 문제 & 대응

| 코드명 | 문제 | 대응 |
|--------|------|------|
| T1: Persona Collapse | 페르소나 응답 수렴 | Temperature 분산 + Layer3 부정 앵커 |
| T2: Social Desirability Bias | LLM 긍정 편향 | Debate Agent (Phase 2) + 8.3점 차감 |
| T3: Context Drift | 긴 대화 중 페르소나 망각 | **질문 1개 = API 호출 1회** 원칙 |
| T4: Scale Issue | 대규모 일관성 저하 | Semaphore(20) + Celery 큐 (300명+) |
| T5: Calibration Gap | 예측 신뢰도 미측정 | `calibration_data` 테이블 축적 후 회귀 |

---

## DB 스키마 요약 (PostgreSQL + pgvector)

| 테이블 | 핵심 컬럼 |
|--------|----------|
| `projects` | `id UUID, user_id, name` |
| `ads` | `id UUID, project_id, input_type, analysis_result JSONB` |
| `persona_templates` | `id UUID, attributes JSONB, embedding vector(1536)` |
| `simulations` | `id UUID, ad_id, status(pending/running/completed/failed), results_summary JSONB` |
| `persona_responses` | `simulation_id, persona_id, response_data JSONB, is_outlier` |
| `calibration_data` | `simulation_id, predicted_ctr_score, actual_ctr_percent` |
| `reports` | `simulation_id, report_data JSONB, pdf_url` |

```sql
-- pgvector 인덱스 (persona_templates)
CREATE INDEX ON persona_templates USING ivfflat (embedding vector_cosine_ops);
```

---

## 환경변수 (settings.py 구현 시 참고)

```python
class Settings(BaseSettings):
    DATABASE_URL: str           # postgresql+asyncpg://... (Neon)
    REDIS_URL: str              # Upstash Redis
    OPENAI_API_KEY: str
    ANTHROPIC_API_KEY: str
    GOOGLE_API_KEY: str         # Gemini (선택)
    R2_BUCKET_NAME: str         # Cloudflare R2
    R2_ACCOUNT_ID: str
    R2_ACCESS_KEY: str
    R2_SECRET_KEY: str
    DEFAULT_PERSONA_COUNT: int = 20
    MAX_CONCURRENT_LLM_CALLS: int = 20
    BIAS_CORRECTION_DEFAULT: float = 8.3
    SIMULATION_CACHE_TTL: int = 86400
```

OAuth 관련 (`KAKAO_CLIENT_ID`, `NAVER_CLIENT_ID`, `GOOGLE_CLIENT_ID` 등)은 `.env` 파일에 존재.

---

## Phase 2+ 확장 기능 (구현 우선순위 순)

| Phase | 기능 | 핵심 신기술 |
|-------|------|-----------|
| 2.1 | 소셜 바이럴 시뮬레이터 | LangGraph 멀티에이전트 메시지 패싱, ReAct |
| 2.2 | 경쟁사 레퍼런스 비교 | pgvector 유사도 검색, Meta Ad Library API |
| 2.3 | ESG & 컴플라이언스 검증 | RAG + 규정 문서 Vector DB |
| 2.4 | 매체별 네이티브 UX 뷰어 | 프롬프트 컨텍스트 확장 (기존 파일 수정) |

상세 명세: `backend/docs/PHASE2_EXPANSION_REFERENCE.md`

---

## 비즈니스 컨텍스트 (개발 의사결정 참고)

- **타깃**: 마케팅 대행사, 인하우스 마케터, 스타트업 PMM
- **핵심 가치**: 실제 매체비 소진 전 5~10분 만에 100명 규모 가상 검증
- **Pricing**: Starter(₩49K/월, 페르소나 50명) / Professional(₩199K/월, 100명) / Enterprise(₩990K+/월, 무제한)
- **광고 자동 제작 기능은 현재 범위 제외** (마케팅 도메인 지식 의존도 높음)

서비스 기획 전체: `docs/PERSONA100_SERVICE_PLAN.md`

---

## 주의사항

- `spokes/retreivers/` 폴더명은 오탈자(retrievers → retreivers)이나 **기존 구조 유지** — 변경 금지
- Phase 1 SSE는 구현하지 않음; `StreamingResponse` 코드는 Phase 2에서 추가
- 페르소나 품질 검증: `std(click_intention) > 15`, 부정 반응 비율 > 15%, Context Drift < 10%
- LLM 응답은 항상 JSON 강제(`response_format`) — 자유 텍스트 파싱 금지
