# Core Reliability Invariants

These invariants protect the evidence-to-decision path before counter-evidence search is added.

- Independence is explicit and deterministic. Raw-content length alone never promotes a source: CONFIRMED requires explicit provenance assessment, uncertain sources remain UNKNOWN, and exact or established copies are DEPENDENT. Only confirmed groups increase independent support.
- Similarity alone does not delete evidence. Changes to polarity/negation, numeric observations, author identity, or claim-bearing signals preserve both sources and leave uncertain independence unresolved.
- Source and group IDs come from one analysis-local SourceIdentityRegistry. Incremental passes reuse it; enrichment reindexes final retained content, protects richer representatives, and maps dependent URL aliases back to the original group.
- Only VERIFIED grounded claims may enter a decision-driving snapshot. Subject, predicate, polarity, direct-experience, and product-generation checks apply on initial and repair attempts.
- Claim-core validity is separate from optional metadata validity. Unsupported usage_period_months is removed and reported as a metadata issue without discarding an otherwise grounded claim.
- Compression is deterministic and extractive. It covers document regions, preserves positive counter-evidence and risks together, redistributes unused budget, and avoids cutting negation context.
- Confidence carries evidence quality, verified-claim coverage, and observation horizon. Snippet-only mass, entirely unknown quality, no verified coverage, and first-impression-only durability support cannot produce an overconfident BUY. Observation duration is not a universal requirement for non-durability claims.
- Unresolved severe risks are computed before decision branching and retained on every applicable return path. Positive support and insufficient-evidence early returns cannot erase them.
- Complete-link clustering keeps the configured threshold unchanged and first canonicalizes claim order. The same claim set therefore produces the same clusters and downstream decision regardless of caller order.
- EvaluationSnapshot is deeply immutable and validates every runtime construction/copy path. Its digest binds analysis, stable product identity, registry manifest/revision, source/group provenance, evidence quality/observation, and decision-driving claim text, sentiment, severity, and grounding state; mismatches and non-VERIFIED claims fail explicitly.
- Severity is aggregated once per independence group using the group's maximum observed severity. Copied URLs cannot add weight, and a minor report cannot dilute repeated severe reports.
- BUY requires sufficient evidence plus affirmative independently supported claims, with no blocking issue or unresolved major risk/conflict. Neutral-only evidence never defaults to BUY.

Numeric threshold and product-category calibration remain deferred to TASK 019. Counter-evidence search and persistence remain deferred to TASK 012 and later tasks.
