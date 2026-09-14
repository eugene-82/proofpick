# Task 002 — Domain Models & Database Schema

## Goal
Define ProofPick's core domain entities and create the initial Supabase/PostgreSQL schema.

## Read First
- `AGENTS.md`
- `PROJECT_SPEC.md`

## Scope
Implement models/tables for at least:
- products
- analyses
- sources
- claims
- claim_sources
- alternatives

Add explicit analysis states:
- queued
- resolving_product
- searching
- filtering_sources
- extracting_claims
- clustering_claims
- evaluating
- searching_counter_evidence
- finding_alternatives
- verifying_alternatives
- complete
- failed

Add migration files rather than manually mutating a production database.

Create corresponding Pydantic models.

## Requirements
- Stable IDs
- timestamps
- analysis version / pipeline version where relevant
- source metadata fields
- alternative analysis linkage
- indexes for common lookups

## Do Not
- Do not store full scraped web pages by default.
- Do not add user authentication.
- Do not create notification tables.

## Tests
Validate:
- model serialization
- required fields
- allowed decision enums
- allowed state enums

## Done When
Database schema and backend domain schemas are consistent and testable.
