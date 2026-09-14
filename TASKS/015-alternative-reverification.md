# Task 015 — Alternative Re-Verification

## Goal
Run alternative candidates through the same evidence pipeline before recommending them.

## Core Rule
> Alternatives are verified too.

For each alternative:
- resolve identity
- search
- filter
- extract
- cluster
- calculate confidence
- decide

If evidence is insufficient:
- mark alternative EARLY_ADOPTER

Do not promote an unverified candidate as a safe recommendation.

## Done When
A user can see why an alternative is recommended and inspect its independent evidence.
