# ProofPick

> **AI는 진실을 판정하지 않고, 근거를 찾아 정리합니다.**

ProofPick은 AI가 제품의 진실을 선언하는 대신, 여러 공개 출처의 근거를 모아 구매 판단을 돕는 서비스입니다.

[Live Demo](https://proofpick.vercel.app) · [Backend Health](https://proofpick-production.up.railway.app/health) · [GitHub](https://github.com/eugene-82/proofpick)

## Why ProofPick

쇼핑몰 리뷰 하나만으로는 편향이나 장기 사용 문제를 충분히 보기 어렵습니다. 커뮤니티, 블로그, 영상, 공식 정보는 서로 흩어져 있고, 생성형 AI가 이 자료를 하나의 확정적인 답처럼 말하면 오히려 판단을 흐릴 수 있습니다.

ProofPick은 다음 원칙으로 이 문제를 다룹니다.

- 여러 공개 출처에서 실제 사용 근거를 찾습니다.
- 문서 전체를 단순 요약하지 않고 claim 단위로 구조화합니다.
- 복제된 글과 서로 독립적인 출처를 구분합니다.
- 첫 판단을 반박할 수 있는 counter-evidence도 검색합니다.
- 근거가 충분하지 않으면 결론을 강제하지 않고 `EARLY_ADOPTER`로 남깁니다.
- 화면에 표시한 주요 근거를 실제 출처 URL과 연결합니다.

## Core Flow

```mermaid
flowchart LR
    A[제품명 또는 URL] --> B[제품 식별과 Canonicalization]
    B --> C[검색 Query 생성]
    C --> D[공개 출처 검색]
    D --> E[관련성 필터와 중복 처리]
    E --> F[Evidence 정리]
    F --> G[Claim 추출과 Grounding]
    G --> H[Claim Clustering]
    H --> I[Evidence Confidence와 Initial Decision]
    I --> J[조건부 Community 또는 Counter-Evidence 검색]
    J --> K[전체 근거 재평가와 Final Decision]
```

검색 결과는 URL/content identity와 dependency group을 기준으로 정리됩니다. 검증된 claim만 clustering, confidence, decision 단계로 전달되며, 근거가 부족한 경우에는 검색을 무리하게 긍정 결론으로 바꾸지 않습니다.

## Decision System

| Decision | 의미 |
| --- | --- |
| `BUY` | 현재 확보한 독립 근거에서 구매를 막을 만한 반복적 문제가 충분히 확인되지 않은 상태 |
| `BUY_IF` | 장점은 확인되지만 사용 조건이나 주의할 리스크를 함께 봐야 하는 상태 |
| `SKIP` | 여러 독립 근거에서 구매를 재고할 만한 문제가 반복적으로 확인된 상태 |
| `EARLY_ADOPTER` | 일반적인 구매 판단을 내리기에 독립적 사용 근거가 아직 충분하지 않은 상태 |

`EARLY_ADOPTER`는 오류나 낮은 제품 점수가 아닙니다. 현재 수집된 evidence로는 `BUY`, `BUY_IF`, `SKIP` 중 하나를 충분한 근거로 제시하기 어렵다는 뜻입니다.

### Evidence Confidence

`LOW`, `MEDIUM`, `HIGH`는 제품 품질 점수가 아니라 **현재 판단을 뒷받침하는 근거 신뢰도**입니다. 근거량, 출처 독립성, 출처 다양성, claim 간 합의, 관찰 기간, evidence quality 등을 함께 반영합니다.

## Key Features

- **Multi-source research**: 한 쇼핑몰에 한정하지 않고 공개 웹 자료를 검색
- **Bounded adaptive search**: 초기 검색 후 근거 상태와 판단에 따라 한국 커뮤니티 또는 반대 근거 검색을 제한적으로 추가
- **Korean community search**: 근거가 부족할 때 국내 커뮤니티 검색 query로 보강
- **Evidence grounding**: claim의 subject, predicate, polarity와 실제 evidence 연결을 검증
- **Source independence**: URL, content hash, dependency lineage를 이용해 복제 출처의 support 부풀림 방지
- **Counter-evidence**: 초기 판단과 반대 방향의 자료를 찾은 뒤 전체 근거를 재평가
- **Conservative fallback**: 제품 identity나 근거 integrity가 불확실하면 강제 결론 대신 명시적 오류 또는 불확실성 반환
- **Provenance links**: claim과 출처 URL을 결과 화면에서 확인 가능
- **Product catalog**: 제출 데모용 canonical product와 한국어·영어 SAFE alias를 exact lookup으로 정규화
- **Responsive and accessible UI**: 모바일 대응, keyboard submit, visible focus, semantic controls, reduced-motion 지원

## Example Inputs

다음과 같은 명확한 제품명을 입력해 분석할 수 있습니다.

```text
Apple AirPods Pro 3
Logitech MX Master 4
Nintendo Switch 2
```

ProofPick은 실시간 검색과 모델 기반 extraction을 사용합니다. 따라서 decision, confidence, sources는 실행 시점의 검색 결과에 따라 달라질 수 있습니다.

## Architecture

```text
Browser
  ↓
Next.js + TypeScript + Tailwind CSS (Vercel)
  ↓  POST /api/analyses
FastAPI + Pydantic (Railway)
  ├─ Product catalog / resolver
  ├─ Query generation
  ├─ Source registry / filtering / evidence processing
  ├─ Claim extraction / grounding / clustering
  ├─ Confidence / decision / counter-evidence
  ├─ Tavily Search API
  └─ OpenAI API
```

현재 live demo는 하나의 동기식 분석 요청으로 실행됩니다. PostgreSQL/Supabase 호환 초기 schema와 migration은 저장소에 있지만, live 분석 경로는 remote database persistence를 사용하지 않습니다.

## Tech Stack

| 영역 | 기술 |
| --- | --- |
| Frontend | Next.js, TypeScript, Tailwind CSS |
| Backend | Python, FastAPI, Pydantic |
| Search | Tavily Search API |
| AI | OpenAI Responses API, structured claim extraction, embeddings |
| Database foundation | Supabase-compatible PostgreSQL migration |
| Deployment | Vercel, Railway |
| Testing | pytest, deterministic offline fixtures, Next.js production build |

## Local Setup

필수 조건은 Node.js/npm과 Python 3입니다. 실제 secret은 Git에 저장하지 말고 로컬 환경변수 또는 `backend/.env`에만 둡니다. 지원하는 변수는 루트의 [`.env.example`](.env.example)을 참고하세요.

### 1. Backend

```bash
cd backend
python -m venv .venv
```

가상환경 활성화:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

의존성 설치와 서버 실행:

```bash
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

`backend/.env` 예시:

```env
TAVILY_API_KEY=<your-tavily-key>
OPENAI_API_KEY=<your-openai-key>
OPENAI_CLAIM_MODEL=gpt-4.1-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EXTRACTION_TIMEOUT_SECONDS=90
FRONTEND_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Windows PowerShell에서는 다음 명령도 사용할 수 있습니다.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

### 2. Frontend

새 터미널에서:

```bash
cd frontend
npm install
npm run dev
```

`frontend/.env.local`:

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

브라우저에서 <http://localhost:3000>을 엽니다. `NEXT_PUBLIC_*` 변수에는 공개 backend URL만 넣고 Tavily/OpenAI key를 넣지 마세요.

### 3. Optional Live Smoke

backend가 실행 중일 때 저장소 루트에서:

```bash
python scripts/live_smoke.py "Apple AirPods Pro 3"
```

스크립트는 HTTP status, initial/final decision, confidence, counter-evidence 상태, source count만 출력하며 key나 원문 evidence를 출력하지 않습니다.

## Environment Variables

| 변수 | 위치 | 필수 여부 | 설명 |
| --- | --- | --- | --- |
| `TAVILY_API_KEY` | Backend | Live 분석 필수 | Tavily 검색 provider key |
| `OPENAI_API_KEY` | Backend | Live 분석 필수 | Claim extraction과 embedding provider key |
| `OPENAI_CLAIM_MODEL` | Backend | 선택 | Claim extraction model override |
| `OPENAI_EMBEDDING_MODEL` | Backend | 선택 | Embedding model override |
| `OPENAI_EXTRACTION_TIMEOUT_SECONDS` | Backend | 선택 | 단일 extraction 요청 timeout, 기본 90초 |
| `FRONTEND_ORIGINS` | Backend | 로컬 기본값 있음 | 허용할 browser origin 목록, production에서는 명시 필요 |
| `NEXT_PUBLIC_API_BASE_URL` | Frontend | Production 필수 | 브라우저가 호출할 공개 backend URL |

## Deployment

- **Frontend (Vercel)**: <https://proofpick.vercel.app>
- **Backend (Railway)**: <https://proofpick-production.up.railway.app>
- **Health**: <https://proofpick-production.up.railway.app/health>

Vercel은 `frontend`를 root directory로 사용하고 `NEXT_PUBLIC_API_BASE_URL`로 Railway URL을 받습니다. Railway는 `backend`를 root directory로 사용하며 다음 command로 시작합니다.

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Production CORS는 Railway의 `FRONTEND_ORIGINS`에 Vercel origin을 정확히 등록합니다. 상세 배포와 진단 절차는 [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)를 참고하세요.

## Reliability Principles

- **No truth oracle**: AI가 리뷰의 진위나 제품의 절대적 진실을 판정한다고 주장하지 않습니다.
- **Provenance first**: 주요 claim은 실제 source/evidence identity와 연결되어야 합니다.
- **Independent support**: 복제 문서는 여러 독립 근거처럼 계산하지 않습니다.
- **Semantic boundary**: 일반 자연어 관계 판정은 structured semantic verdict를 통과해야 합니다.
- **Counter-evidence**: 첫 판단을 확인하는 자료뿐 아니라 반박할 자료도 찾습니다.
- **Conservative fallback**: 불확실성을 숨기기보다 `EARLY_ADOPTER` 또는 명시적 실패로 드러냅니다.
- **Identity guard**: 제품 세대, variant, model number가 충돌하면 잘못된 제품 분석을 강제하지 않습니다.

## Tests

기본 backend test suite는 외부 Tavily/OpenAI 호출 없이 deterministic fake와 fixture로 실행됩니다.

```bash
# macOS / Linux, repository root
PYTHONPATH=backend backend/.venv/bin/python -m pytest -p no:cacheprovider -q
```

```powershell
# Windows PowerShell, repository root
$env:PYTHONPATH = "backend"
backend\.venv\Scripts\python.exe -m pytest -p no:cacheprovider -q
```

Frontend production validation:

```bash
cd frontend
npm run build
```

## Known Limitations

- 실시간 분석은 외부 검색, claim extraction, community 보강, counter-evidence까지 수행하므로 수 분 걸릴 수 있습니다.
- 검색 결과와 최종 판단은 검색엔진 색인 상태와 실행 시점에 따라 달라질 수 있습니다.
- 한국어 product alias는 제출용 catalog의 exact SAFE alias 중심이며, 모든 제품군을 포괄하는 다국어 fuzzy canonicalization은 아닙니다.
- 일부 커뮤니티는 Tavily와 검색엔진의 노출 상태에 따라 검색 결과 편차가 큽니다.
- 현재 live demo는 synchronous request이며 caching, background queue, analysis history를 제공하지 않습니다.
- 결과는 구매 참고 자료이며 제품 품질에 대한 절대적 판정이나 보증이 아닙니다.

## Roadmap

제출 이후 검토할 개선 방향입니다.

- multilingual product entity normalization과 catalog coverage 확대
- caching과 asynchronous analysis로 latency 개선
- richer autocomplete와 product discovery
- community retrieval 품질 개선
- visual regression과 더 넓은 end-to-end test coverage
- persistence와 분석 history

## Project Status

- Production frontend/backend deployed
- Production E2E verified
- Counter-evidence와 Korean community 보강 경로 연결
- Submission catalog canonicalization과 responsive UI 적용
- Backend reliability 동결, 현재 focus는 submission/demo polish

---

ProofPick은 사용자를 대신해 진실을 선언하지 않습니다. **검색은 넓게, 검증은 보수적으로, 판단 근거는 투명하게** 제공하는 것을 목표로 합니다.
