# TASK 011A — Core Reliability Hardening

## Purpose

TASK 011과 TASK 012 사이에 삽입하는 신뢰성 보강 작업이다.

목표는 새 기능 추가가 아니라, 중간 Red Team 감사에서 발견된 핵심 correctness 문제를 TASK 012의 검색 확대 전에 수정하는 것이다.

핵심 위험:
- 복제/근복제 콘텐츠가 독립 근거로 부풀려지는 문제
- substring 수준 grounding이 허구 claim을 통과시키는 문제
- BUY가 사실상 기본 fallback이 되는 문제
- severity가 중복/희석에 취약한 문제
- connected-components chaining으로 무관한 claim이 하나의 반복 이슈가 되는 문제
- 제품 identity/relevance 오류
- evidence compression에서 핵심 문맥/부정어 손실
- usage period 오인
- TASK 012 증분 검색 시 source/group ID 충돌

TASK 012는 이 작업의 acceptance criteria를 통과하기 전 시작하지 않는다.

---

## 1. Global Reliability Invariants

### 1.1 Independence
- Unknown independence를 confirmed independence로 자동 간주하지 않는다.
- 서로 다른 URL/도메인이라는 이유만으로 독립 근거로 세지 않는다.
- exact duplicate와 강한 near-duplicate는 `independent_source_count`, cluster support, confidence, decision threshold를 부풀리면 안 된다.
- 같은 domain도 서로 다른 실제 게시물이라면 자동 duplicate 처리하지 않는다.

### 1.2 Claim Grounding
- claim은 짧은 fragment가 원문에 존재한다는 이유만으로 decision-driving evidence가 되면 안 된다.
- 최소한 source consistency, context-rich fragment, polarity, subject, direct-experience 여부를 검증한다.
- 안전하게 지지 여부를 확정할 수 없으면 `UNCERTAIN` 또는 동등 상태로 두고 일반 decision-driving evidence에서 제외한다.

### 1.3 BUY Safety
- `SKIP도 아니고 BUY_IF도 아니면 BUY` 패턴을 금지한다.
- BUY는 충분한 evidence와 명시적 positive/useful support를 요구한다.
- neutral/descriptive evidence만으로 BUY하지 않는다.
- unresolved severe risk가 있으면 overconfident BUY를 금지한다.

### 1.4 Severe Risk Preservation
- severity 5 단일 신고 하나로 바로 SKIP하지 않는다.
- 그러나 반복 지지가 없다고 severe risk 자체를 버리지 않는다.
- unresolved severe risk는 구조화된 결과로 보존해 TASK 012/013이 재검증할 수 있게 한다.

### 1.5 Duplicate Invariance
- dependent/duplicate source를 추가해도 issue severity/support, confidence, decision이 실질적으로 변하지 않아야 한다.

### 1.6 Snapshot Safety
- confidence/decision은 동일한 analysis snapshot의 source/claim/provenance를 사용해야 한다.

---

## 2. Phase A — Critical Fixes

### A1. Source Independence Hardening

기존 exact check를 유지한다.
- normalized URL duplicate
- exact content hash duplicate

추가로 deterministic한 conservative near-duplicate/dependency 판별을 도입한다.

가능한 신호:
- cleaned content fingerprint
- normalized paragraph set
- token/shingle overlap
- stable similarity over cleaned text
- 원출처 metadata가 있다면 활용

금지:
- vector DB
- LLM dependency 판단

필수 테스트:
1. exact URL duplicate
2. exact content duplicate
3. HTML wrapper만 다른 복제
4. footer만 다른 복제
5. cross-domain copied content
6. same domain의 서로 다른 실제 post
7. duplicate 추가 시 independent support 불변
8. duplicate 추가 시 severity/decision 불변

---

### A2. Claim Grounding Hardening

다음은 반드시 실패해야 한다.

Source:
`The battery lasts all day.`

fragment:
`battery`

claim:
`The battery catches fire.`

작은 명시적 grounding state를 둔다.

권장:
- `VERIFIED`
- `UNCERTAIN`
- `REJECTED`

동등한 이름 사용 가능.

검증 후보:
- source_id consistency
- normalized fragment containment
- 최소 meaningful fragment 길이/토큰 수
- negation/polarity mismatch
- subject mismatch
- third-party report marker
- speculation marker
- obvious marketing/spec-only text

거대한 regex ontology는 만들지 않는다.

불확실하면 `VERIFIED`로 승격하지 않는다.

필수 테스트:
1. supported claim
2. unsupported semantic claim
3. negation reversal
4. quoted third-party opinion
5. explicit non-experience
6. tiny fragment
7. Korean grounded claim
8. marketing + real usage 혼합
9. source ID mismatch
10. uncertain claim이 SKIP/BUY를 만들지 않음

---

### A3. Decision BUY Safety

권장 decision 흐름:

1. evidence insufficient
   -> EARLY_ADOPTER

2. repeated + independent + severe negative
   -> SKIP

