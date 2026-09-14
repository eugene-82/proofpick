# Task 005 — Adaptive Query Generator

## Goal
Generate efficient product research queries without wasting search calls.

## Query Strategy
Start with a small base set, roughly:
1. general real-user review
2. problems / disadvantages
3. long-term use

Only expand when evidence is insufficient.

Potential later expansions:
- failures / defects
- category-specific issues
- community-specific searches
- Reddit / Korean community variants
- positive counter-evidence

## Requirements
Queries should consider product category.

Examples:
- laptops: heat, battery, fan noise, hinge
- robot vacuums: mapping, sensor, threshold, hair, battery
- keyboards: chatter, stabilizer, wireless, battery

## Output
Structured query objects including query purpose.

## Do Not
- Do not generate dozens of queries upfront.
- Do not hard-code every category in a giant branch if the LLM can generalize safely.

## Tests
Verify:
- base budget
- category-aware queries
- no duplicate queries
- maximum budget enforcement

## Done When
The system can create an initial low-cost query plan and request expansion only when necessary.
