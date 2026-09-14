# AGENTS.md

## 1. Project Identity

Project name: **ProofPick**

ProofPick is an AI-assisted purchase verification service.

The service does NOT claim to detect "truth" or definitively label reviews as fake.
Instead, it searches multiple public sources, extracts evidence, clusters repeated claims,
evaluates source diversity and evidence quality, and helps users make purchase decisions.

The core product principle is:

> Good products are not recommended because AI says so.
> They are recommended only when sufficient evidence supports the recommendation.

Secondary principles:

> Cheap by default, smart when uncertain.

> Retrieve once, compress once, reuse everywhere.

---

## 2. Source of Truth

The primary specification for implementation is:

- `PROJECT_SPEC.md`

The human-readable planning document is:

- `docs/ProofPick_AI_Championship_2026_Project_Plan_v2.docx`

When implementation decisions conflict:

1. Explicit user instruction in the current task
2. `PROJECT_SPEC.md`
3. `AGENTS.md`
4. Planning document in `docs/`
5. Existing code conventions

Do not silently override `PROJECT_SPEC.md`.

If an implementation requirement cannot be satisfied, document the reason clearly before changing the design.

---

## 3. Required Technology Stack

Unless explicitly instructed otherwise, use the following stack.

### Frontend
- Next.js
- TypeScript
- Tailwind CSS

### Backend
- Python
- FastAPI
- Pydantic

### Database
- Supabase PostgreSQL

### Deployment
- Frontend: Vercel
- Backend: Railway

### AI / Search
- Search provider abstraction
- LLM provider abstraction where practical
- Structured outputs only for machine-consumed LLM responses

Do NOT replace the stack with another framework without explicit approval.

Examples of forbidden unilateral changes:
- FastAPI -> Django
- Next.js -> React SPA / Vue
- Supabase -> Firebase
- Railway -> arbitrary alternative platform

---

## 4. MVP Scope

The required MVP flow is:

1. User enters a product name or product URL
2. Resolve the canonical product
3. Generate adaptive search queries
4. Search public web sources
5. Filter irrelevant and duplicate sources
6. Extract product claims
7. Cluster semantically similar claims
8. Evaluate cross-source support
9. Estimate evidence confidence
10. Produce one of the purchase states
11. If needed, find alternative products
12. Re-run the same verification pipeline on alternatives
13. Show supporting source links to the user

Required purchase states:

- `BUY`
- `BUY_IF`
- `SKIP`
- `EARLY_ADOPTER`

Do not add large unrelated features before the MVP is complete.

---

## 5. Product Safety / Trust Rules

Never make unsupported factual claims.

Do not state:

- "This review is fake."
- "This user is lying."
- "This company manipulates reviews."
- "This product definitely has defect X."

Prefer evidence-grounded language such as:

- "Commercial signals were detected."
- "This issue appeared repeatedly across multiple independent sources."
- "Evidence is currently insufficient."
- "This product remains in the early-adopter zone."
- "Long-term user evidence is limited."

Every major product claim shown to the user should be traceable to source evidence.

When evidence is insufficient, the correct behavior is uncertainty, not fabrication.

---

## 6. AI Harness Rules

The AI pipeline must optimize both quality and cost.

### 6.1 Cheap by default

Use deterministic code or low-cost methods whenever possible.

Use regular code for:

- URL normalization
- duplicate removal
- counting
- source statistics
- confidence formulas
- caching
- state transitions
- thresholds
- sorting
- filtering

Do not use an LLM for tasks that deterministic code can handle reliably.

### 6.2 Model routing

Use low-cost models for:

- product normalization
- simple relevance checks
- search query generation
- claim extraction
- sentiment / aspect tagging

Use stronger models only for:

- ambiguous evidence
- conflicting claims
- final purchase decision explanation
- difficult alternative comparison
- low-confidence verification

### 6.3 Confidence gate

Do not call a strong model by default.

Preferred pattern:

