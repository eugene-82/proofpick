# Task 008 — Structured Claim Extractor

## Goal
Extract product-use claims from evidence into validated structured output.

## Required Fields
At minimum:
- source_id
- aspect
- claim
- sentiment
- severity
- usage_period_months when known
- evidence fragment / reference

## Requirements
- Pydantic validation
- structured model output
- batched extraction
- retry once on schema failure
- mark failure rather than accepting malformed output

## Important
Do not infer facts that are absent from the source.

## Batch Rule
Avoid one LLM call per document.
Use bounded multi-document batches where context limits allow.

## Tests
Include:
- positive claim
- negative claim
- mixed review
- no useful claim
- invalid LLM schema output
- usage-period extraction

## Done When
Raw evidence becomes a reusable claim dataset keyed by source IDs.
