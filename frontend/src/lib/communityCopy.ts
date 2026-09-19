import type { AnalysisResponse, ClaimSummary, DecisionSignal, PurchaseDecision } from "@/lib/types";

export type CommunitySummaryLines = readonly [string, string, string];

export const communityPhraseBank: Record<PurchaseDecision, readonly string[]> = {
  BUY: ["이륙 허가 ㄱㄱ", "이 가격이면 ㄱㄱ", "가성비 잘 뽑힘"],
  BUY_IF: ["용도 맞으면 추천", "할인가면 ㄱㄱ", "단점 감당 ㄱㄴ?"],
  SKIP: ["이륙 말고 회항 ㄱ", "이 가격엔 비추", "AS까지 생각하면 패스"],
  EARLY_ADOPTER: ["선발대 모십니다", "선발대 후기좀 ㅋㅋ", "후기 뜨면 다시 보자"],
};

const aspectLabels: Record<string, string> = {
  battery: "배터리",
  comfort: "착용감",
  connectivity: "연결 안정성",
  durability: "내구성",
  noise: "소음",
  price: "가격",
  reliability: "신뢰성",
  sound: "음질",
  sound_quality: "음질",
  value: "가성비",
  warranty: "보증과 AS",
};

function displayAspect(aspect: string): string {
  const normalized = aspect.toLowerCase().replaceAll(" ", "_");
  return aspectLabels[normalized] ?? normalized.replaceAll("_", " ");
}

function byImportance<T extends DecisionSignal | ClaimSummary>(left: T, right: T): number {
  const severityDifference = right.max_severity - left.max_severity;
  if (severityDifference !== 0) return severityDifference;
  const supportDifference = right.independent_source_count - left.independent_source_count;
  if (supportDifference !== 0) return supportDifference;
  return left.aspect.localeCompare(right.aspect);
}

function primaryRisk(analysis: AnalysisResponse): DecisionSignal | undefined {
  return [...analysis.blocking_issues, ...analysis.unresolved_risks].sort(byImportance)[0];
}

function primaryPositiveClaim(analysis: AnalysisResponse): ClaimSummary | undefined {
  return analysis.claims.filter((claim) => claim.sentiment === "positive").sort(byImportance)[0];
}

function factLine(analysis: AnalysisResponse): string {
  const risk = primaryRisk(analysis);
  if (risk) {
    const aspect = displayAspect(risk.aspect);
    return risk.independent_source_count > 0
      ? `${aspect} 쪽 위험이 핵심이고 독립 근거 ${risk.independent_source_count}개에서 확인됨.`
      : `${aspect} 쪽 위험이 아직 해소되지 않음.`;
  }
  const positive = primaryPositiveClaim(analysis);
  if (positive && positive.independent_source_count > 0) {
    return `${displayAspect(positive.aspect)} 쪽 긍정 근거가 독립 출처 ${positive.independent_source_count}곳에서 확인됨.`;
  }
  if (analysis.decision === "BUY") return "반복 확인된 구매 차단 이슈는 없음.";
  if (analysis.decision === "BUY_IF") return "조건부 판단이라 아래 주의점을 같이 봐야 함.";
  if (analysis.decision === "SKIP") return "구매를 막는 반복 문제가 확인됨.";
  return "독립적인 실사용 근거가 더 필요함.";
}

function reactionLine(analysis: AnalysisResponse): string {
  const risk = primaryRisk(analysis);
  const riskAspect = risk?.aspect.toLowerCase() ?? "";
  const positiveAspect = primaryPositiveClaim(analysis)?.aspect.toLowerCase() ?? "";
  const signal = `${riskAspect} ${positiveAspect}`;
  if (analysis.decision === "BUY") {
    if (/price/.test(signal)) return communityPhraseBank.BUY[1];
    if (/value/.test(signal)) return communityPhraseBank.BUY[2];
    return communityPhraseBank.BUY[0];
  }
  if (analysis.decision === "BUY_IF") {
    if (/price|value/.test(signal)) return communityPhraseBank.BUY_IF[1];
    if (/battery|noise|comfort|reliability|durability/.test(signal)) return communityPhraseBank.BUY_IF[2];
    return communityPhraseBank.BUY_IF[0];
  }
  if (analysis.decision === "SKIP") {
    if (/price|value/.test(signal)) return communityPhraseBank.SKIP[1];
    if (/battery|reliability|durability|warranty|service/.test(signal)) return communityPhraseBank.SKIP[2];
    return communityPhraseBank.SKIP[0];
  }
  if (analysis.confidence_level === "LOW") return communityPhraseBank.EARLY_ADOPTER[1];
  if (/reliability|durability|battery/.test(signal)) return communityPhraseBank.EARLY_ADOPTER[2];
  return communityPhraseBank.EARLY_ADOPTER[0];
}

export function buildCommunitySummary(analysis: AnalysisResponse): CommunitySummaryLines {
  const conclusion: Record<PurchaseDecision, string> = {
    BUY: "전반적으로 괜찮다는 근거가 우세함.",
    BUY_IF: "장점은 분명한데 조건을 좀 탐.",
    SKIP: "단점 쪽 근거가 꽤 강함.",
    EARLY_ADOPTER: "아직 믿고 결론 내리기엔 정보가 적음.",
  };
  return [conclusion[analysis.decision], factLine(analysis), reactionLine(analysis)];
}

export function communitySourceLabel(domain: string): string {
  const normalized = domain.toLowerCase().replace(/^www\./, "");
  const labels: readonly [RegExp, string][] = [
    [/dcinside/, "디시"],
    [/fmkorea/, "에펨"],
    [/ruliweb/, "루리웹"],
    [/quasarzone/, "퀘이사존"],
    [/clien/, "클리앙"],
    [/ppomppu/, "뽐뿌"],
    [/naver/, "네이버"],
    [/youtube|youtu\.be/, "YouTube"],
  ];
  return labels.find(([pattern]) => pattern.test(normalized))?.[1] ?? normalized;
}
