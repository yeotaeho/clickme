# 논문 → Persona.100 통합 분석 노트

> **참고 논문**: "LLM-Based Multi-Agent System for Simulating and Analyzing Marketing and Consumer Behavior"  
> Clark University & Quinnipiac University / IEEE ICEBE 2025  
> arxiv: https://arxiv.org/pdf/2510.18155  
> GitHub (논문 공개 코드): https://github.com/carolchu1208/LLM-Based-Generative-Agents-Simulating-Consumer-Decisions  
> **작성일**: 2026-06-02  
> **목적**: 논문 검증 결과를 현재 설계에 어떻게 흡수할지 결정하기 위한 기술 판단 문서

---

## 0. 핵심 결론 (TL;DR)

```
1. "LLM 에이전트 마케팅 시뮬레이션"은 학술적으로 검증된 접근이다.
   → 우리가 만들려는 것은 헛소리가 아니다.

2. 단, 논문의 핵심은 "System Prompt 주입" 단 하나가 아니다.
   메모리 + 내부 상태 수치 제약 + Enum 강제 출력의 조합이 핵심이다.

3. 우리 현재 설계(Phase 1)는 이 중 Enum 강제 출력만 충족한다.
   메모리와 상태 제약은 Phase 2 이전에 최소 버전이라도 넣어야 한다.

4. 18~45세 페르소나는 신뢰 가능, 그 외는 명시적 한계 고지 필요.

5. 멀티 LLM 전략은 다양성에는 유효하지만, 재현성을 위해
   동일 시뮬레이션 재실행 시에는 모델 + 버전을 고정해야 한다.

6. 에이전트 간 구전 효과(Word-of-Mouth)가 프로그래밍 없이 자연 발생했다.
   → Phase 3 Virality Potential 지표의 학술적 근거로 직접 활용 가능.

7. 할인 이벤트는 시장을 키운 게 아니라 경쟁사 점유율을 뺏어온 것이었다.
   → "광고가 시장을 넓히는가 vs 점유율을 뺏어오는가"를 시뮬레이션으로
   구분할 수 있다는 근거. Phase 3 경쟁 분석 기능의 설계 근거.
```

---

## 1. 논문이 검증한 것 — 우리가 근거로 쓸 수 있는 것

### 1-1. 마케팅 시뮬레이션의 방향성은 실제와 유의미하게 일치한다

논문 실험 결과, 할인 이벤트에 대한 LLM 에이전트의 반응이 기존 마케팅 이론(Salop & Stiglitz, 1982)과 일치하는 패턴을 보였다.

| 지표 | 결과 |
|------|------|
| 할인 당일 매출 변화 | +51% ($100.6 → $152.11) |
| 경쟁 식당 영향 | -7% |
| 시장 점유율 | 30% → 41% |
| 할인 종료 후 지속 효과 | 2~3일간 유지 |

**우리 서비스에 적용하는 방식**:
- B2B 고객 설득 자료에 "IEEE ICEBE 2025 논문에서 LLM 시뮬레이션이 마케팅 이론과 유의미하게 일치함이 검증됨"을 인용 가능
- 단, "정확한 수치 예측"이 아닌 "방향성과 상대적 비교"가 신뢰 구간이라는 점을 disclaimer에 명시

### 1-2. 소셜 다이내믹스 — 구전 효과가 프로그래밍 없이 자연 발생했다

논문의 가장 주목할 만한 발견 중 하나는 **에이전트 간 대화를 통한 구전 효과**가 연구자의 별도 프로그래밍 없이 자연적으로 발생했다는 점이다.

```
[실제 시뮬레이션 로그]
Lisa → David  : "그 치킨집 어제 갔는데 진짜 맛있더라, 같이 가자"
Lisa → Sophie : 동일 추천
Lisa → Rebecca, Alex, Maria: 연쇄 추천

결과: Lisa 한 명의 경험이 5명의 방문 행동으로 이어짐
→ "입소문 확산" 패턴이 코드가 아닌 에이전트의 자유 대화에서 발생
```

**우리 서비스에 주는 시사점**:

