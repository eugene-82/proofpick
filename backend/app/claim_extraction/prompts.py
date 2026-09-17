"""Single versioned prompt location for claim extraction."""

from .policy import CLAIM_EXTRACTION_PROMPT_VERSION


CLAIM_EXTRACTION_INSTRUCTIONS = f"""
ProofPick claim extraction prompt {CLAIM_EXTRACTION_PROMPT_VERSION}.

Extract only product-use claims directly supported by the supplied evidence documents.
Return the provided structured schema and no prose.

Rules:
- Keep each claim attributed to an input source_id.
- evidence_fragment must be a short verbatim excerpt present in that source's text.
- Exclude shipping speed, seller service, speculation, hearsay, and unused-product impressions.
- Marketing or sponsorship disclosure alone is not a product-use claim.
- Use concise snake_case aspects. Prefer stable labels such as battery, durability, noise,
  comfort, sensor, mapping, build_quality, performance, software, connectivity,
  cleaning_performance, and after_sales_service where applicable.
- sentiment must be positive, negative, or neutral.
- severity is impact from 1 to 5: 1 minor preference; 2 noticeable but usable;
  3 meaningful inconvenience; 4 major core-function issue; 5 serious failure or safety issue.
  For positive and neutral claims, use the same practical-impact scale without inventing harm.
- usage_period_months is an integer only when the source explicitly states an equivalent
  whole-month or whole-year duration. Use null for vague durations or periods under one month.
- Do not paraphrase evidence_fragment, invent facts, or force a claim when none is useful.
- For every claim, return semantic_relation as the provider's explicit verdict. Bind it to
  the exact target_product_id, evidence_source_id, and evidence_quote. Use
  target_product_id="unspecified-product" when no resolved identity was supplied.
- subject and predicate must describe the same clause-local relation as the claim; do not
  transfer a predicate from an accessory, comparison product, or nearby entity.
- polarity, experiencer, experience_type, observation_type, and verification_status must be
  explicit. Use UNCERTAIN instead of guessing an ambiguous pronoun or product relation.
- VERIFIED is allowed only for a direct observation of the target relation. Speculation,
  marketing, and reported experience remain UNCERTAIN or REJECTED.
- Only USAGE, OWNERSHIP, or TEST may carry long-term observation_months. Warranty,
  subscription, return-period, hypothetical, and first-impression periods do not establish it.
- semantic_relation.evidence_quote must exactly equal evidence_fragment and its
  evidence_source_id must exactly equal source_id.
- Multiple claims from one source and an empty claims list are both valid.
""".strip()


REPAIR_INSTRUCTION = """
The previous output failed schema or source-grounding validation. Return a corrected structured
payload only. Remove claims that cannot use a valid input source_id, a verbatim source fragment,
or an explicitly supported usage period. Re-evaluate every repaired candidate through the same
semantic relation contract; repair never relaxes semantic verification.
""".strip()
