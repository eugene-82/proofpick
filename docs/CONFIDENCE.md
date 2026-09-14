# Evidence Confidence Engine

The confidence engine measures how reliable and sufficient the collected evidence is.
It does **not** measure whether a product is good, and claim severity is deliberately not
part of this score.

The score keeps six inspectable components:

- evidence volume: unique useful sources, with diminishing returns;
- independence: independent-group count plus the independent/source ratio;
- diversity: unique source domains, with diminishing returns;
- agreement: repeated independent support per claim cluster, reduced when positive and
  negative clusters conflict within the same aspect;
- long-term evidence: independent long-term groups, their coverage, and capped duration;
- commercial risk: the mean of explicitly supplied signals after grouping dependent
  sources, subtracted as a bounded penalty.

Unknown commercial signals are ignored rather than treated as zero. Source quality is not
estimated because the current source-filter output has no measured quality value. All
weights, saturation scales, long-term thresholds, and LOW/MEDIUM/HIGH boundaries live in
`ConfidencePolicy`. The initial policy uses LOW below 0.40, MEDIUM below 0.70, and HIGH at
or above 0.70. Evidence from no more than one independent group is capped below MEDIUM.

This is an initial MVP heuristic. It is deterministic and fixture-testable, but its weights
should be calibrated through the later evaluation harness before being treated as stable.
