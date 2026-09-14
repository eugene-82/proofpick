# Core Reliability Invariants

These invariants protect the evidence-to-decision path before counter-evidence search is added.

- Independent evidence means a distinct, confirmed independence group. Exact URL/content copies and conservative near-copies are dependent; unknown independence is never promoted to confirmed support.
- Source and independence-group IDs come from one analysis-local `SourceIdentityRegistry`. Incremental filtering passes must reuse that registry so IDs cannot collide and duplicates reconcile to the original representative.
- Only `VERIFIED` grounded claims may enter clustering, confidence, or purchase decisions. `UNCERTAIN` and `REJECTED` assessments remain observable but are excluded from decision evidence.
- Grounding requires source membership, meaningful source text, semantic support, compatible polarity/negation, direct-experience safety, explicit usage duration, and target-product consistency when identity is available.
- Claim clusters are deterministic complete-link groups within normalized aspect and sentiment partitions. Every new member must meet the configured similarity threshold against every existing member; bridge chains cannot create support.
- Severity is aggregated once per independence group using that group's maximum observed severity. SKIP support counts confirmed groups at the high-severity threshold, so copied URLs cannot add weight and a minor report cannot dilute repeated severe reports.
- BUY requires sufficient evidence plus affirmative independently supported claims, with no blocking issue or unresolved major risk/conflict. Neutral-only evidence never defaults to BUY.
- A severe report without repeated confirmed support does not force SKIP, but it is retained in `unresolved_risks` and prevents BUY.
- Evidence compression is extractive and bounded. It prioritizes risk, usage, and negation context and avoids slicing away a negation token. If cleaned raw content is empty, a useful snippet is used.

Numeric threshold calibration remains deferred to TASK 019.
