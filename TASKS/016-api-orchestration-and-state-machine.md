# Task 016 — Analysis API & Pipeline Orchestration

## Goal
Connect the pipeline behind stable REST endpoints and persisted states.

## Minimum API
- `POST /api/analyses`
- `GET /api/analyses/{id}`
- `GET /api/analyses/{id}/sources`
- `GET /api/analyses/{id}/claims`
- alternative endpoint if not included in analysis payload

## Behavior
POST should return quickly with an analysis ID.

Progress should be represented through real persisted states, not fake percentages.

## Failure Handling
Handle:
- search errors
- LLM errors
- schema validation failures
- zero useful sources
- database failures
- partial alternative failure

## Done When
Frontend can submit a product and poll/receive meaningful analysis progress and results.