현재 `PersonaResponse`에는 `action_taken`으로 `"share"` 값이 있다. 이것이 단순한 선택지가 아니라 **Virality Potential 지표의 학술적 근거**가 된다.

```python
# "share"를 선택한 페르소나 비율 = Virality Potential 원시값
virality_potential = len([r for r in responses if r.action_taken == "share"]) / len(responses)

# 리포트에 반영
{
    "metrics": {
        "virality_potential": 0.18,  # 18%가 공유 의향 → "바이럴 가능성 높음"
        "virality_label": "high" if virality_potential > 0.15 else "low"
    }
}
```

Phase 3의 "소셜 바이럴 시뮬레이터" 기능은 이 논문 결과를 직접 근거로 삼는다.  
단일 페르소나의 "share" 반응이 2차 노출 그룹으로 전파되는 시나리오를 멀티라운드로 시뮬레이션한다.

### 1-3. 대체 효과 vs. 시장 확장 — 경쟁 분석 기능의 설계 근거

논문의 중요한 발견 중 하나는 할인 이벤트의 **효과 원천**에 관한 것이다.

```
[논문 결과]
총 일일 시장 규모: $276~471 사이에서 변동 (체계적 확장 없음)
치킨집 점유율:    30% → 41% 상승
경쟁 식당 매출:  -7% 감소

해석: 할인이 "전체 시장 파이를 키운 게 아니라"
     경쟁사 고객을 뺏어온 것 (Substitution Effect, 대체 효과)
```

**우리 서비스에 주는 시사점**:

광고 시뮬레이션 결과를 해석할 때 두 가지 시나리오를 구분할 수 있다:

| 시나리오 | 의미 | 마케터에게 주는 신호 |
|----------|------|-------------------|
| 높은 CTR + 낮은 audience_fit | 기존 구매자 재활성화 | 리텐션 캠페인에 적합 |
| 높은 CTR + 높은 audience_fit + 낮은 purchase_intent | 신규 고객 인지 확대 | 브랜딩 캠페인에 적합 |
| 높은 CTR + 높은 purchase_intent | 경쟁사 전환 가능성 | 비교 광고 전략 고려 |

Phase 3 경쟁 분석 기능(`PHASE2_EXPANSION_REFERENCE.md` 2.2항)에서 경쟁사 대비 시뮬레이션을 구현할 때 이 프레임워크를 적용한다.

---

## 2. 현재 설계의 공백 — 논문이 드러낸 것

### 2-1. System Prompt 주입만으로는 페르소나가 유지되지 않는다

**현재 우리 설계** (`reaction_simulation.py` 예정):
```python
# "질문 1개 = API 호출 1회" 원칙을 지키면 Context Drift는 막을 수 있음
# 하지만 이것은 단발성 광고 반응에만 유효하다
system = f"""당신은 지금부터 아래 소비자 역할만 합니다... {persona 정보}"""
```

**논문이 보여준 한계**:
```
단순 프롬프트로 "Lisa와 커피 마시기로 했다" 주입 → 다음 턴에 망각
메모리 시스템 있을 때만 → 실제로 약속 이행 행동 발생
```

**판단**:  
Phase 1 MVP는 "광고 1개에 대한 단발 반응" 시나리오이므로 "1질문 1호출" 원칙만으로도 충분하다.  
하지만 Phase 2의 **가상 설문조사(Synthetic Survey)** 는 여러 라운드 질문을 하는 시나리오이므로, 이때는 최소한의 세션 메모리가 필요하다.

**결론**: Phase 1은 현재 설계 유지 가능. Phase 2 설문조사 기능 구현 시 아래 섹션 4의 경량 메모리를 도입한다.

---

### 2-2. Layer3 서사 컨텍스트를 정량 수치 제약으로 강화해야 한다

**현재 우리 Layer3**:
```python
class PersonaLayer3(BaseModel):
    recent_purchase_experience: str   # 서사 텍스트
    current_pain_point: str           # 서사 텍스트
    ad_repellent_words: list[str]     # ✅ 이건 제약으로 작동
    ad_trigger_words: list[str]
    emotional_state_current: str
```