```text
cheap processing
      ↓
confidence evaluation
      ↓
high confidence ──────> continue
      ↓
low confidence
      ↓
strong verifier
```

### 6.4 Adaptive search budget

Do not run the maximum number of queries immediately.

Preferred search expansion:

```text
3 queries
   ↓
enough evidence? -> stop
   ↓ no
6 queries
   ↓
enough evidence? -> stop
   ↓ no
10 queries maximum
```

Search expansion should depend on:

- number of useful sources
- source diversity
- platform diversity
- long-term usage evidence
- evidence agreement

### 6.5 Evidence compression

Do NOT repeatedly send raw web pages to the LLM.

Preferred pipeline:

```text
raw page
  ↓
clean text
  ↓
relevant evidence
  ↓
structured claim JSON
```

After extraction, downstream stages should reuse structured evidence.

Raw content should only be revisited when necessary.

### 6.6 Batch extraction

Do not make one LLM call per document unless required.

Prefer bounded batches of multiple documents.

Each extracted claim must retain its `source_id`.

### 6.7 Semantic clustering

Use embeddings / similarity methods for first-pass grouping where practical.

The LLM may name or refine a cluster after grouping.

Avoid using an expensive LLM to compare every claim pair.

### 6.8 Counter-evidence search

The system should actively search for evidence that challenges its current conclusion.

If the initial evidence is highly positive, search for:

- problems
- failures
- regrets
- long-term issues
- defects

If the initial evidence is strongly negative, search for:

- positive long-term experience
- satisfied users
- situations where the product works well

The system should not only confirm its first hypothesis.

---

## 7. Evidence and Source Rules

Each source should have a stable internal ID.

Example:

```text
S001
S002
S003
```

Each claim should also have a stable internal ID.

Example:

```text
C001
C002
```

Claims should reference source IDs rather than repeating long URLs throughout the internal pipeline.

The UI may resolve source IDs back to URLs at render time.

Track at minimum:

- source URL
- domain
- title
- source type
- publication date if known
- commercial signal
- quality score
- content fingerprint if available

---

## 8. Source Independence

Do not treat copied content as independent evidence.

Possible duplicate / dependence signals:

- identical text
- high content similarity
- same quoted passage
- syndicated content
- same author
- same source domain
- same canonical URL

Prefer:

```text
20 pages found
↓
7 independent evidence groups
```

over claiming:

```text
20 independent reviewers agree
```

when independence is not established.

---

## 9. Claim Extraction

LLM extraction must use structured output.

Machine-consumed LLM output must never depend on free-form prose parsing when avoidable.

Preferred claim schema concept:

```json
{
  "source_id": "S001",
  "aspect": "battery",
  "claim": "Battery duration decreased after long-term use.",
  "sentiment": "negative",
  "severity": 3,
  "usage_period_months": 8
}
```

Use Pydantic models for validation.

If structured output fails validation:

1. Retry once with repair instructions
2. If still invalid, mark the extraction as failed
3. Do not silently accept malformed data

---

## 10. Decision Engine

The final decision must not be generated solely by an LLM.

The pipeline should combine deterministic metrics such as:

- evidence volume
- independent source count
- platform diversity
- long-term evidence
- agreement score
- severity
- commercial signal
- confidence

The LLM may explain the decision in natural language.

The decision engine should remain inspectable and testable.

---

## 11. Early Adopter Logic

When there is insufficient evidence, return:

`EARLY_ADOPTER`

Do not force a BUY or SKIP decision.

Possible signals:

- too few independent sources
- no long-term usage data
- product launched recently
- sources dominated by first-look / press / official marketing content

When possible, analyze the predecessor product separately.

Never transfer predecessor defects to the new product as facts.

Use language such as:

> The predecessor had recurring reports of X, but there is not yet enough evidence to conclude that the new model has the same issue.

---

## 12. Alternative Product Rules

Alternatives must not be recommended purely from popularity or LLM memory.

Required process:

```text
original product
      ↓
SKIP / major concern
      ↓
candidate alternatives
      ↓
run same verification pipeline
      ↓
only verified alternatives may be recommended
```

