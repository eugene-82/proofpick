# Task 012 — Counter-Evidence Search

## Goal
Actively challenge the pipeline's initial conclusion.

## Behavior
If initial evidence is strongly positive, generate searches for:
- defects
- failures
- regrets
- long-term problems

If initial evidence is strongly negative, search for:
- satisfied users
- positive long-term experiences
- contexts where the product works well

## Rules
- Only run when useful.
- Respect the global search budget.
- Feed new evidence through the same filter/extraction pipeline.
- Recalculate confidence and decision after new evidence.

## Tests
Verify search direction changes based on initial result.

## Done When
The system demonstrates that it seeks disconfirming evidence rather than merely reinforcing the first conclusion.
