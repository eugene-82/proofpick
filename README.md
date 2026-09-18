# ProofPick

> **AI는 진실을 판정하지 않고, 근거를 찾아 정리합니다.**  
> ProofPick은 제품 구매 전 웹과 커뮤니티의 실사용 근거를 수집·검증해, 사용자가 더 근거 있는 구매 결정을 내릴 수 있도록 돕는 AI 구매 검증 서비스입니다.

---

## 1. 프로젝트 소개

온라인 쇼핑에서 가장 어려운 점은 리뷰가 많아도 **무엇을 믿어야 하는지 알기 어렵다**는 것입니다.

ProofPick은 특정 쇼핑몰의 별점이나 리뷰만 보는 대신, 웹 전반의 실사용 후기·장기 사용 경험·단점·문제 사례·커뮤니티 글을 수집합니다.

수집한 자료는 그대로 요약하지 않습니다.

ProofPick은 다음을 확인합니다.

- 같은 내용이 여러 곳에 복제된 것은 아닌가?
- 서로 독립적인 출처인가?
- 실제 사용 경험인가?
- 제품 자체에 대한 주장인가?
- 인용 근거가 실제 원문에 존재하는가?
- 장기 사용 근거가 있는가?
- 반대되는 근거도 존재하는가?

최종적으로 ProofPick은 구매 판단과 함께 **그 판단을 만든 근거와 출처를 함께 보여주는 것**을 목표로 합니다.

---

## 2. 핵심 기능

### 제품 분석

사용자가 제품명을 입력하면 ProofPick이 실제 웹 검색을 수행합니다.

예:

```text
AirPods Pro 2
Logitech MX Master 3S
Dyson V15 Detect
```

### 실사용 근거 검색

기본 검색은 다음 세 방향으로 이루어집니다.

```text
{제품명} 실사용 후기
{제품명} 단점 문제
{제품명} 장기 사용
```

현재 검색 provider는 **Tavily**이며, query당 최대 5개의 결과와 가능한 경우 `raw_content`를 받아옵니다.

### 한국 커뮤니티 보강 검색

초기 근거만으로 판단하기 어려워 `EARLY_ADOPTER` 상태가 나오면 한국 커뮤니티 검색을 추가로 수행합니다.

대상 커뮤니티:

- 디시인사이드
- 에펨코리아
- 더쿠
- 아카라이브
- 루리웹

현재 최대 3개의 community query를 추가로 사용합니다.

예:

```text
{product} (site:dcinside.com OR site:fmkorea.com) 후기 단점
{product} (site:theqoo.net OR site:arca.live) 후기 문제
{product} site:ruliweb.com 실사용 장기 사용
```

커뮤니티 글이라고 자동으로 신뢰하지 않습니다. 기존과 동일한 filtering, deduplication, grounding, semantic verification을 모두 거칩니다.

### 반대 근거 재검증

초기 판단이 아래 중 하나이면 반대 근거를 추가로 검색합니다.

- `BUY`
- `BUY_IF`
- `SKIP`

예를 들어 BUY가 나왔다면:

```text
{product} problems long term
{product} failure issue
{product} {positive aspect} problems
```

를 추가 검색한 뒤 전체 근거를 다시 평가합니다.

즉 ProofPick은 한 방향의 근거만 보고 결론을 내리지 않습니다.

---

## 3. 구매 판단

ProofPick은 네 가지 상태를 사용합니다.

### BUY

독립적이고 검증 가능한 근거가 충분하고, 반대 근거를 추가로 확인한 뒤에도 구매 판단이 유지되는 상태입니다.

### BUY_IF

제품 자체는 고려할 만하지만 특정 조건, 사용 환경, 단점 또는 리스크를 감수해야 하는 상태입니다.

### SKIP

신뢰 가능한 부정 근거나 구매를 막을 수준의 리스크가 충분히 확인된 상태입니다.

### EARLY_ADOPTER

제품이 나쁘다는 뜻이 아닙니다.

현재 확보된 근거만으로는 일반 사용자에게 BUY / BUY_IF / SKIP 중 하나를 충분한 확신으로 제시하기 어렵다는 의미입니다.

예:

- 독립적인 실사용 출처 부족
- 장기 사용 근거 부족
- 검증 가능한 claim 부족
- 검색 결과의 품질 또는 coverage 부족

UI에서는 다음과 같이 설명하는 것을 목표로 합니다.

> **검증 근거 부족 — 일반적인 구매 판단을 내리기에 독립적인 실사용 근거가 충분하지 않습니다.**

---

## 4. 전체 분석 파이프라인

