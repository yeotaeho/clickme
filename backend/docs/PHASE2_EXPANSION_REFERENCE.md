# Persona.100 — Phase 2+ 확장 기능 기술 레퍼런스 (AI Agent용)

> **전제 조건**: `backend/docs/MULTIAGENT_TECHNICAL_REFERENCE.md` 숙지 필수  
> **현재 상태**: Phase 1 MVP 구현 후 착수할 확장 기능 명세  
> **우선순위**: Phase 2.1 → 2.2 → 2.3 순서로 구현

---

## 0. Phase 2 기능 전체 요약

| Phase | 기능명 | 핵심 가치 | 타깃 고객 확장 | 주요 신규 기술 |
|-------|--------|----------|--------------|--------------|
| **2.1** | 소셜 바이럴 시뮬레이터 | 에이전트 간 상호작용으로 바이럴 확산 예측 | 콘텐츠 마케터, 바이럴 대행사 | LangGraph 멀티에이전트 메시지 패싱, ReAct |
| **2.2** | 경쟁사 레퍼런스 비교 | 내 광고의 시장 내 포지셔닝 파악 | 전략 기획자, PM, 브랜드 매니저 | pgvector 유사도 검색, 크롤링 파이프라인 |
| **2.3** | ESG & 컴플라이언스 검증 | 광고 배포 전 법적/브랜드 리스크 차단 | 대기업 인하우스, PR/ESG 부서 | RAG + 규정 문서 Vector DB |
| **2.4** | 매체별 네이티브 UX 뷰어 | 플랫폼 맥락 주입으로 매체 최적화 인사이트 | 퍼포먼스 마케터, 미디어 바이어 | 컨텍스트 프롬프트 확장 |

---

## Phase 2.1 — 소셜 바이럴 시뮬레이터

### 개념

```
Phase 1: 에이전트 100명이 광고를 "독립적으로" 평가
                 ↓
Phase 2.1: 에이전트들이 "서로의 반응을 보고" 재반응
           (인스타 댓글창 시뮬레이션)
```

**핵심 추가 가치**: 단순 클릭률 예측이 아닌 바이럴 확산 가능성(네트워크 효과) 예측

---

### 신규 파일 구조

```
domain/multiagent/
├── hub/
│   ├── orchestrator/
│   │   └── viral_graph.py          # Phase 1 simulation_graph.py와 별도 그래프
│   └── services/
│       └── viral_simulation_service.py
└── spokes/
    └── agents/
        ├── viral_reaction_agent.py  # 타인 댓글을 읽고 반응하는 에이전트
        └── viral_summary_agent.py  # 확산 패턴 네트워크 분석 요약
```

---

### LangGraph 멀티에이전트 메시지 패싱 설계

```python
# domain/multiagent/models/states/viral_state.py
class ViralSimulationState(TypedDict):
    ad_analysis: dict
    persona_pool: list
    comment_thread: list[CommentNode]  # 댓글 트리 (순서 있는 리스트)
    interaction_graph: dict            # 노드(에이전트) + 엣지(반응 관계)
    viral_metrics: dict
    network_visualization: dict        # 프론트 시각화용 노드-엣지 데이터

class CommentNode(TypedDict):
    comment_id: str
    persona_id: str
    content: str
    sentiment: str         # "positive" | "negative" | "neutral"
    parent_comment_id: str | None   # 대댓글 구조
    triggered_by: str | None        # 어떤 댓글에 의해 반응했는지
    action: str            # "comment" | "share" | "ignore" | "report"
```

---

### ReAct 패턴 프롬프트 (핵심 구현)