**논문의 Needs 트리아드** (내부 상태 수치 제약):
```
식료품 수준 → 일정 수준 이하 시 쇼핑 행동 트리거
에너지 수준 → 이동/업무 시 감소, 식사/수면으로 회복
금전 수준   → 예산 초과 시 cheaper 옵션으로 자동 전환
```

**핵심 인사이트**: "가성비를 중시한다"는 텍스트 서사보다  
"이번 달 가용 예산: 50,000원 / 광고 제품 가격: 89,000원" 이라는 수치 제약이  
훨씬 더 일관된 행동을 만들어낸다.

**Persona.100 버전으로 변환**:

| 논문 원본 | 우리 서비스 변환 |
|----------|----------------|
| 에너지 수준 (Energy) | 구매 욕구 수준 (`purchase_desire: int`, 0~100) |
| 식료품 수준 (Grocery) | 현재 보유 여부 (`already_owns: bool`) |
| 금전 수준 (Money) | 가용 예산 (`available_budget: int`, 단위: 원) |

> **왜 `int`인가**: 문서의 핵심 인사이트가 "서사 텍스트보다 수치 제약이 강력하다"인데,  
> `"under_30k"` 같은 문자열 범주는 텍스트 서사와 다를 게 없다.  
> `available_budget: 50000` + `product_price_reference: 89000` 이라는 두 수치가 있으면  
> LLM이 "예산이 부족하므로 구매를 미루겠다"는 논리적으로 일관된 반응을 생성하기 쉽다.

**행동 트리거 로직**:
```python
# 이 수치들을 프롬프트에 명시적으로 주입
# ad_product_price는 광고 분석 시 추출하거나 사용자가 입력
if persona.available_budget < ad_product_price:
    → "지금은 살 형편 안 돼" 반응 가중치 증가
if persona.purchase_desire < 30:
    → 광고 회피(ad_avoidance) 가중치 증가
if persona.already_owns:
    → "이미 갖고 있어서 필요 없음" 반응 트리거

# 프롬프트 내 수치 직접 반영 예시
prompt_context = f"""
당신의 이번 달 여유 자금: {persona.available_budget:,}원
이 광고의 제품 예상 가격: {ad_product_price:,}원
"""
```

**적용 시점**: Phase 1.5 또는 Phase 2에서 `PersonaLayer3`에 수치 필드 추가 권장.  
Phase 1 MVP는 현재 구조로 진행하되, 설계 시 확장 고려해서 JSONB로 저장.

---

### 2-3. 할루시네이션 대응 — Enum 강제는 이미 맞다, 더 강화하면 된다

**논문에서 발생한 오류**:
```json
{
  "action": "eat",
  "target": "new bistro near Oak View Condos",  // 존재하지 않는 장소
  "description": "Dinner plans with Sophie"
}
// 프롬프트가 7,098 글자였음에도 발생
```

**현재 우리 설계** (`PersonaResponse`):
```python
scroll_behavior: str  # "pass" | "pause_1sec" | "pause_3sec" | "stop_and_read"
action_taken: str     # "ignore" | "screenshot" | "click" | "share"
```

이 부분은 이미 올바른 방향이다. 추가로 강화할 점:

```python
# 현재
action_taken: str

# 개선안: Enum 타입으로 강제 + 프롬프트에도 명시
from enum import Enum

class ActionTaken(str, Enum):
    IGNORE = "ignore"
    SCREENSHOT = "screenshot"
    CLICK = "click"
    SHARE = "share"

# 프롬프트 내 명시 (할루시네이션 방지)
"""
반드시 다음 중 하나만 선택하세요. 이 외의 값은 절대 출력 금지:
- "ignore"
- "screenshot"  
- "click"
- "share"
"""
```