3. repeated conditional negative
   -> BUY_IF

4. unresolved severe risk 존재
   -> BUY 금지

5. sufficient positive/useful support + no blocking issue + no unresolved major conflict
   -> BUY

6. 그 외
   -> conservative non-BUY 결과

결과에는 필요하면 다음을 보존한다.
- blocking_issues
- conditions
- unresolved_risks
- supporting_signals

필수 테스트:
1. neutral/descriptive source 3개 -> BUY 금지
2. low-evidence positive -> EARLY_ADOPTER
3. 충분한 positive support + risk 없음 -> BUY
4. severity 5 단일 신고 + unrelated positive 다수 -> overconfident BUY 금지
5. repeated independent severity 4 issue -> SKIP
6. BUY_IF는 meaningful condition 보유
7. unresolved severe risk provenance 보존

---

## 3. Phase B — Error Amplification Fixes

### B1. Severity Aggregation by Independence Group

source-level naive average를 SKIP 핵심 신호로 쓰지 않는다.

최소 파생값:
- independent_source_count
- high_severity_independent_support
- max_severity
- independence-group 기반 severity distribution 또는 robust aggregate

예:
`[4,4,4,4]`에 unrelated severity 1이 추가됐다고 중대 반복 이슈가 사라지면 안 된다.

동일 independence group의 severity 5 URL 복제가 threshold를 올리면 안 된다.

필수 테스트:
- `[4,4,4,4]` vs `[4,4,4,4,1]`
- 같은 IG duplicate URLs
- severity 5 outlier 1개
- severity 4 independent reports 4개
- 한 IG 안의 다수 복제

---

### B2. Claim Clustering Chaining Guard

다음 실패를 막는다.

A~B >= threshold
B~C >= threshold
C~D >= threshold
A~D unrelated

이 구조가 내부 coherence 확인 없이 한 cluster/support=4가 되면 안 된다.

허용 접근:
- incremental medoid/centroid assignment
- connected components + post-validation
- member-to-medoid minimum similarity
- maximum internal distance guard

금지:
- vector DB
- pairwise LLM judge

필수:
- deterministic ordering
- stable cluster IDs
- provenance 보존

필수 테스트:
1. A-B-C-D chaining synthetic vectors
2. compact valid cluster
3. bridge claim
4. threshold boundary
5. same-source duplicate claims
6. 기존 정상 clustering regression

---

### B3. Aspect / Sentiment Fragmentation Safety

- 현재 small alias map은 유지
- 명백한 alias만 보강
- giant ontology 금지
- `battery`, `battery_life`, `battery_health`, `battery_runtime` 같은 변형 검증
- positive/negative를 무조건 합치지 않는다
- aspect extraction이 완벽하다고 가정하지 않는다
- 안전한 자동 merge가 어렵다면 uncertainty/evaluation signal을 남긴다

---

## 4. Phase C — Input Quality Hardening Before TASK 012

### C1. Product Identity / Relevance Safety

다음을 구분해야 한다.
- 본체 vs accessory
- 단일 제품 vs comparison page
- exact generation/model vs adjacent generation
- tracking parameter 속 우연한 제품명
- `MaxV`, `Pro`, `Plus` 등 suffix model

필수 테스트:
- `AirPods Pro 2 case`
- `AirPods Pro 2 vs AirPods Pro 3`
- 제품명이 `utm_*`에만 있는 unrelated URL
- suffix model preservation
- previous generation evidence
- ambiguous family input

---

### C2. Evidence Compression Context Safety

- sentence/paragraph boundary에서 truncate 우선
- negation/context를 중간에서 잘라 의미 반전 금지
- cleaned raw가 empty/useless면 snippet fallback
- provenance 유지
- 가능하면 source segment/offset debugging metadata 고려

필수 테스트:
- failure가 paragraph 2/4에만 존재
- negation near truncation boundary
- script/style-only raw + useful snippet
- Korean sentence boundary
- deterministic output

---

### C3. Usage Period Grounding

다음을 구분한다.
- actual use duration
- warranty period
- product age
- subscription period
- arbitrary duration

필수 사례:
- `6개월 사용`
- `6개월간 사용`
- `1년째 사용`
- `Warranty lasts 12 months`
- `0.6 months`

integer-month schema를 유지한다면 sub-month/ambiguous 값을 misleading integer로 바꾸지 않는다.

---

### C4. Stable IDs for Incremental Search

TASK 012의 별도 filtering run들이 모두 `S001`, `IG001`부터 시작해 충돌하면 안 된다.

analysis/snapshot-safe identity contract를 만든다.

가능한 방식:
- normalized URL/content key 기반 deterministic ID
- caller-supplied analysis namespace
- cumulative registry
- full snapshot rebuild

가장 단순하고 향후 orchestration과 호환되는 방식을 선택한다.