```python
# domain/multiagent/spokes/agents/viral_reaction_agent.py
def build_viral_reaction_prompt(
    persona: Persona,
    ad_analysis: dict,
    existing_comments: list[CommentNode],   # 이미 달린 댓글 목록
    round_number: int
) -> list:
    """
    ReAct 패턴: Observe → Reason → Act
    에이전트가 타인 댓글을 보고 반응 여부를 결정
    """
    comments_text = "\n".join([
        f"- {c['persona_id']} ({c['sentiment']}): {c['content']}"
        for c in existing_comments[-10:]   # 최근 10개만 (토큰 절감)
    ])

    system = f"""
당신은 {persona.layer1.age}세 {persona.layer1.gender}입니다.
인스타그램 피드를 보다가 광고와 그 아래 댓글들을 보고 있습니다.

[광고 내용 요약]
{ad_analysis['text_analysis']['headline']}
소구점: {ad_analysis['text_analysis']['usp_extracted']}

[현재 달린 댓글들]
{comments_text}

[절대 규칙]
- 분석가처럼 판단하지 마세요. 실제 SNS 사용자처럼 반응하세요.
- 댓글에 동조 또는 반박할 수 있습니다.
- 무관심하면 아무것도 하지 않아도 됩니다.
- 반드시 JSON으로만 출력하세요.
"""
    user = """
지금 이 광고와 댓글을 보고 당신의 행동을 결정하세요.

{
  "action": "ignore | comment | share | report",
  "comment_content": "댓글 내용 (action이 comment일 때만, 없으면 null)",
  "replying_to_comment_id": "대댓글 대상 ID (없으면 null)",
  "share_reason": "공유 이유 (action이 share일 때만, 없으면 null)",
  "triggered_emotion": "댓글/광고를 보고 느낀 감정 1단어"
}
"""
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
```

---

### 바이럴 워크플로우 실행 구조

```python
# domain/multiagent/hub/orchestrator/viral_graph.py
"""
라운드 방식으로 에이전트들이 순차적으로 반응하는 구조

Round 0: 광고 최초 공개 (댓글 없음)
  → 초기 반응자 20명 (충동적 성향 상위 20%) 먼저 반응
  
Round 1: Round 0의 댓글을 보고 나머지 에이전트들이 반응
  → 긍정 댓글이 많으면 → 더 많은 에이전트가 관심
  → 부정 댓글이 많으면 → 회의적 에이전트들 반박
  
Round 2: 논쟁이 발생한 경우 추가 반응
  → 최대 3라운드 (비용 제어)
"""

VIRAL_ROUNDS = 3
INITIAL_REACTOR_RATIO = 0.2  # 1라운드에 반응하는 비율 (충동성 기준 상위 20%)
```

---

### 바이럴 지표 산출

```python
class ViralMetrics(BaseModel):
    virality_score: int          # 0~100 (공유 행동 선택 비율 × 가중치)
    controversy_score: int       # 0~100 (부정 댓글 비율 × 논쟁 깊이)
    organic_reach_multiplier: float  # 예: 1.0 = 원본 도달, 2.3 = 2.3배 확산 예상
    comment_cascade_depth: int   # 최대 대댓글 깊이 (바이럴 강도 지표)
    dominant_narrative: str      # "긍정 바이럴" | "논쟁형 화제" | "조용한 무관심"
    key_trigger_comment: str     # 가장 많은 반응을 유발한 댓글
    network_graph: dict          # 프론트 시각화용 노드/엣지 데이터
```

---

### Phase 1 API에 추가되는 엔드포인트

```
POST /api/v1/simulations/viral    # 바이럴 시뮬레이션 실행
GET  /api/v1/simulations/{id}/network  # 네트워크 그래프 데이터 반환
```

---

## Phase 2.2 — 경쟁사 레퍼런스 비교 분석기

### 개념

```
내 광고 시안 업로드
        ↓
Vector DB에서 동일 카테고리 경쟁사 광고 임베딩 검색 (cosine similarity)
        ↓
유사도 높은 경쟁사 광고 Top 5 추출
        ↓
LLM이 포지셔닝 차별성 & 카니발리제이션 위험 분석
```

---

### 신규 파일 구조

```
domain/multiagent/
├── hub/
│   ├── services/
│   │   └── competitor_analysis_service.py
│   └── repositories/
│       └── competitor_repository.py     # 경쟁사 광고 Vector DB CRUD
└── spokes/
    ├── agents/
    │   └── competitor_analysis_agent.py
    └── retreivers/                      # 기존 폴더명 유지 (typo이나 그대로)
        └── competitor_retriever.py      # pgvector 유사도 검색
```

