# Task 019 — AI Evaluation Harness

## Goal
Measure pipeline/model/prompt changes instead of judging them by feel.

## Benchmark Fixtures
Prepare representative cases:
- good product
- bad product
- early-adopter product
- ambiguous product
- duplicate-source-heavy product

## Metrics
At minimum:
- claim recall
- unsupported claim rate
- source attribution correctness
- decision consistency
- evidence diversity
- latency
- token usage
- estimated cost

## Requirements
Results should be comparable across pipeline versions.

## Done When
A prompt/model/pipeline change can be evaluated quantitatively before adoption.