필수 테스트:
1. 독립 filter call 두 번
2. accepted sources 병합
3. source ID collision 없음
4. IG collision 없음
5. 두 call 사이 duplicate가 안전하게 dedup/reconcile됨

---

## 5. Deferred to TASK 019

이번 TASK에서는 구조적 correctness를 먼저 고친다.

다음 숫자 자체는 직관만으로 튜닝하지 않는다.
- clustering threshold `0.82`
- confidence weights
- LOW/MEDIUM/HIGH threshold
- minimum confidence `0.40`
- minimum independent evidence `3`
- SKIP support `4`
- BUY_IF support `2`
- long-term threshold `6 months`

실데이터/held-out fixture를 이용한 calibration은 TASK 019에서 한다.

---

## 6. Required Adversarial Regression

최소 다음을 추가한다.

1. cross-domain copied content -> independent support 증가 금지
2. footer/wrapper near-duplicate -> independent support 증가 금지
3. unsupported semantic claim -> decision 참여 금지
4. negated evidence -> opposite claim 금지
5. neutral-only evidence -> BUY 금지
6. unresolved severe risk 보존
7. duplicate source -> severity/support 증가 금지
8. minor report 추가 -> repeated high-severity issue 소멸 금지
9. chaining vector case -> invalid strong cluster 금지
10. aspect alias split scenario
11. accessory/comparison/generation ambiguity
12. compression failure/negation context 보존
13. cleaned-empty raw -> snippet fallback
14. warranty != usage duration
15. `6개월간`
16. `0.6 months` != six months
17. separate filter runs ID collision 없음
18. TASK 001~011 전체 regression 통과

기본 test suite는 network/유료 API를 호출하지 않는다.

---

## 7. Acceptance Criteria

TASK 011A 완료 조건:

- Red Team CRITICAL 재현 3개가 더 이상 기존 unsafe 결과를 만들지 않음
- copied/near-duplicate가 독립 support를 쉽게 증가시키지 못함
- unsupported/uncertain claim이 일반 decision evidence에 참여하지 않음
- BUY가 affirmative support를 요구함
- unresolved severe risk가 보존됨
- severity threshold가 URL 수가 아니라 independence-group support를 사용함
- clustering chaining에 internal coherence guard가 있음
- usage duration이 unrelated duration에서 생성되지 않음
- TASK 012용 incremental source/group ID가 안전함
- 기존 전체 regression 통과
- 신규 adversarial regression 통과
- 새 LLM/network dependency는 꼭 필요한 경우가 아니면 추가하지 않음

---

## 8. Non-Goals

구현 금지:
- TASK 012 Counter Evidence Search
- TASK 013 Strong-model Gate
- TASK 014 Alternative Engine
- TASK 015 Alternative Reverification
- DB persistence
- Frontend
- Deployment
- 대형 semantic relevance classifier
- 대형 product taxonomy
- 대형 aspect ontology
- vector DB
- 직관만으로 threshold 최적화

---

## 9. Documentation

최종적으로 확정된 invariant는 짧게 문서화한다.

최소:
- independent evidence 의미
- grounding state/rule
- BUY safety rule
- unresolved severe risk 처리
- severity aggregation 의미
- cluster coherence rule
- incremental source/group identity rule

프로젝트 전역 불변조건으로 확정된 항목만 `PROJECT_SPEC.md`에 좁게 반영한다.
관련 없는 기존 spec을 대규모 수정하지 않는다.

---

## 10. Git / Completion

시작 전:

```powershell
git status
```

작업 완료 후:

```powershell
$env:PYTHONPATH = 'backend'
backend\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests
git diff
git status
```

모든 테스트 통과 시 TASK 011A 변경만 commit.

권장 commit:

```text
Harden core evidence and decision reliability
```

자동 push 금지.
TASK 012 구현 금지.

---

## 11. Completion Report

[사전 확인]
- 시작 Git 상태
- 읽은 파일/명세

[변경 파일]
- 생성/수정 목록

[Audit Fix Mapping]
각 항목에 `fixed / partially fixed / deferred / reason`
- C01
- C02
- C03
- H01
- H02
- H03
- H04
- H05
- H06
- H07/H09
- M02
- M03

[Source Independence]
- exact duplicate
- near duplicate
- unknown independence
- cross-domain copy

[Grounding]
- verification state
- polarity/subject/direct experience
- unsupported claim 처리

[Decision Safety]
- BUY requirements
- unresolved severe risk
- SKIP / BUY_IF changes

[Severity]
- independence-group aggregation
- high-severity support

[Clustering]
- chaining mitigation
- internal coherence

[Input Quality]
- product identity
- evidence compression
- usage duration
- incremental IDs

[테스트]
- 신규 adversarial tests
- 전체 passed / failed / skipped
- 기존 regression

[Dependency]
- 추가 dependency 또는 없음

[Git]
- commit hash
- final status
- push 여부

[남은 문제]
- 잔여 audit finding
- TASK 019로 명시적으로 defer한 항목

완료 후 멈춰라.
