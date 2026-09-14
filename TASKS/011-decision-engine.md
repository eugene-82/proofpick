# Task 011 — Purchase Decision Engine

## Goal
Produce one of:
- BUY
- BUY_IF
- SKIP
- EARLY_ADOPTER

using evidence metrics and claims.

## Rules
- Decision must not be produced solely from LLM prose.
- EARLY_ADOPTER must be used when evidence is insufficient.
- Severe recurring issues across independent sources should influence SKIP.
- Mixed evidence may produce BUY_IF.

The LLM may later explain a decision but should not be the only logic behind it.

## Tests
Create deterministic cases for all four states.

## Done When
Given a fixed analysis fixture, the same decision is produced consistently.
