# Task 013 — Strong-Model Confidence Gate

## Goal
Use expensive/high-capability models only when ambiguity justifies them.

## Trigger Examples
- low confidence
- conflicting high-quality claims
- BUY_IF/SKIP boundary
- ambiguous product identity
- difficult alternative comparison

## Non-Trigger
High-confidence straightforward cases should continue without strong-model verification.

## Requirements
Record:
- whether strong verifier was used
- reason
- token usage
- result

## Tests
- confident fixture: verifier not called
- ambiguous fixture: verifier called

## Done When
Strong-model usage is conditional, observable, and testable.
