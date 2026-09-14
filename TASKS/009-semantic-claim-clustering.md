# Task 009 — Semantic Claim Clustering

## Goal
Group semantically equivalent claims while keeping their underlying evidence.

## Strategy
Prefer:
1. embedding/similarity grouping
2. deterministic thresholds
3. optional LLM cluster naming/refinement

Do not use an expensive LLM to compare every claim pair.

## Output
Each cluster should contain:
- cluster ID
- canonical claim
- aspect
- sentiment
- member claim IDs
- supporting source IDs
- independent evidence count
- platform/domain diversity

## Tests
Test phrases with same meaning and phrases that should remain separate.

## Done When
The system can say that differently worded reports represent one recurring issue without losing source traceability.
