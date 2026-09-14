# Task 014 — Alternative Candidate Engine

## Goal
Find plausible alternatives when the original product is unsuitable.

## Flow
1. Derive original product constraints
2. Generate/search candidate products
3. Keep candidates in a comparable category/price/use case
4. Do NOT immediately recommend them

Candidate fields should include:
- product identity
- reason candidate is comparable
- likely price band if known
- matching required features

## Rule
LLM memory alone is not sufficient evidence for final recommendation.

## Done When
SKIP or severe-concern products can produce a small candidate set ready for verification.