**`ValidationAgent`의 역할 확장**:  
Enum 이탈 감지를 1차 방어선으로 추가:
```python
def validate_response(response: dict) -> bool:
    valid_actions = {"ignore", "screenshot", "click", "share"}
    valid_scrolls = {"pass", "pause_1sec", "pause_3sec", "stop_and_read"}
    
    if response.get("action_taken") not in valid_actions:
        return False  # 할루시네이션 → 재시도 또는 제외
    if response.get("scroll_behavior") not in valid_scrolls:
        return False
    return True
```

---

## 3. 연령대 신뢰도 제약 — 리포트에 반드시 반영

**논문의 직접 인용**:
> "7세 아이 에이전트에게 어린이 특성을 주입했음에도 피곤할 때 커피를 요청하는 등 성인 행동이 나타났다. 노인 에이전트도 중년 성인과 구별되지 않았다."  
> 원인: LLM 학습 데이터가 인터넷 사용자(18~45세) 위주로 구성됨

**Persona.100 연령대 신뢰 등급**:

| 연령대 | 신뢰 등급 | 비고 |
|--------|----------|------|
| 20대 | ✅ 높음 | SNS, 커뮤니티 학습 데이터 풍부 |
| 30대 | ✅ 높음 | 블로그, 리뷰, 직장 관련 풍부 |
| 40대 | ⚠️ 중간 | 학습 데이터 상대적으로 적음 |
| 50대 | ⚠️ 낮음 | 주의 필요, 명시적 한계 고지 |
| 60대+ | ❌ 매우 낮음 | 결과 신뢰 불가 수준 |
| 10대 이하 | ❌ 매우 낮음 | 성인 행동 패턴이 투영됨 |

**구현 방향**:

```python
# domain/multiagent/models/bases/persona.py
AGE_RELIABILITY_MAP = {
    (20, 39): "high",
    (40, 49): "medium",
    (50, 59): "low",
    (60, 99): "very_low",
    (0, 19): "very_low",
}

def get_age_reliability(age: int) -> str:
    for (low, high), level in AGE_RELIABILITY_MAP.items():
        if low <= age <= high:
            return level
    return "unknown"
```

```python
# 리포트 출력에 반드시 포함
{
    "disclaimer": "본 결과는 AI 시뮬레이션 기반 예측입니다. 실제 성과와 ±20~30% 오차 가능.",
    "reliability_notes": {
        "age_coverage": "20~39세 구간 응답 신뢰도 높음. 50대 이상 구간은 LLM 학습 데이터 한계로 신뢰도 낮음.",
        "persona_count_valid": 97,
        "outliers_excluded": 3
    }
}
```

---

## 4. 멀티 LLM 전략 재정립 — 다양성 vs. 재현성

**논문이 발견한 문제**:
```
DeepSeek-V3: 동일 프롬프트에 상대적으로 안정적 응답
llama2:      동일 프롬프트에서 자주 이탈
→ 결과의 재현성이 프롬프트뿐만 아니라 LLM 모델에도 의존함
```

**현재 우리 Fallback 체인**:
```
1차: GPT-4o-mini → 2차: Claude Haiku → 3차: 캐시 재사용 → 4차: 페르소나 제외
```

**문제점**: 동일한 시뮬레이션을 재실행할 때 1차/2차 모델이 다르게 선택되면 결과가 달라진다.

**개선된 전략**:

| 시나리오 | 전략 | 이유 |
|----------|------|------|
| 다양성 확보 (첫 실행) | 멀티 LLM 혼합 허용 | 페르소나 간 응답 분산 목적 |
| 재현성 확보 (재실행) | 모델 고정 + 버전 고정 | `gpt-4o-mini-2024-07-18` 처럼 |
| Rate Limit 상황 | Fallback 허용, 단 리포트에 명시 | 투명성 확보 |

```python
# SimulationState에 추가
class SimulationState(TypedDict):
    ...
    model_config: dict  # {"primary": "gpt-4o-mini-2024-07-18", "fallback": "claude-haiku-20240307"}
    # → 재현 시 이 config를 그대로 사용
```

---

## 5. Phase별 적용 우선순위

### Phase 1 MVP — 현재 설계 유지 + 최소 강화