---

### 경쟁사 광고 DB 스키마

```sql
-- 경쟁사 광고 레퍼런스 DB
CREATE TABLE competitor_ads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_name VARCHAR(100) NOT NULL,
    industry VARCHAR(50) NOT NULL,        -- "fashion" | "food" | "tech" | ...
    platform VARCHAR(50),                 -- "instagram" | "youtube" | "banner"
    headline TEXT,
    visual_summary TEXT,
    usp_keywords TEXT[],
    emotional_tone VARCHAR(50),
    performance_tier VARCHAR(20),         -- "hit" | "normal" | "failed" (공개 데이터 기반)
    source_url TEXT,
    image_embedding vector(1536),         -- CLIP 또는 GPT-4o Vision 임베딩
    text_embedding vector(1536),          -- text-embedding-3-small
    collected_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_competitor_ads_industry
    ON competitor_ads(industry);
CREATE INDEX idx_competitor_ads_image_emb
    ON competitor_ads USING ivfflat (image_embedding vector_cosine_ops);
CREATE INDEX idx_competitor_ads_text_emb
    ON competitor_ads USING ivfflat (text_embedding vector_cosine_ops);
```

---

### 데이터 수집 파이프라인

```python
# domain/multiagent/spokes/infra/competitor_crawler.py
"""
수집 대상:
  1. Meta Ad Library API (공식 API, 무료)
     → https://www.facebook.com/ads/library/api/
  2. Google Ads Transparency Center (크롤링)
  3. 국내: 네이버 광고 심의 공개 DB (공공데이터)

수집 주기: 주 1회 Celery Beat 스케줄러
저장: S3/R2 (원본) + PostgreSQL + pgvector (임베딩)
"""

async def collect_meta_ad_library(
    search_terms: list[str],
    country: str = "KR",
    limit: int = 100
) -> list[CompetitorAd]:
    # Meta Ad Library API 호출
    # 광고 이미지 → Vision API로 임베딩 생성
    # pgvector에 저장
    ...
```

---

### 유사도 검색 & 포지셔닝 분석 프롬프트

```python
# domain/multiagent/spokes/retreivers/competitor_retriever.py
async def find_similar_competitor_ads(
    my_ad_analysis: dict,
    industry: str,
    top_k: int = 5
) -> list[CompetitorAd]:
    # 내 광고의 텍스트 임베딩 생성
    my_text_emb = await embed_text(my_ad_analysis['text_analysis']['headline'])
    
    # pgvector cosine similarity 검색
    similar_ads = await db.execute(
        """
        SELECT *, 1 - (text_embedding <=> $1) AS similarity
        FROM competitor_ads
        WHERE industry = $2
        ORDER BY text_embedding <=> $1
        LIMIT $3
        """,
        my_text_emb, industry, top_k
    )
    return similar_ads

# domain/multiagent/spokes/agents/competitor_analysis_agent.py
def build_competitor_analysis_prompt(
    my_ad: dict,
    competitor_ads: list[dict]
) -> list:
    """
    출력: 차별화 점수, 카니발리제이션 위험, 포지셔닝 갭
    """
    ...
```

---

### 최종 출력 구조

```python
class CompetitorAnalysisResult(BaseModel):
    differentiation_score: int     # 0~100 (경쟁사와 얼마나 다른가)
    cannibalization_risk: str       # "low" | "medium" | "high"
    similar_competitor_ads: list   # Top 5 유사 광고 (브랜드명, 유사도 점수)
    positioning_gap: str           # "빈 포지션 발견" | "레드오션 포지션"
    tone_overlap_warning: str | None  # "나이키 2024 캠페인과 85% 유사"
    recommended_differentiation: str  # "경쟁사 대비 차별화할 수 있는 방향 1가지"
```

---

## Phase 2.3 — ESG & 컴플라이언스 리스크 검증 에이전트

### 개념