```text
User Query
    ↓
Product Resolver
    ↓
Initial Query Generator
    ↓
Tavily Search
    ↓
Product Identity Filtering
    ↓
Source Filtering
    ↓
URL / Content Deduplication
    ↓
Source Identity Registry
    ↓
Evidence Cleaning / Compression
    ↓
Structured Claim Extraction
    ↓
Grounding Validation
    ↓
Semantic Verification
    ↓
Claim Clustering
    ↓
Confidence Evaluation
    ↓
Initial Decision
    ↓
┌─────────────────────────────┐
│ EARLY_ADOPTER               │
│   ↓                         │
│ Korean Community Boost      │
│   ↓                         │
│ Full Re-evaluation          │
└─────────────────────────────┘
    ↓
BUY / BUY_IF / SKIP
    ↓
Counter-Evidence Search
    ↓
Full Re-evaluation
    ↓
Final Decision
```

---

## 5. 검색 예산

불필요한 검색 비용과 분석 시간을 제한하기 위해 query budget을 사용합니다.

### 일반 분석

```text
Initial: 최대 3
Counter Evidence: 최대 3
```

### 근거 부족 시

```text
Initial: 최대 3
Korean Community Boost: 최대 3
Counter Evidence: 최대 3
```

현재 runtime 기준 최대 검색 수는 **9회**이며, 설계 상한 10회 이내에서 동작합니다.

---

## 6. 근거 신뢰성 처리

### Product Identity

등록된 제품은 deterministic resolver를 사용합니다.

등록되지 않은 명확한 제품명은 provisional identity로 처리한 뒤 검색 결과에서 동일 제품임을 확인합니다.

예:

```text
Logitech MX Master 3S
Dyson V15 Detect
Sony WH-1000XM5
```

세대와 variant는 엄격하게 구분합니다.

```text
WH-1000XM5 != WH-1000XM4
AirPods Pro 2 != AirPods Pro
Nintendo Switch OLED != Nintendo Switch
```

### Source Deduplication

다음은 중복으로 처리할 수 있습니다.

- 동일 normalized URL
- 동일 raw-content hash
- enrichment 이후 exact duplicate

강한 복제 관계가 있는 서로 다른 URL은 제거하지 않고 동일 dependency group에 배치할 수 있습니다.

같은 사이트라는 이유만으로 자동 dependent 처리하지 않습니다.

### Claim Grounding

AI가 생성한 claim은 반드시 evidence fragment와 연결되어야 합니다.

검증 과정에서 다음과 같은 claim은 제외될 수 있습니다.

- 제품과 직접 관계없는 주장
- 추측 또는 가정
- 인용문이 실제 evidence에 없음
- 사용 경험이 아닌 마케팅 문구
- source/evidence binding 불일치
- semantic verifier가 `UNCERTAIN` 또는 `REJECTED`

---

## 7. Confidence

ProofPick의 confidence는 **제품 점수**가 아니라 **현재 판단을 뒷받침하는 evidence confidence**입니다.

주요 구성 요소:

- evidence volume
- source independence
- source diversity
- claim agreement
- long-term evidence
- source/evidence quality

Confidence만으로 BUY를 강제하지 않습니다.

독립 support, risk, quality gate 등의 조건을 함께 봅니다.

---

## 8. 현재 Live 테스트

### AirPods Pro 2

최근 live run 중 하나:

```text
decision: BUY
confidence: 0.711809
counter_attempted: true
counter_completed: true
source_count: 21
```

다른 run에서는 검색/모델 결과 변동으로 `EARLY_ADOPTER`가 나온 사례도 있습니다.

현재 ProofPick은 외부 검색과 LLM 기반 extraction을 사용하므로 결과가 완전히 deterministic하지 않습니다.

### Logitech MX Master 3S

```text
decision: EARLY_ADOPTER
confidence: 0.463167
source_count: 8
```

초기 구현에서는 confidence가 0.0까지 떨어졌지만, product identity filtering과 evidence coverage 처리 개선 이후 usable evidence가 증가했습니다.

### Korean Community Boost

실제 live log에서 다음이 확인되었습니다.

```text
community_boost_attempted=True
community_query_count=3
community_source_count=12
```

즉 community boost 자체는 runtime에 연결되어 실제 검색을 수행하고 있습니다.

다만 각 community query가 어떤 국내 커뮤니티를 얼마나 안정적으로 반환하는지는 현재 추가 진단 중입니다.

---

## 9. 기술 스택

### Frontend

- Next.js
- TypeScript
- Tailwind CSS

### Backend

- Python
- FastAPI
- Pydantic

### Search

- Tavily Search API

### AI

- OpenAI API
- claim extraction
- semantic verification
- embeddings

현재 live configuration 예:

```text
OPENAI_CLAIM_MODEL=gpt-4.1-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

### Database

- Supabase PostgreSQL 예정

### Deployment

- Frontend: Vercel
- Backend: Railway

---

## 10. 프로젝트 구조

```text
proofpick/
├─ backend/
│  └─ app/
│     ├─ analysis_runtime/
│     ├─ claim_clustering/
│     ├─ claim_extraction/
│     ├─ confidence/
│     ├─ decision/
│     ├─ evidence_processing/
│     ├─ product_resolution/
│     ├─ query_generation/
│     ├─ search/
│     └─ source_filtering/
├─ frontend/
├─ scripts/
├─ tests/
├─ docs/
├─ PROJECT_SPEC.md
└─ AGENTS.md
```

---

## 11. 환경 변수

예시:

```env
TAVILY_API_KEY=
OPENAI_API_KEY=