| 항목 | 상태 | 조치 |
|------|------|------|
| "1질문 1호출" 원칙 | ✅ 이미 설계됨 | 유지 |
| Enum 강제 출력 | ✅ 이미 설계됨 | Python Enum 타입으로 강화 |
| ValidationAgent Enum 이탈 감지 | ⚠️ 미구현 | Phase 1에 추가 |
| 연령대 신뢰도 리포트 표기 | ⚠️ 미구현 | Phase 1에 추가 (코드 5줄 수준) |
| 모델 버전 고정 (`-2024-07-18`) | ⚠️ 미적용 | Phase 1 settings.py에 상수 추가 |

### Phase 2 — 페르소나 내부 상태 수치 제약 도입

| 항목 | 조치 |
|------|------|
| `PersonaLayer3`에 수치 필드 추가 | `purchase_desire: int`, `available_budget: int`, `product_price_reference: int`, `already_owns: bool` |
| 프롬프트 템플릿에 수치 트리거 반영 | `available_budget` < `product_price_reference` → "살 형편 안 돼" 반응 가중치 |
| 경량 세션 메모리 (설문조사용) | Redis에 이전 답변 저장, 다음 질문 프롬프트에 주입 |
| 리포트에 AISAS 레이어 추가 | Attention/Interest/Action/Share 단계별 수치 출력 |

### Phase 2+ — 완전한 메모리 시스템 (논문 수준)

논문의 3계층 메모리(EVENT/REFLECTION/CONVERSATION/PURCHASE 태깅 + 시간 감쇠 필터)는  
Phase 2 이후 "사용자 패널 재사용" 기능이 필요할 때 도입.  
MVP 단계에서는 over-engineering이므로 스킵.

---

## 6. 페르소나 이탈 감지 로직 (논문 → 코드 변환)

### Dead Agent 개념과의 연결

논문에서 에이전트의 내부 상태(에너지)가 0에 도달하면 **"Dead Agent"** 로 처리하고 비상 복구 로직(Emergency Re-plan)을 적용한다:

```
논문:
  에너지 < 20 → 긴급 식사 계획 재수립 (Emergency Re-plan)
  에너지 = 0  → 강제 귀가, 수면 후 다음날 복귀 (Dead Agent 처리)

우리 서비스 대응:
  응답 품질 < 임계값 (Enum 이탈 or 페르소나 이탈) → 재시도 (Emergency Re-plan)
  재시도 후에도 실패                              → Dead Agent 처리: 해당 페르소나 제외
```

이 논문 개념이 우리 Fallback 체인의 설계 근거가 된다. 단순한 예외 처리가 아니라  
"에이전트가 기능 불능 상태에 빠졌을 때 복구를 시도하고, 복구 불가 시 제거"라는  
명확한 의미론을 가진 로직이다.

논문의 "Emergency Re-plan" 개념을 우리 서비스의 이탈 감지로 변환:

```python
# domain/multiagent/spokes/agents/validation.py

MARKETING_EXPERT_TERMS = [
    "CTR", "전환율", "ROAS", "퍼널", "acquisition cost",
    "A/B 테스트", "인게이지먼트", "KPI", "마케팅 전략"
]

AI_DISCLOSURE_PATTERNS = [
    "저는 AI", "언어 모델", "I'm an AI", "as an AI",
    "제 페르소나", "역할극", "제가 연기하는"
]

def detect_persona_drift(response: dict, persona: Persona) -> bool:
    text = str(response.get("first_impression_text", "")) + str(response.get("main_concern", ""))
    
    # 1. AI 자기 노출
    if any(pattern in text for pattern in AI_DISCLOSURE_PATTERNS):
        return True
    
    # 2. 마케팅 전문 용어 3개 이상
    expert_count = sum(1 for term in MARKETING_EXPERT_TERMS if term in text)
    if expert_count >= 3:
        return True
    
    # 3. 응답 언어가 페르소나와 불일치 (예: 영어 페르소나인데 한국어 응답)
    # (언어 감지 라이브러리 사용 시 추가)
    
    return False
```

