# Task 004 — Product Resolver

## Goal
Normalize user input into a canonical product representation.

## Inputs
- free-text product name
- product URL

## Output
Structured product identity containing at least:
- brand
- product name
- model
- generation/version if identifiable
- category
- canonical name
- ambiguity flag
- candidate products when ambiguous

## Rules
- Use structured LLM output when AI is required.
- Prefer deterministic URL parsing when possible.
- Do not silently merge product generations.
- Ambiguous input must remain ambiguous.

## Tests
Cover:
- exact model name
- vague family name
- generation ambiguity
- URL input
- unsupported/invalid input

## Done When
Downstream search logic receives a stable canonical product identity rather than raw user text.
