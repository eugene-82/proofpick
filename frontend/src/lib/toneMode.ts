import type { AnalysisResponse, PurchaseDecision } from "@/lib/types";

export type ToneMode = "formal" | "casual" | "community";

export const toneModeOptions: readonly { value: ToneMode; label: string }[] = [
  { value: "formal", label: "기본" },
  { value: "casual", label: "캐주얼" },
  { value: "community", label: "커뮤" },
];

const decisionDescriptions: Record<ToneMode, Record<PurchaseDecision, string>> = {
  formal: {
    BUY: "현재 확인된 근거에서는 구매를 막을 만한 반복적인 문제가 충분히 확인되지 않았습니다.",
    BUY_IF: "조건에 따라 만족도가 달라질 수 있어 아래 주의점을 먼저 확인하는 것이 좋습니다.",
    SKIP: "여러 독립 근거에서 구매를 재고할 만한 문제가 반복적으로 확인되었습니다.",
    EARLY_ADOPTER: "아직 확신할 만큼 독립적인 사용 근거가 충분하지 않습니다.",
  },
  casual: {
    BUY: "지금까지 확인한 근거에서는 구매를 막을 만한 반복 문제가 많지 않아요.",
    BUY_IF: "괜찮은 점은 있지만, 내 사용 조건과 아래 주의점은 먼저 확인해 보세요.",
    SKIP: "여러 독립적인 경험에서 구매를 다시 생각할 만한 문제가 반복됐어요.",
    EARLY_ADOPTER: "아직 믿고 결론 내리기엔 독립적인 사용 근거가 조금 부족해요.",
  },
  community: {
    BUY: "확인된 근거 기준으로는 크게 발목 잡는 반복 문제가 많지 않음.",
    BUY_IF: "장점은 있는데 조건을 좀 타는 편이라 주의점 확인 필요.",
    SKIP: "한두 군데 얘기가 아니라 구매를 말리는 문제가 반복됨.",
    EARLY_ADOPTER: "아직 결론 내릴 만큼 독립 실사용 정보가 안 모임.",
  },
};

const reasonCopy: Record<string, Record<ToneMode, string>> = {
  INSUFFICIENT_EVIDENCE: {
    formal: "판단에 필요한 근거가 아직 충분하지 않습니다.",
    casual: "아직 결론 내리기에는 확인된 근거가 부족해요.",
    community: "결론 내리기엔 근거가 아직 모자람.",
  },
  INSUFFICIENT_EVIDENCE_QUALITY: {
    formal: "의사결정에 사용할 수 있는 근거의 품질이 제한적입니다.",
    casual: "판단에 바로 쓰기 어려운 근거가 많아요.",
    community: "근거 수보다 쓸 만한 근거가 부족함.",
  },
  LOW_EVIDENCE_CONFIDENCE: {
    formal: "현재 근거의 신뢰도가 낮습니다.",
    casual: "지금 모인 근거만 믿고 가기에는 아직 불안해요.",
    community: "지금 근거만으로 확신하기 어려움.",
  },
  INSUFFICIENT_INDEPENDENT_EVIDENCE: {
    formal: "서로 독립적인 근거가 충분하지 않습니다.",
    casual: "서로 다른 곳에서 확인된 경험이 아직 부족해요.",
    community: "독립 출처 수가 아직 부족함.",
  },
  NO_MEANINGFUL_CLAIMS: {
    formal: "구매 판단에 사용할 만한 검증된 주장이 없습니다.",
    casual: "구매 판단에 쓸 만큼 확인된 얘기가 아직 없어요.",
    community: "판단에 넣을 만한 검증 claim이 없음.",
  },
  REPEATED_HIGH_SEVERITY_ISSUE: {
    formal: "중대한 문제가 여러 독립 근거에서 반복되었습니다.",
    casual: "큰 문제가 서로 다른 사용 경험에서 반복해서 나왔어요.",
    community: "큰 문제가 독립 출처 여러 곳에서 반복됨.",
  },
  CONDITIONAL_NEGATIVE_ISSUE: {
    formal: "사용 조건에 따라 주의할 문제가 확인되었습니다.",
    casual: "어떻게 쓰느냐에 따라 신경 써야 할 문제가 있어요.",
    community: "사용 조건 따라 단점이 꽤 갈릴 수 있음.",
  },
  LONG_TERM_NEGATIVE_ISSUE: {
    formal: "장기 사용에서 주의할 문제가 확인되었습니다.",
    casual: "오래 쓴 뒤 나타난 문제를 확인해 볼 필요가 있어요.",
    community: "장기 사용 쪽에서 문제 제보가 나옴.",
  },
  STRONG_POSITIVE_SUPPORT: {
    formal: "구매를 지지하는 독립 근거가 확인되었습니다.",
    casual: "구매를 긍정적으로 볼 만한 독립 근거가 있어요.",
    community: "좋다는 쪽 독립 근거가 확인됨.",
  },
  CONFLICTING_EVIDENCE: {
    formal: "서로 충돌하는 사용 경험이 확인되었습니다.",
    casual: "사용자 경험이 한쪽으로 모이지 않고 엇갈려요.",
    community: "후기가 한쪽으로 안 모이고 갈림.",
  },
  UNRESOLVED_SEVERE_RISK: {
    formal: "추가 확인이 필요한 중대한 위험이 남아 있습니다.",
    casual: "아직 풀리지 않은 큰 위험이 하나 이상 남아 있어요.",
    community: "아직 해소 안 된 큰 리스크가 남음.",
  },
  NO_AFFIRMATIVE_SUPPORT: {
    formal: "구매를 적극 지지할 근거가 충분하지 않습니다.",
    casual: "적극적으로 추천할 만큼의 긍정 근거는 아직 부족해요.",
    community: "적극 추천할 긍정 근거가 부족함.",
  },
  NO_BLOCKING_ISSUES: {
    formal: "반복적으로 확인된 구매 차단 문제가 없습니다.",
    casual: "여러 곳에서 반복된 큰 구매 차단 문제는 없어요.",
    community: "반복 확인된 치명적인 문제는 없음.",
  },
};

