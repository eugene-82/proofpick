# Purchase Decision Engine

The decision engine evaluates the current evidence snapshot with deterministic MVP heuristics. It is stateless and can be run again after counter-evidence is added.

- `EARLY_ADOPTER`: evidence is insufficient, affirmative support is absent, or a severe/conflicting risk remains unresolved. Missing information is not interpreted as either good or bad.
- `SKIP`: sufficient evidence contains the configured number of confirmed independent groups reporting an issue at or above the high-severity threshold.
- `BUY_IF`: sufficient evidence contains a repeated negative issue that does not meet the SKIP threshold. Every result includes at least one structured condition.
- `BUY`: evidence is sufficient, independently supported affirmative evidence exists, and no blocking, conditional, unresolved severe, or unresolved conflicting issue remains.

Severity is aggregated by independence group. Each group contributes its maximum observed severity once; duplicate URLs cannot raise support, and a lower-severity report cannot erase four independently repeated high-severity reports. A lone high-severity report is not an automatic SKIP, but its provenance is retained in `unresolved_risks` and it blocks BUY.

Evidence confidence describes the reliability and sufficiency of the evidence. The decision describes what those claims imply for purchase. A HIGH confidence score can therefore produce BUY, BUY_IF, SKIP, or a conservative EARLY_ADOPTER result.

All numeric thresholds remain centralized in `DecisionPolicy`. They are initial hackathon-MVP heuristics, not scientifically established constants, and will be calibrated with held-out fixtures in TASK 019.
