# Task 003 — Search Provider Abstraction

## Goal
Create a replaceable web search provider layer.

## Scope
Define a common interface such as:
- `search(query, max_results, ...)`

Implement the first provider using the configured search API.

Normalize results into a shared structure containing:
- title
- url
- snippet
- domain
- published_at if available
- raw_content if provider supplies it

## Requirements
- timeouts
- API error handling
- rate-limit handling
- provider-specific code isolated from business logic
- no API keys in source code

## Cost Rule
Search must support adaptive query budgets later.
Do not hard-code 10 queries per analysis.

## Tests
Use mocks to test:
- successful search
- empty results
- timeout
- rate-limit
- malformed provider response

## Done When
The backend can run one normalized search without other parts of the pipeline knowing which provider is used.
