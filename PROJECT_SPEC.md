# ProofPick - PROJECT_SPEC

## 1. Product Goal
ProofPick is an evidence-grounded AI purchase verification service. A user enters a product name or shopping URL. The system searches public web sources, extracts repeated real-use claims, measures evidence quality across independent sources, avoids forced conclusions when evidence is weak, and re-verifies alternatives when the original product appears problematic.

Core principle:
- Do not claim to detect "truth" or definitively label reviews as fake.
- Prefer evidence aggregation and cross-source consistency.
- Every major claim shown to the user must trace back to real source IDs/URLs.
- If evidence is insufficient, return EARLY_ADOPTER / insufficient evidence.
- Alternatives must pass the same verification pipeline.

## 2. MVP Decisions
Final states:
- BUY
- BUY_IF
- SKIP
- EARLY_ADOPTER

ALTERNATIVE is a follow-up action/result group, not a substitute for the original decision.

MVP must support:
1. Product name or URL input.
2. Product resolution/normalization.
3. Public web search.
4. Source filtering and deduplication.
5. Claim extraction.
6. Claim clustering.
7. Evidence/confidence calculation.
8. Final purchase state.
9. Source links for each important claim.
10. Alternative discovery and re-verification for SKIP cases.
11. Public deployment without login.

Do not build in MVP:
- user accounts
- payment
- full price tracking
- browser extension
- dedicated crawler for every community
- custom ML model training
- fake-review binary classifier
- Redis/Celery unless strictly required

## 3. Tech Stack
Frontend:
- Next.js
- TypeScript
- Tailwind CSS
- Vercel

Backend:
- Python
- FastAPI
- Pydantic
- Railway

Database:
- Supabase PostgreSQL

External services:
- SearchProvider interface; initial provider Tavily, fallback-ready design
- OpenAI API for LLM tasks
- Embeddings provider behind an interface

## 4. Repository Layout
```text
proofpick/
├─ AGENTS.md
├─ README.md
├─ frontend/
├─ backend/
├─ docs/
│  ├─ ARCHITECTURE.md
│  ├─ API.md
│  ├─ DATABASE.md
│  ├─ AI_PIPELINE.md
│  ├─ RULES.md
│  └─ TASKS/
├─ tests/
│  └─ fixtures/
└─ supabase/
   └─ migrations/
```

## 5. Codex Working Rules
Codex must:
- read AGENTS.md first
- implement one TASK file at a time
- preserve existing API contracts unless the task explicitly changes them
- add/update tests for behavior changes
- run relevant tests before considering a task complete
- use Pydantic structured outputs for LLM responses
- never parse free-form LLM output with fragile regex when a schema can be used
- avoid adding new infrastructure unless a concrete requirement demands it
- keep secrets in environment variables
- never expose API keys to the frontend

Task sequence:
1. 001-project-bootstrap
2. 002-search-provider
3. 003-product-resolver
4. 004-query-generator
5. 005-source-filter
6. 006-evidence-compressor
7. 007-claim-extractor
8. 008-claim-clustering
9. 009-confidence-engine
10. 010-decision-engine
11. 011-counter-evidence
12. 012-alternative-engine
13. 013-result-ui
14. 014-cache-telemetry
15. 015-evaluation-harness
16. 016-deployment-regression

## 6. API Contract
### POST /api/analyses
Request:
```json
{
  "query": "product name or URL"
}
```
Response:
```json
{
  "analysis_id": "uuid",
  "status": "queued"
}
```

### GET /api/analyses/{id}
Returns progress and final result.

Status machine:
```text
queued
-> resolving
-> searching
-> filtering
-> extracting
-> clustering
-> verifying
-> evaluating
-> alternatives
-> complete
or failed
```

### GET /api/analyses/{id}/sources
Returns source metadata and URLs.

### GET /api/analyses/{id}/claims
Returns clustered claims with evidence references.

### POST /api/analyses/{id}/alternatives
Triggers or returns alternative analysis for eligible cases.

## 7. Core Data Model
### products
- id
- name
- brand
- category
- model
- canonical_name
- created_at

### analyses
- id
- product_id
- status
- decision
- confidence
- summary
- pipeline_version
- created_at
- completed_at

### sources
- id
- analysis_id
- source_code (S001 etc.)
- url
- domain
- title
- published_at
- source_type
- content_hash
- commercial_signal
- quality_score
- independent_group_id

### claims
- id
- analysis_id
- claim_code (C001 etc.)
- aspect
- canonical_claim
- sentiment
- severity
- independent_source_count
- platform_count
- confidence