OPENAI_CLAIM_MODEL=gpt-4.1-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EXTRACTION_TIMEOUT_SECONDS=90

FRONTEND_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

실제 API key는 `.env` 또는 배포 플랫폼의 secret 환경변수로 관리하며 Git에 commit하지 않습니다.

---

## 12. 로컬 실행

### Backend

```powershell
cd backend

.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

### Live smoke test

프로젝트 root에서:

```powershell
backend\.venv\Scripts\python.exe scripts\live_smoke.py "AirPods Pro 2"
```

예상 형식:

```json
{
  "http_status": 200,
  "initial_decision": "BUY",
  "decision": "BUY",
  "confidence": 0.711809,
  "counter_attempted": true,
  "counter_completed": true,
  "source_count": 21
}
```

---

## 13. 테스트

최근 #33 구현 완료 기준:

```text
관련 테스트: 98 passed
전체 테스트: 385 passed
git diff --check: passed
```

핵심 regression coverage:

- product identity resolution
- source deduplication
- evidence grounding
- semantic verification
- clustering
- confidence
- purchase decision
- counter evidence
- Korean community boost
- search budget
- runtime integration

---

## 14. 현재 상태

완료:

- [x] Backend API
- [x] Tavily search integration
- [x] Product identity resolution
- [x] Adaptive query generator 기반 구조
- [x] Source filtering / deduplication
- [x] Evidence cleaning / compression
- [x] Structured claim extraction
- [x] Semantic claim verification
- [x] Claim clustering
- [x] Evidence confidence
- [x] Purchase decision engine
- [x] Counter-evidence search
- [x] Frontend MVP
- [x] Live E2E
- [x] Search-assisted product identity
- [x] Evidence coverage reliability fix
- [x] Korean community search boost

진행 중:

- [ ] Korean community retrieval 품질 진단
- [ ] stable demo fixture 선정
- [ ] production deployment
- [ ] 최종 UI / visual polish
- [ ] README screenshot / GIF
- [ ] 발표 및 제출 자료 정리

---

## 15. 현재 알려진 한계

### 분석 속도

외부 검색, claim extraction, community boost, counter-evidence가 모두 실행될 경우 분석 시간이 길어질 수 있습니다.

일부 live 분석에서는 1~4분 수준의 latency가 관찰되었습니다.

### 검색 결과 변동성

Tavily 검색 결과와 LLM 기반 extraction은 매 실행마다 완전히 동일하지 않을 수 있습니다.

같은 제품도 확보되는 evidence에 따라 confidence와 decision이 달라질 수 있습니다.

### 국내 커뮤니티 색인 품질

ProofPick은 직접 사이트를 크롤링하지 않습니다.

따라서 디시인사이드, 에펨코리아, 더쿠, 아카라이브, 루리웹 검색 품질은 Tavily 및 각 사이트의 검색엔진 색인 상태에 영향을 받습니다.

### Product Identity

명확한 모델명도 검색 결과가 충분하지 않으면 fail-closed 방식으로 `PRODUCT_IDENTITY_UNRESOLVED`를 반환할 수 있습니다.

이는 잘못된 제품을 분석하는 것보다 분석을 중단하는 쪽을 선택한 설계입니다.

---

## 16. 제품 철학

ProofPick은 "AI가 정답을 알려주는 쇼핑 서비스"를 목표로 하지 않습니다.

대신 다음을 목표로 합니다.

> **검색은 넓게, 검증은 보수적으로, 판단 근거는 투명하게.**

제품에 대한 진실을 AI가 선언하지 않습니다.

웹과 커뮤니티의 여러 근거를 찾아 연결하고, 서로 독립적인지 확인하고, 반대되는 근거도 함께 보여준 뒤 사용자가 직접 판단할 수 있도록 돕습니다.

---

## 17. 향후 개선 방향

마감 이후 고려할 수 있는 개선:

- 부족한 evidence에 대한 adaptive 3 → 6 → 10 search
- 한국 커뮤니티 retrieval 품질 개선
- source별 장기 사용 신호 강화
- 결과 caching
- 분석 latency 최적화
- stable fixture / demo mode
- product alternatives
- Supabase persistence
- 분석 히스토리
- frontend source explorer
- screenshot / GIF 기반 README 개선

---

## 18. 한 줄 요약

**ProofPick은 제품 리뷰를 믿어주는 AI가 아니라, 구매 전에 믿을 만한 근거를 찾아 검증해주는 AI입니다.**
