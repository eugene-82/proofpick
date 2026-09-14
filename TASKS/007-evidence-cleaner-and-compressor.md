# Task 007 — Evidence Cleaner & Compressor

## Goal
Reduce raw web content before sending it to an LLM.

## Pipeline
```text
raw content
→ boilerplate reduction
→ relevant text selection
→ bounded evidence chunks
```

Remove or reduce:
- navigation
- footer
- menus
- repeated page chrome
- unrelated recommendations
- duplicated text

## Rules
- Preserve source ID.
- Preserve enough context for claims.
- Do not rewrite evidence into unsupported statements.
- Bound maximum text per source.

## Metrics
Track:
- original character/token estimate
- compressed character/token estimate
- compression ratio

## Tests
Ensure useful review text survives while obvious boilerplate is removed.

## Done When
Claim extraction no longer requires repeatedly sending full pages to the LLM.