### claim_sources
- claim_id
- source_id
- evidence
- usage_period

### alternatives
- analysis_id
- alternative_product_id
- reason
- rank
- analysis_id_of_alternative

## 8. LLM Schemas
### ProductResolution
```json
{
  "brand": "string|null",
  "product": "string",
  "model": "string|null",
  "generation": "string|null",
  "category": "string|null",
  "canonical_name": "string",
  "ambiguous": false,
  "candidates": []
}
```

### ExtractedClaim
```json
{
  "source_id": "S001",
  "aspect": "battery",
  "claim": "Long-term battery life decreases",
  "sentiment": "negative",
  "severity": 3,
  "usage_period_months": 8,
  "evidence": "short supporting fragment"
}
```

Constraints:
- evidence must be supported by the source text
- no invented URL or source ID
- severity should represent practical impact, not emotional tone

## 9. AI Harness Architecture
Pipeline:
```text
Input
-> Product Cache Check
-> Product Resolver
-> Adaptive Query Generator
-> Search Provider
-> Source Dedup / Filter
-> Evidence Compressor
-> Cheap Claim Extractor
-> Embedding Clusterer
-> Confidence Gate
-> Strong Verifier only if uncertain
-> Counter-Evidence Search
-> Deterministic Confidence / Decision
-> Alternative Finder + same pipeline
-> Final Writer
```

Principles:
- Cheap by default, smart when uncertain.
- Retrieve once, compress once, reuse everywhere.
- Use code for deterministic work.
- Use strong LLMs only behind a confidence gate.
- Generate polished natural language only once at the end.

## 10. Adaptive Query Budget
Start with 3 core queries.
Expand only if evidence is insufficient.

Suggested stages:
- Stage A: 3 queries
- Stage B: up to 6 queries
- Stage C: up to 10 queries

Example stopping condition:
- >= 25 relevant sources OR
- >= 3 independent platforms AND sufficient claim coverage

Counter-evidence stage:
- if initial result is strongly positive: search problem/failure/regret/long-term terms
- if strongly negative: search satisfaction/benefit/recommendation terms

## 11. Source Processing
Before LLM use:
- canonicalize URLs
- exact duplicate removal
- content-hash duplicate removal
- remove navigation/footer/ads/recommendation widgets where possible
- discard low-content pages
- reject clearly irrelevant pages

Source independence indicators:
- same content hash
- high embedding similarity
- same domain repetition
- same author where detectable
- copied quote blocks

Repeated copies do not count as independent evidence.
Unknown independence is not confirmed support. Incremental filtering within one analysis must share an analysis-local identity registry so source/group IDs remain collision-free and duplicates reconcile to a stable representative.

## 12. Evidence Compression
Never repeatedly pass full source pages into downstream LLM calls.

Store compact evidence:
```json
{
  "source_id": "S012",
  "claims": [...],
  "metadata": {
    "domain": "...",
    "published_at": "...",
    "commercial_signal": 0.2
  }
}
```

Downstream steps operate on evidence objects. Fetch original text only when a verifier explicitly needs it.

## 13. Model Routing
Cheap model tasks:
- product normalization
- query generation
- relevance classification
- claim extraction
- sentiment/aspect tagging

Strong model tasks:
- ambiguous product disambiguation
- conflicting evidence adjudication
- low-confidence claim verification
- BUY_IF vs SKIP boundary cases
- final comparison wording
- final human-readable summary

Target high-end model calls per new analysis: <= 2.

## 14. Claim Clustering
Preferred approach:
1. embed claim text
2. group semantically similar claims by cosine similarity / clustering
3. generate one canonical cluster label
4. compute independent source count and platform diversity in code

Do not use one LLM call per claim.
Only VERIFIED grounded claims participate downstream. Clusters must enforce internal coherence rather than merging a similarity chain whose endpoints are unrelated.

## 15. Confidence Engine
Confidence is deterministic, not an LLM opinion.

Initial conceptual factors:
- evidence volume
- independent source count
- platform diversity
- agreement ratio
- long-term usage evidence
- source quality
- duplicate penalty
- commercial-signal penalty

Example conceptual formula:
```text
confidence =
  0.25 * source_sufficiency
+ 0.20 * source_independence
+ 0.20 * platform_diversity
+ 0.20 * agreement
+ 0.15 * long_term_evidence
- penalties
```

Weights are configurable and must be evaluated with fixtures before being treated as stable.

