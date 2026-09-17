function humanizeReason(reason: string) {
  const copy: Record<string, string> = {
    INSUFFICIENT_EVIDENCE: "판단에 필요한 근거가 아직 충분하지 않습니다.",
    INSUFFICIENT_EVIDENCE_QUALITY: "의사결정에 사용할 수 있는 근거의 품질이 제한적입니다.",
    LOW_EVIDENCE_CONFIDENCE: "현재 근거의 신뢰도가 낮습니다.",
    INSUFFICIENT_INDEPENDENT_EVIDENCE: "서로 독립적인 근거가 충분하지 않습니다.",
    NO_MEANINGFUL_CLAIMS: "구매 판단에 사용할 만한 검증된 주장이 없습니다.",
    REPEATED_HIGH_SEVERITY_ISSUE: "중대한 문제가 여러 독립 근거에서 반복되었습니다.",
    CONDITIONAL_NEGATIVE_ISSUE: "사용 조건에 따라 주의할 문제가 확인되었습니다.",
    LONG_TERM_NEGATIVE_ISSUE: "장기 사용에서 주의할 문제가 확인되었습니다.",
    STRONG_POSITIVE_SUPPORT: "구매를 지지하는 독립 근거가 확인되었습니다.",
    CONFLICTING_EVIDENCE: "서로 충돌하는 사용 경험이 확인되었습니다.",
    UNRESOLVED_SEVERE_RISK: "추가 확인이 필요한 중대한 위험이 남아 있습니다.",
    NO_AFFIRMATIVE_SUPPORT: "구매를 적극 지지할 근거가 충분하지 않습니다.",
    NO_BLOCKING_ISSUES: "반복적으로 확인된 구매 차단 문제가 없습니다.",
  };
  return copy[reason] ?? reason.toLowerCase().replaceAll("_", " ");
}

export function ReasonList({ reasons }: { reasons: string[] }) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
      <h3 className="text-lg font-bold text-white">이 판단이 나온 이유</h3>
      <ul className="mt-4 space-y-3">
        {reasons.map((reason) => (
          <li className="flex gap-3 text-sm leading-6 text-slate-300" key={reason}>
            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-sky-400" aria-hidden="true" />
            {humanizeReason(reason)}
          </li>
        ))}
      </ul>
    </section>
  );
}
