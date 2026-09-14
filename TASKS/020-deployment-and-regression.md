# Task 020 — Deployment & Final Regression

## Goal
Deploy ProofPick and verify the full MVP before submission.

## Deployment
- Frontend: Vercel
- Backend: Railway
- Database: Supabase

## Security Checks
- no secrets committed
- production environment variables configured
- `.env.example` contains placeholders only
- backend CORS limited appropriately

## Regression Scenarios
Test at least:
1. evidence-rich good product
2. recurring-problem product
3. newly launched / low-evidence product
4. product requiring verified alternatives
5. ambiguous product name
6. external API failure

## Demo Preparation
Prepare cached representative analyses for:
- BUY
- SKIP + alternative
- EARLY_ADOPTER

## Final Checks
- mobile layout
- public URL works
- source links work
- failures do not expose stack traces
- cache works
- analysis states work
- API limits/costs checked

## Done When
The public service can be demonstrated end-to-end reliably and matches the MVP definition in `PROJECT_SPEC.md`.