The key product rule is:

> Alternatives are verified too.

If an alternative lacks enough evidence, mark it as `EARLY_ADOPTER` instead of recommending it confidently.

---

## 13. Caching Rules

Caching is required for both cost and latency.

### Product-level cache

If a recent completed analysis exists:

- return cached analysis
- show analysis age
- allow explicit refresh

Initial TTL target:

- 24 hours

### Source-level cache

Store reusable extraction results using:

- normalized URL
- content hash
- extracted claims
- extraction version

If the same source content is seen again, avoid unnecessary LLM extraction.

### Analysis versioning

Cache keys should include pipeline / prompt version where necessary so old results can be invalidated safely.

---

## 14. Cost and Token Targets

Target for a new product analysis:

- Search queries: <= 10
- Useful sources: <= 30-40
- Strong-model calls: <= 2 under normal conditions
- Final natural-language generation: 1 call
- Repeated raw-context transmission: avoid

Target for a valid cache hit:

- Search calls: 0
- LLM calls: 0
- Database read only

Track token and cost metrics per analysis.

---

## 15. Observability

Record at minimum:

- analysis_id
- product_id
- number of search queries
- sources found
- sources used
- independent source groups
- input tokens
- output tokens
- estimated LLM cost
- search cost
- total latency
- cache hit / miss
- final decision
- confidence score
- pipeline version

Never log secrets or API keys.

---

## 16. Backend State Machine

Use explicit analysis states.

Recommended states:

- `queued`
- `resolving_product`
- `searching`
- `filtering_sources`
- `extracting_claims`
- `clustering_claims`
- `evaluating`
- `searching_counter_evidence`
- `finding_alternatives`
- `verifying_alternatives`
- `complete`
- `failed`

State changes should be explicit and persisted.

Do not infer state only from logs.

---

## 17. API Contract Discipline

Do not make breaking API changes silently.

If an API schema changes:

1. Update backend schema
2. Update frontend types
3. Update tests
4. Update `PROJECT_SPEC.md` if the contract materially changed

Prefer versioned Pydantic request / response models.

---

## 18. Database Discipline

Use migrations.

Do not manually mutate production tables without a migration plan.

Avoid storing full copyrighted web pages unless specifically required.

Prefer storing:

- metadata
- short evidence fragments
- claim structures
- URLs
- hashes
- analysis results

---

## 19. Testing Rules

No major feature is complete without tests.

Minimum expected test areas:

- product resolution
- source normalization
- duplicate filtering
- claim schema validation
- clustering
- confidence calculation
- decision engine
- early adopter logic
- alternative verification
- cache behavior

Use deterministic fixtures whenever possible.

Recommended fixture groups:

```text
tests/fixtures/
├── good_product.*
├── bad_product.*
├── early_adopter_product.*
├── ambiguous_product.*
└── duplicate_sources.*
```

Before completing a task:

- run relevant unit tests
- run formatter / linter if configured
- ensure no obvious regression

Do not declare success when tests fail.

---

## 20. Evaluation Harness

Prompt or model changes should be evaluated against a stable benchmark set.

Track metrics such as:

- claim recall
- unsupported claim rate
- source attribution accuracy
- decision consistency
- evidence diversity
- latency
- token usage
- estimated cost

A change is not automatically better because the prose sounds better.

Prefer measurable improvements.

Example comparison:

```text
Pipeline A
claim recall             81%
unsupported claims        8%
latency                  28s
cost                  $0.12

Pipeline B
claim recall             89%
unsupported claims        3%
latency                  19s
cost                  $0.07
```

Store benchmark outputs where practical.

---

## 21. Codex Working Rules

Work in small, reviewable tasks.

Do not attempt to implement the entire project in one pass.

Preferred task order:

1. project bootstrap
2. database / schemas
3. search provider
4. product resolver
5. query generator
6. source filtering
7. claim extraction
8. claim clustering
9. confidence engine
10. decision engine
11. counter-evidence search
12. alternative engine
13. API integration
14. frontend result flow
15. caching
16. observability
17. deployment
18. regression tests