```
광고 카피 입력
    ↓
RAG: 광고 심의 규정 + IFRS S1/S2 + GRI 가이드라인 Vector DB 검색
    ↓
ComplianceAgent가 위반 여부 판정
    ↓
리스크 레벨 + 위반 조항 + 수정 제안 출력
```

**포지셔닝**: 성과 예측 에이전트(Phase 1)와 별개로 "배포 전 게이트키퍼" 역할

---

### 신규 파일 구조

```
domain/multiagent/
├── hub/
│   └── services/
│       └── compliance_service.py
└── spokes/
    ├── agents/
    │   └── compliance_agent.py      # 법무/ESG 특화 에이전트
    └── retreivers/
        └── compliance_retriever.py  # 규정 문서 RAG 조회
```

---

### 규정 문서 Vector DB 스키마

```sql
CREATE TABLE compliance_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_type VARCHAR(50) NOT NULL,   -- "ad_regulation" | "esg_guideline" | "consumer_protection"
    doc_name VARCHAR(200) NOT NULL,  -- "공정거래위원회 표시광고법 2024"
    jurisdiction VARCHAR(20),        -- "KR" | "EU" | "US" | "global"
    article_number VARCHAR(50),      -- "제3조 제2항"
    content TEXT NOT NULL,           -- 조항 원문
    keywords TEXT[],                 -- ["친환경", "그린워싱", "과장광고"]
    risk_level VARCHAR(20),          -- "critical" | "warning" | "info"
    embedding vector(1536),
    effective_date DATE,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 우선 수집 대상 문서 목록
-- 1. 공정거래위원회: 표시광고의 공정화에 관한 법률
-- 2. 한국광고자율심의기구(KARA): 광고자율심의규정
-- 3. GRI Standards (그린워싱 관련 S-분류)
-- 4. IFRS S1, S2 (지속가능성 공시 기준)
-- 5. 소비자기본법 관련 고시
```

---

### ComplianceAgent 구현 패턴

```python
# domain/multiagent/spokes/agents/compliance_agent.py
async def run_compliance_check(
    ad_analysis: dict,
    jurisdiction: str = "KR"
) -> ComplianceResult:
    """
    특화 에이전트: 일반 소비자 에이전트와 완전히 분리
    역할: 법무/컴플라이언스 전문가 페르소나
    LLM: Claude 3.5 Sonnet (긴 규정 문서 처리에 강함)
    """
    # 1. RAG: 광고 카피 관련 규정 조항 검색
    relevant_regulations = await compliance_retriever.search(
        query=ad_analysis['text_analysis']['headline'],
        doc_types=["ad_regulation", "esg_guideline"],
        jurisdiction=jurisdiction,
        top_k=8
    )

    # 2. 위반 여부 판정 프롬프트
    system = """
당신은 광고 법규 및 ESG 가이드라인 전문 컴플라이언스 담당자입니다.
광고 소재와 관련 규정을 검토하여 위반 여부와 리스크를 판정합니다.
반드시 근거 조항을 명시하고 JSON으로만 출력하세요.
"""
    user = f"""
[검토 대상 광고]
헤드라인: {ad_analysis['text_analysis']['headline']}
주요 카피: {ad_analysis['text_analysis'].get('body_copy', [])}
환경 관련 표현: {[k for k in ad_analysis['text_analysis'].get('emotional_keywords', []) 
                  if any(w in k for w in ['친환경', '에코', '그린', '탄소', '지속가능'])]}

[관련 규정 조항]
{format_regulations(relevant_regulations)}

[판정 출력 형식]
{{
  "overall_risk_level": "safe | warning | critical",
  "violations": [
    {{
      "regulation_name": "조항명",
      "article": "조문 번호",
      "violated_copy": "위반 소지 카피",
      "reason": "위반 이유",
      "severity": "critical | warning | info",
      "suggested_fix": "수정 제안"
    }}
  ],
  "greenwashing_risk": "none | low | medium | high",
  "greenwashing_detail": "그린워싱 위험 설명 (없으면 null)",
  "safe_to_proceed": true | false
}}
"""
    ...
```

---

