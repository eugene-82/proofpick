# Task 010 — Evidence Confidence Engine

## Goal
Calculate inspectable evidence-confidence metrics using deterministic code.

## Candidate Signals
- useful source count
- independent source count
- domain/platform diversity
- evidence agreement
- long-term usage evidence
- evidence specificity
- commercial signals
- duplicate/dependent-source penalty

## Important
The confidence score measures evidence quality, not absolute product quality.

## Requirements
- configurable weights
- normalized outputs
- component scores preserved for UI/debugging
- unit tests around boundaries

## Do Not
Do not ask an LLM to invent a confidence percentage.

## Done When
The pipeline can explain why evidence confidence is high or low.