One task should have one clear goal.

---

## 22. Before Editing Code

Before implementing a task:

1. Read `PROJECT_SPEC.md`
2. Read this `AGENTS.md`
3. Inspect relevant existing files
4. Identify existing tests
5. Preserve working architecture
6. Avoid unrelated refactoring

Do not rewrite working components merely because another design seems cleaner.

---

## 23. Change Scope

Keep changes narrow.

If asked to implement the claim extractor:

- implement claim extraction
- add tests
- update related schemas if necessary

Do NOT also redesign:

- frontend
- database
- deployment
- unrelated APIs

unless the task requires it.

---

## 24. Refactoring Rules

Refactoring is allowed only when it supports the current task or fixes a clear architectural problem.

Avoid:

- broad renaming
- moving directories without need
- replacing libraries without reason
- rewriting functioning modules

Prefer incremental improvement.

---

## 25. Dependency Rules

Before adding a new dependency, ask:

1. Can the current stack already do this?
2. Is the dependency maintained?
3. Does it materially reduce implementation risk?
4. Does it increase deployment complexity?
5. Is its license acceptable?

Do not add large frameworks for small utilities.

---

## 26. Secret Management

Never commit:

- API keys
- database passwords
- service role keys
- access tokens
- private credentials

Use environment variables.

Maintain:

- `.env.example`

Never include real credentials in `.env.example`.

---

## 27. Frontend UX Rules

The product should feel trustworthy, not sensational.

Avoid UI language such as:

- FAKE!
- SCAM!
- DO NOT BUY!
- 100% TRUE REVIEW

Prefer:

- repeated issue
- limited evidence
- high confidence
- mixed feedback
- long-term concern
- alternative worth considering

Every important claim should expose a path to supporting sources.

---

## 28. Loading / Progress UX

Analysis may take time.

Show meaningful progress states, such as:

- identifying product
- searching real-world usage evidence
- removing duplicate sources
- extracting repeated claims
- checking counter-evidence
- evaluating confidence
- verifying alternatives

Do not use fake random progress percentages.

Progress should reflect actual pipeline stages.

---

## 29. Performance Priorities

Optimization priority order:

1. Correctness
2. Evidence traceability
3. Reliability
4. Latency
5. Cost
6. Visual polish

Do not sacrifice evidence integrity to save a small number of tokens.

Do not use expensive models where deterministic logic is sufficient.

---

## 30. Error Handling

External APIs will fail.

Handle:

- search API timeout
- search rate limit
- LLM timeout
- invalid structured output
- empty search result
- database failure
- partial pipeline failure

Return user-friendly states.

Do not expose raw stack traces to users.

Store enough internal error context for debugging without storing secrets.

---

## 31. Definition of Done

A feature is complete when:

- implementation matches `PROJECT_SPEC.md`
- relevant tests pass
- structured schemas validate
- no secrets are committed
- failure states are handled
- cost / token impact is considered
- documentation is updated if contracts changed

The MVP is complete when a user can:

1. enter a product
2. receive evidence-backed claims
3. inspect source links
4. see evidence confidence
5. receive BUY / BUY_IF / SKIP / EARLY_ADOPTER
6. receive verified alternatives when appropriate

---

## 32. Explicit Non-Goals for the Hackathon MVP

Do not prioritize these before the core MVP is stable:

- user accounts
- social login
- mobile application
- browser extension
- price tracking
- notification system
- full e-commerce scraping infrastructure
- custom model training
- complex recommendation ML
- administrator dashboard
- broad personalization

These may be added after submission.

---

## 33. Final Rule

When uncertain about implementation direction:

> Prefer the smallest implementation that preserves evidence quality, testability, and the architecture defined in `PROJECT_SPEC.md`.

Do not optimize for cleverness.

Optimize for a working, trustworthy, demonstrable hackathon product.