### 기존 시뮬레이션 파이프라인과 통합 지점

```python
# domain/multiagent/hub/orchestrator/simulation_graph.py 수정
# Phase 1 그래프에 컴플라이언스 노드 추가 (선택적 실행)

graph.add_node("compliance_check", compliance_check_node)
graph.add_conditional_edges(
    "analyze_ad",
    lambda state: "compliance_check" if state.get("run_compliance") else "generate_personas",
    {
        "compliance_check": "compliance_check",
        "generate_personas": "generate_personas"
    }
)
graph.add_edge("compliance_check", "generate_personas")

# 컴플라이언스 위반 시 조기 중단 옵션
def compliance_check_node(state: SimulationState) -> SimulationState:
    result = run_compliance_check(state['ad_analysis'])
    if result.overall_risk_level == "critical" and state.get("block_on_critical"):
        state['errors'].append({"type": "compliance_critical", "detail": result})
        return {**state, "report": generate_compliance_only_report(result)}
    state['compliance_result'] = result
    return state
```

---

### 컴플라이언스 전용 API 엔드포인트 추가

```
POST /api/v1/compliance/check      # 광고 소재 단독 컴플라이언스 검토
GET  /api/v1/compliance/regulations # 지원 규정 목록 조회
```

---

## Phase 2.4 — 매체별 네이티브 UX 컨텍스트 주입

### 개념 및 구현 방식

Phase 1 대비 변경 범위가 가장 작음 — **프롬프트 확장**으로 구현 가능

```python
# 기존 Phase 1 ReactionSimulationAgent 프롬프트에 매체 컨텍스트 추가

PLATFORM_CONTEXTS = {
    "instagram_feed": {
        "context": "인스타그램 피드 스크롤 중 (썸네일 크기로 노출)",
        "constraints": "3초 안에 멈추지 않으면 지나침, 텍스트 과다 시 무시",
        "optimal_format": "비주얼 중심, 카피 최소화",
    },
    "instagram_story": {
        "context": "인스타그램 스토리 (전체화면, 5초 자동 넘김)",
        "constraints": "5초 내 핵심 전달 필수, 상단 UI가 카피 가림",
        "optimal_format": "임팩트 있는 첫 1초, CTA 버튼 가시성",
    },
    "naver_display": {
        "context": "네이버 포털 디스플레이 배너 (PC 우측 사이드바)",
        "constraints": "배너 맹시(Banner Blindness) 심각, 신뢰 신호 중요",
        "optimal_format": "브랜드 신뢰도 강조, 명확한 혜택 문구",
    },
    "youtube_preroll": {
        "context": "유튜브 영상 재생 전 광고 (5초 후 스킵 가능)",
        "constraints": "5초 안에 스킵 여부 결정, 흥미 없으면 즉시 스킵",
        "optimal_format": "초반 3초 훅 강도가 핵심",
    },
    "mobile_app_banner": {
        "context": "모바일 앱 하단 배너 (320×50)",
        "constraints": "매우 작은 화면, 텍스트 거의 안 읽힘, 실수 클릭 많음",
        "optimal_format": "브랜드 컬러 + 짧은 카피 + 강한 CTA",
    },
    "kakao_bizboard": {
        "context": "카카오톡 채팅 목록 상단 빅보드",
        "constraints": "카카오톡 이용 중 컨텍스트, 대화 흐름 방해 인식",
        "optimal_format": "친근한 톤, 일상 연관 메시지",
    }
}
```

---

### 프롬프트 수정 패턴 (기존 파일 수정)

```python
# domain/multiagent/spokes/agents/reaction_simulation.py 수정
def build_ad_reaction_prompt(
    persona: Persona,
    ad_analysis: dict,
    platform: str = "instagram_feed"   # ← 신규 파라미터
) -> list:
    platform_ctx = PLATFORM_CONTEXTS.get(platform, PLATFORM_CONTEXTS["instagram_feed"])
    
    system = f"""
당신은 {persona.layer1.age}세 {persona.layer1.gender}입니다.
지금 {platform_ctx['context']}에서 광고를 보게 되었습니다.

[이 매체의 특성 — 반드시 고려]
{platform_ctx['constraints']}

[기존 페르소나 정보]
...{persona 정보}...
"""
```