이탈 감지 시 처리:
```python
# Fallback 체인에 이탈 감지 추가
if detect_persona_drift(response, persona):
    # 1차: 재시도 (온도 낮춰서)
    response = await retry_with_lower_temperature(persona, ad_analysis)
    # 재시도 후에도 이탈 시 제외 + errors 필드에 기록
    if detect_persona_drift(response, persona):
        state["errors"].append(f"Persona {persona.persona_id}: drift detected, excluded")
        return None
```

---

## 7. Thread-safe 병렬 실행 — 논문 구조 단순화 버전

논문은 `threading.Lock()` 기반 메모리 잠금을 사용했지만,  
우리는 asyncio 기반이므로 `asyncio.Lock()`으로 대응:

```python
# domain/multiagent/hub/services/simulation_service.py

class SimulationContext:
    def __init__(self):
        self._results: list = []
        self._errors: list = []
        self._lock = asyncio.Lock()
    
    async def record_result(self, result: PersonaResponse):
        async with self._lock:
            self._results.append(result)
    
    async def record_error(self, error: str):
        async with self._lock:
            self._errors.append(error)

async def run_reactions(personas: list, ad_analysis: dict) -> SimulationContext:
    ctx = SimulationContext()
    semaphore = asyncio.Semaphore(20)
    
    async def bounded_simulate(persona: Persona):
        async with semaphore:
            try:
                result = await simulate_single_persona(persona, ad_analysis)
                if result and not detect_persona_drift(result, persona):
                    await ctx.record_result(result)
                else:
                    await ctx.record_error(f"{persona.persona_id}: drift/invalid")
            except Exception as e:
                await ctx.record_error(f"{persona.persona_id}: {str(e)}")
    
    await asyncio.gather(*[bounded_simulate(p) for p in personas])
    return ctx
```

---

## 8. 소비자 여정 프레임워크 — 우리 지표의 이론적 근거

논문이 인용한 소비자 여정 프레임워크의 진화:

```
AIDA (1898)  → Attention → Interest → Desire → Action
AIDMA (1920) → + Memory (구매 전 기억 단계 추가)
AISAS (2004) → Attention → Interest → Search → Action → Share  (인터넷 시대)
AIDEES(2012) → + Emotional Involvement, Evangelize, Share (SNS 시대)
```

**AISAS와 우리 측정 지표의 매핑**:

| AISAS 단계 | 우리 지표 | 필드 | 비고 |
|------------|----------|------|------|
| Attention | 첫인상 점수 | `scroll_behavior`, `first_emotion` | 스크롤 멈춤 = Attention 발생 |
| Interest | 클릭 의향 | `click_intention` (0~100) | 관심도 정량화 |
| Search | (현재 미측정) | — | Phase 3에서 "검색 의향" 항목 추가 가능 |
| Action | 구매 전환 의향 | `purchase_intention`, `action_taken` | "click" or "purchase" |
| Share | 바이럴 가능성 | `action_taken == "share"` | Virality Potential 원시값 |

이 매핑은 두 가지 목적에 활용된다:
1. **내부 설계 근거**: 왜 이 지표들을 측정하는가에 대한 이론적 뒷받침
2. **B2B 고객 설득**: 마케터에게 친숙한 AISAS 언어로 결과를 설명할 수 있음

```python
# 리포트에서 AISAS 프레임워크 기반 서술 예시
{
    "aisas_summary": {
        "attention_rate": "62% — 10명 중 6명이 스크롤을 멈춤",
        "interest_score": 54,
        "search_intent": "미측정 (Phase 3 예정)",
        "action_rate": "23% — 클릭 또는 저장 의향",
        "share_rate": "18% — Virality Potential 높음"
    }
}
```

---

## 9. 논문 vs. 우리 설계 — 격차 요약표 (업데이트)

