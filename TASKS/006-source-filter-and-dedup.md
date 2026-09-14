# Task 006 — Source Filtering & Deduplication

## Goal
Remove irrelevant, duplicate, and low-value sources before LLM extraction.

## Deterministic Processing
Implement:
- URL normalization
- canonical URL handling
- duplicate URL detection
- content hash support
- basic low-content rejection
- irrelevant page filtering where possible

Identify source type/domain.

## Source Independence
Create an initial mechanism for grouping likely dependent sources using signals such as:
- identical content
- high similarity
- same quoted text
- same canonical URL
- syndicated copies

## Important
Do not claim that every URL equals one independent reviewer.

## Tests
Include fixtures with:
- URL tracking parameters
- duplicated pages
- syndicated content
- irrelevant pages
- valid unique sources

## Done When
Downstream extraction receives a cleaner, smaller, traceable evidence set.