export const toneCopy: Record<ToneMode, {
  confidenceDescription: string;
  reasonTitle: string;
  blockingTitle: string;
  blockingEmpty: string;
  unresolvedTitle: string;
  unresolvedEmpty: string;
  evidenceTitle: string;
  evidenceEmpty: string;
  sourceTitle: string;
  sourceDescription: string;
}> = {
  formal: {
    confidenceDescription: "이 값은 제품의 품질 점수나 별점이 아닙니다. 현재 확보된 근거의 양, 독립성, 일치도에 대한 신뢰 수준입니다.",
    reasonTitle: "판단 근거 요약",
    blockingTitle: "구매를 막는 반복 문제",
    blockingEmpty: "현재 기준에서 반복적으로 확인된 차단 이슈가 없습니다.",
    unresolvedTitle: "아직 해소되지 않은 위험",
    unresolvedEmpty: "별도로 표시할 미해결 중대 위험이 없습니다.",
    evidenceTitle: "검증된 주장과 근거",
    evidenceEmpty: "현재 판단에 사용할 수 있는 검증된 주장이 없습니다.",
    sourceTitle: "확인한 출처",
    sourceDescription: "각 주장에 연결된 공개 원문입니다. 커뮤니티 글과 전문 리뷰를 동일한 provenance 기록으로 표시합니다.",
  },
  casual: {
    confidenceDescription: "제품 점수나 별점이 아니라, 지금 모은 근거를 얼마나 믿고 판단할 수 있는지 보여주는 값이에요.",
    reasonTitle: "이렇게 판단했어요",
    blockingTitle: "구매 전에 꼭 볼 문제",
    blockingEmpty: "여러 곳에서 반복해서 나온 큰 차단 문제는 없어요.",
    unresolvedTitle: "아직 확인이 더 필요한 위험",
    unresolvedEmpty: "따로 표시할 만한 미해결 중대 위험은 없어요.",
    evidenceTitle: "확인된 얘기와 근거",
    evidenceEmpty: "지금 판단에 사용할 수 있는 검증된 주장은 없어요.",
    sourceTitle: "어디서 확인했나요",
    sourceDescription: "판단에 사용한 공개 원문을 모았습니다. 링크를 열어 직접 맥락을 확인할 수 있어요.",
  },
  community: {
    confidenceDescription: "제품 점수 아님. 지금 모은 근거가 얼마나 탄탄하고 독립적인지 보는 수치임.",
    reasonTitle: "판단 나온 이유",
    blockingTitle: "구매 막는 이슈",
    blockingEmpty: "반복 확인된 치명적인 문제는 없음.",
    unresolvedTitle: "아직 남은 리스크",
    unresolvedEmpty: "따로 표시할 미해결 중대 리스크는 없음.",
    evidenceTitle: "근거글 모아보기",
    evidenceEmpty: "판단에 넣을 만한 검증 claim이 아직 없음.",
    sourceTitle: "원문 링크",
    sourceDescription: "판단에 들어간 공개 원문 목록. 제목이나 도메인을 누르면 새 창에서 열림.",
  },
};

export function decisionDescription(mode: ToneMode, decision: PurchaseDecision): string {
  return decisionDescriptions[mode][decision];
}

export function reasonText(reason: string, mode: ToneMode): string {
  return reasonCopy[reason]?.[mode] ?? reason.toLowerCase().replaceAll("_", " ");
}

export function counterEvidenceText(analysis: AnalysisResponse, mode: ToneMode): string {
  const attempted = analysis.counter_evidence_attempted;
  const completed = analysis.counter_evidence_completed;
  if (mode === "formal") {
    if (attempted && !completed) return "반대 근거 확인을 시도했지만 검색 서비스가 응답하지 않았습니다. 초기 분석 결과를 유지했습니다.";
    if (completed && analysis.decision_changed) return `추가 근거 확인 후 판단이 ${analysis.initial_decision}에서 ${analysis.decision}(으)로 변경되었습니다.`;
    if (completed) return "반대 근거도 확인했으며, 최종 판단은 유지되었습니다.";
    return "초기 근거가 부족해 반대 근거 추가 검색을 진행하지 않았습니다.";
  }
  if (mode === "casual") {
    if (attempted && !completed) return "반대되는 얘기도 찾아봤지만 검색을 끝내지 못해 초기 결과를 유지했어요.";
    if (completed && analysis.decision_changed) return `좋다는 얘기만 보지 않고 다시 확인한 뒤 ${analysis.initial_decision}에서 ${analysis.decision}(으)로 바뀌었어요.`;
    if (completed) return "좋다는 얘기만 있는 건 아닌지 확인했고, 최종 판단은 그대로예요.";
    return "초기 근거가 부족해서 반대 근거 추가 검색까지 진행하지 않았어요.";
  }
  if (attempted && !completed) return "반대쪽도 찾아봤는데 검색 응답이 안 와서 초기 결과 유지함.";
  if (completed && analysis.decision_changed) return `반대 근거까지 보고 ${analysis.initial_decision} → ${analysis.decision}로 바뀜.`;
  if (completed) return "근데 반대쪽 얘기도 확인함. 결론은 그대로임.";
  return "근거가 부족해서 반대 검색까지는 진행 안 함.";
}
