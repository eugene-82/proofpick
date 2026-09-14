# Purchase Decision Engine

The decision engine evaluates the current evidence snapshot with deterministic MVP
heuristics. It is stateless and can be run again after counter-evidence is added.

- `EARLY_ADOPTER`: evidence confidence, independent support, or meaningful claims are
  insufficient. Missing information is not interpreted as either good or bad.
- `SKIP`: sufficient evidence contains a repeated, independently supported negative issue
  at or above the configured high-severity threshold. Severity is averaged after
  deduplicating claims by source, so one severe claim cannot elevate a repeated cluster.
- `BUY_IF`: sufficient evidence contains a repeated negative issue that does not meet the
  SKIP threshold. Every result includes at least one structured condition.
- `BUY`: evidence is sufficient and no repeated blocking or conditional issue is present.
  Positive support may be included, but positive volume cannot override a blocking issue.

Evidence confidence describes the reliability and sufficiency of the evidence. The
decision describes what those claims imply for purchase. A HIGH confidence score can
therefore produce either BUY or SKIP, while LOW confidence produces EARLY_ADOPTER.

All thresholds are centralized in `DecisionPolicy`. They are initial hackathon-MVP
heuristics, not scientifically established constants, and should be calibrated with the
later evaluation harness.
