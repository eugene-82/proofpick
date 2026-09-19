const work = ["제품 식별", "공개 근거 탐색", "주장·출처 검토", "반대 근거 확인", "판단 정리"];

export function AnalysisLoading() {
  return (
    <section
      aria-live="polite"
      aria-busy="true"
      className="border-y border-[#b9c9c1] bg-[#eef3ef] px-1 py-6 sm:px-5 sm:py-8"
    >
      <div className="flex items-start gap-4 sm:gap-5">
        <span className="mt-1.5 h-3 w-3 shrink-0 animate-pulse bg-[#175c49] motion-reduce:animate-none" aria-hidden="true" />
        <div>
          <p className="font-semibold text-[#183c31]">근거 조사를 진행하고 있습니다</p>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[#59675f]">
            검색과 검증에는 수 초에서 수 분이 걸릴 수 있습니다. 아래 항목은 조사 범위이며, 실시간 진행 단계나 완료율을 뜻하지 않습니다.
          </p>
        </div>
      </div>
      <ul className="mt-6 grid gap-x-6 gap-y-2 border-t border-[#cbd6d0] pt-4 text-sm text-[#56645d] sm:grid-cols-2 lg:grid-cols-5">
        {work.map((label, index) => (
          <li className="flex items-center gap-2" key={label}>
            <span className="font-mono text-xs text-[#7a8881]" aria-hidden="true">0{index + 1}</span>
            {label}
          </li>
        ))}
      </ul>
    </section>
  );
}