## 16. Confidence Gate
Skip strong verification if:
- sufficient independent sources
- multi-platform agreement
- claim cluster confidence above threshold

Invoke verifier if:
- small source count
- one-platform concentration
- conflicting claims
- weak product identity
- decision near BUY_IF/SKIP boundary

## 17. Decision Engine
Decision logic must consider both product evidence and evidence quality.

EARLY_ADOPTER when:
- too few usable sources
- no meaningful long-term evidence for a new product
- independent-source diversity is too low

SKIP should require meaningful repeated negative evidence, not one dramatic post.

BUY should require adequate evidence quality and affirmative independent support, not merely the absence of blocking issues. Neutral-only evidence cannot default to BUY, and unresolved severe risks must remain visible and block BUY without automatically forcing SKIP.

BUY_IF when benefits are credible but important caveats depend on user context.

## 18. Alternative Engine
Run only when useful, especially SKIP.

Steps:
1. derive product category, approximate price band, must-have features
2. discover candidate products
3. run candidates through the same verification pipeline
4. exclude candidates with insufficient evidence
5. return 1-2 strongest verified alternatives

Never recommend an alternative solely from the LLM's prior knowledge.

## 19. Caching
Product cache:
- reuse complete analysis for a configurable TTL, initial value 24h
- allow manual refresh

Source cache:
- key by URL + content hash
- reuse extraction when unchanged

Cache hit goal:
- 0 searches
- 0 LLM calls
- DB read only

## 20. Cost and Token Budget
Target per uncached product analysis:
- search queries <= 10
- relevant source candidates <= 30-40
- total LLM calls <= 8
- strong-model calls <= 2

Telemetry fields:
- analysis_id
- search_query_count
- sources_found
- sources_used
- input_tokens
- output_tokens
- estimated_llm_cost
- estimated_search_cost
- latency_ms
- cache_hit
- decision
- confidence
- pipeline_version

## 21. Evaluation Harness
Maintain representative fixtures:
- good_product
- bad_product
- new_product
- ambiguous_product
- contradictory_product

Each fixture may define:
```json
{
  "required_claims": [],
  "forbidden_claims": [],
  "acceptable_decisions": ["BUY_IF", "SKIP"]
}
```

Track:
- claim recall
- unsupported claim rate
- source attribution accuracy
- decision consistency
- cost per analysis
- latency

Prompt/model changes should be compared against a baseline before merge.

## 22. Test Strategy
Required tests:
- URL normalization
- exact/content duplicate detection
- source independence grouping
- confidence scoring
- EARLY_ADOPTER threshold behavior
- decision boundary behavior
- alternative re-verification
- cache behavior
- invalid LLM schema handling
- missing/failed external API behavior

All tests must avoid real paid API calls by default. Use fixtures/mocks.

## 23. UI Requirements
Landing:
- one product/URL input
- one clear CTA
- 3 demo examples

Progress:
- show current pipeline stage
- show number of sources found where meaningful

Result:
- decision badge
- one-sentence summary
- evidence confidence breakdown
- repeated pros/cons
- independent source count
- clickable source evidence
- EARLY_ADOPTER explanation when applicable
- alternative CTA when applicable

Alternatives:
- original vs 1-2 verified alternatives
- show evidence sufficiency for each
- explain why each alternative is recommended

## 24. Safety / Product Language Rules
Allowed language:
- "commercial signals are high"
- "this issue appears repeatedly across independent sources"
- "evidence is insufficient"
- "requires further verification"

Avoid unsupported categorical language:
- "this review is fake"
- "this seller manipulates reviews"
- "this product definitely has defect X"

The product should expose uncertainty.

## 25. Definition of Done for MVP
The MVP is done when all are true:
1. user can submit a product name
2. real public web search runs
3. at least 10 relevant sources can be collected for a known test product
4. repeated claims are extracted and clustered
5. every major displayed claim links to source evidence
6. evidence sufficiency is computed
7. one of BUY / BUY_IF / SKIP / EARLY_ADOPTER is returned
8. SKIP can discover and re-verify at least one alternative
9. public Vercel URL works without login
10. representative demo cases are cached
11. token/cost/latency telemetry is logged
12. regression tests pass

## 26. Demo Cases
Prepare at least:
- one well-reviewed, evidence-rich product
- one product with repeated significant issues and verified alternative
- one newly launched / low-evidence product that returns EARLY_ADOPTER

The demo must remain usable even if a live external search provider temporarily fails; cached representative analyses may be shown as demo examples.
