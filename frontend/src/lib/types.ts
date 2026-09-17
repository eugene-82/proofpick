export type PurchaseDecision = "BUY" | "BUY_IF" | "SKIP" | "EARLY_ADOPTER";
export type ConfidenceLevel = "LOW" | "MEDIUM" | "HIGH";
export type ClaimSentiment = "positive" | "negative" | "neutral";

export interface DecisionSignal {
  reason_code: string;
  cluster_id: string;
  aspect: string;
  sentiment: ClaimSentiment;
  severity: number;
  max_severity: number;
  source_count: number;
  independent_source_count: number;
  high_severity_independent_support: number;
  domain_count: number;
  long_term_evidence: boolean;
}

export interface EvidenceReference {
  source_id: string;
  source_url: string;
  fragment: string;
}

export interface ClaimSummary {
  cluster_id: string;
  canonical_claim: string;
  aspect: string;
  sentiment: ClaimSentiment;
  max_severity: number;
  independent_source_count: number;
  evidence: EvidenceReference[];
}

export interface SourceSummary {
  source_id: string;
  url: string;
  domain: string;
  title: string | null;
  independence_group_id: string;
}

export interface AnalysisResponse {
  analysis_id: string;
  status: "complete";
  product: string;
  initial_decision: PurchaseDecision;
  decision: PurchaseDecision;
  confidence: number;
  confidence_level: ConfidenceLevel;
  reasons: string[];
  blocking_issues: DecisionSignal[];
  unresolved_risks: DecisionSignal[];
  counter_evidence_attempted: boolean;
  counter_evidence_completed: boolean;
  counter_evidence_queries: string[];
  counter_evidence_source_count: number;
  counter_evidence_sources: SourceSummary[];
  decision_changed: boolean;
  claims: ClaimSummary[];
  sources: SourceSummary[];
}

export type ApiErrorCode =
  | "PRODUCT_IDENTITY_UNRESOLVED"
  | "INVALID_REQUEST"
  | "MODEL_PROVIDER_UNAVAILABLE"
  | "ANALYSIS_INTEGRITY_ERROR"
  | "NETWORK_ERROR"
  | "UNKNOWN_ERROR";

export class AnalysisApiError extends Error {
  constructor(
    public readonly code: ApiErrorCode,
    message: string,
    public readonly status?: number,
  ) {
    super(message);
    this.name = "AnalysisApiError";
  }
}