| 항목 | 논문 | 현재 우리 설계 | 격차 / 우선순위 |
|------|------|--------------|----------------|
| 페르소나 주입 방식 | 메모리 3계층 | System Prompt | Phase 1은 OK, Phase 2에서 보완 |
| 내부 상태 제약 | 수치 트리아드 (에너지/식료품/금전) | Layer3 텍스트 서사 | Phase 2에 `available_budget: int` 등 수치 필드 추가 |
| 할루시네이션 방지 | 장소 제약 명시 | Enum 강제 (이미 설계) | Python Enum 타입 강화로 충분 |
| 이탈 감지 | Dead Agent 개념 (논문에서 명시 안 함) | ValidationAgent (설계됨) | 위 코드로 Phase 1에 구현 |
| 연령 신뢰도 | 언급만 함 | 없음 | 리포트 disclaimer에 Phase 1 추가 |
| 재현성 | 모델별 차이 언급 | 멀티 LLM Fallback | 모델 버전 고정 상수 추가 |
| 규모 | 11명 | 20~100명 | Semaphore(20) + Celery로 대응 |
| 소셜 다이내믹스 | 구전 효과 자연 발생 | `action_taken: "share"` 집계만 | Phase 3 바이럴 시뮬레이터에서 멀티라운드 구현 |
| 대체 효과 분석 | 경쟁사 점유율 대체 확인 | 없음 | Phase 3 경쟁 분석 기능 설계 근거 |
| 소비자 여정 | AISAS 인용 | 암묵적 매핑 | 리포트 출력에 AISAS 레이어 추가 (Phase 2) |
| 검증 | 실제 패턴과 비교 | calibration_data 테이블 | Phase 3 이후 실제 성과 대비 교정 |
| 참조 구현 | GitHub 공개 코드 없음 | — | Phase 2 메모리 구현 시 논문 GitHub 참고 |

---

## 10. 결론 — 바로 할 것 vs. 나중에 할 것

### Phase 1 MVP에 반영할 것 (작업량 소규모)

1. **모델 버전 상수 고정** `settings.py`
   ```python
   OPENAI_REACTION_MODEL: str = "gpt-4o-mini-2024-07-18"
   ANTHROPIC_FALLBACK_MODEL: str = "claude-haiku-20240307"
   ```

2. **Python Enum 타입 강화** — `PersonaResponse`의 문자열 필드를 Enum으로

3. **ValidationAgent에 이탈 감지 추가** — 위 `detect_persona_drift()` 함수 구현

4. **리포트 disclaimer에 연령대 신뢰도 고지** — 5줄 코드

5. **SimulationState에 `model_config` 필드 추가** — 재현성 추적용

### Phase 2에서 할 것 (설계 변경 수반)

1. **`PersonaLayer3`에 수치 제약 필드 추가**
   - `purchase_desire: int` (0~100)
   - `available_budget: int` (단위: 원. 예시: 50000)
   - `product_price_reference: int` (광고 대상 제품 예상 가격. 행동 트리거 비교용)
   - `already_owns: bool`

2. **설문조사 기능용 경량 세션 메모리** — Redis에 이전 답변 저장, 다음 질문 프롬프트에 주입

3. **수치 제약 기반 행동 트리거** — 프롬프트 템플릿 개선

4. **리포트에 AISAS 레이어 추가** — Attention/Interest/Action/Share 단계별 수치 출력

### Phase 3 이후에 할 것 (연구 영역)

1. **완전한 3계층 메모리 시스템** (논문 수준)  
   → 재사용 패널 기능이 필요해질 때. 출발점: 논문 GitHub 참고  
   https://github.com/carolchu1208/LLM-Based-Generative-Agents-Simulating-Consumer-Decisions

2. **소셜 바이럴 시뮬레이터** — "share" 반응자를 2차 노출 그룹으로 연결, 멀티라운드 확산 시뮬레이션

3. **경쟁 분석 기능** — 동일 광고를 경쟁사 광고와 나란히 시뮬레이션, 대체 효과 수치화

4. **calibration_data 기반 회귀 모델** — 실제 성과 데이터 누적 후 예측 정확도 교정

---

> 이 문서는 논문 분석을 마치고 설계 의사결정을 위해 작성된 기술 판단 노트입니다.  
> 구현 순서는 `MULTIAGENT_TECHNICAL_REFERENCE.md`의 Phase별 범위를 따릅니다.
