# Task 017 — Caching & Observability

## Goal
Reduce repeated cost/latency and make pipeline behavior measurable.

## Product-Level Cache
Initial target:
- 24-hour TTL for recent completed analyses
- explicit refresh option
- analysis age exposed to UI

## Source-Level Cache
Key reusable extraction by:
- normalized URL
- content hash
- extraction/prompt version

## Log/Metrics
Track:
- analysis ID
- queries
- sources found/used
- independent evidence groups
- input/output tokens
- estimated cost
- latency
- cache hit
- decision
- confidence
- pipeline version

Never log secrets.

## Done When
Repeated product searches can avoid unnecessary search/LLM calls and developers can inspect cost/latency.