---

### 매체 비교 API 엔드포인트

```
POST /api/v1/simulations/cross-platform
```

**요청 예시:**
```json
{
  "ad_id": "AD_0042",
  "platforms": ["instagram_feed", "instagram_story", "naver_display"],
  "persona_pool_id": "POOL_0012"
}
```

**응답:** 플랫폼별 CTR Prediction, 매체 최적화 제안 비교 테이블

---

## Phase 2 통합 아키텍처 변경 사항

### 신규 추가 노드 (LangGraph)

```python
# Phase 2에서 simulation_graph.py에 추가되는 노드들
graph.add_node("compliance_check", ...)        # Phase 2.3 (선택적)
graph.add_node("viral_simulation", ...)         # Phase 2.1 (별도 그래프)
graph.add_node("competitor_analysis", ...)      # Phase 2.2 (선택적)
graph.add_node("cross_platform_analysis", ...)  # Phase 2.4 (파라미터 확장)
```

### 신규 DB 테이블 목록

| 테이블 | 용도 | 추가 Phase |
|--------|------|-----------|
| `viral_comments` | 바이럴 시뮬레이션 댓글 트리 저장 | 2.1 |
| `viral_network_graphs` | 네트워크 그래프 데이터 (프론트 시각화용) | 2.1 |
| `competitor_ads` | 경쟁사 광고 임베딩 DB | 2.2 |
| `competitor_analysis_results` | 비교 분석 결과 | 2.2 |
| `compliance_documents` | 규정 문서 임베딩 DB | 2.3 |
| `compliance_results` | 컴플라이언스 검토 결과 | 2.3 |

### 신규 의존 패키지

```
# Phase 2.1
langgraph>=0.2.0             # 이미 있음 (Phase 1), ReAct 패턴 활용

# Phase 2.2
playwright>=1.40.0           # 경쟁사 광고 크롤링
httpx>=0.27.0                # Meta Ad Library API 호출 (이미 있을 가능성)

# Phase 2.3
pypdf>=4.0.0                 # 규정 PDF 파싱
python-docx>=1.1.0           # 규정 Word 문서 파싱
```

---

## 엔터프라이즈 Pricing 연계

| 기능 | Starter | Professional | Enterprise |
|------|---------|--------------|------------|
| 소셜 바이럴 시뮬레이터 (2.1) | ❌ | ✅ (50명) | ✅ (무제한) |
| 경쟁사 레퍼런스 비교 (2.2) | ❌ | ✅ (월 10회) | ✅ (무제한 + 커스텀 DB) |
| ESG 컴플라이언스 검증 (2.3) | ❌ | ❌ | ✅ (전용 기능) |
| 매체별 UX 뷰어 (2.4) | ❌ | ✅ (3개 매체) | ✅ (전체 매체) |

---

## 미결 의사결정 사항 (구현 전 합의 필요)

| # | 질문 | 결정 필요 이유 |
|---|------|--------------|
| 1 | 바이럴 시뮬레이션 라운드 수를 몇 으로 할 것인가? (비용 vs 정밀도) | 3라운드 = Phase 1 대비 ~3배 비용 |
| 2 | 경쟁사 광고 DB를 자체 수집할 것인가, 외부 데이터 API를 쓸 것인가? | 크롤링 법적 리스크 vs 구독 비용 |
| 3 | 컴플라이언스 위반 시 시뮬레이션을 중단시킬 것인가, 경고만 줄 것인가? | UX 방향 결정 |
| 4 | 규정 DB를 KR만 지원할 것인가, 글로벌(EU, US) 확장할 것인가? | 첫 타깃 시장 결정에 따라 공수 3배 차이 |

---

> **참고 문서**:  
> - 기술 레퍼런스: `backend/docs/MULTIAGENT_TECHNICAL_REFERENCE.md`  
> - 서비스 기획서: `docs/PERSONA100_SERVICE_PLAN.md`
