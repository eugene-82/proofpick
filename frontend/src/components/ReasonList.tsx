import { reasonText, toneCopy, type ToneMode } from "@/lib/toneMode";


export function ReasonList({ reasons, mode }: { reasons: string[]; mode: ToneMode }) {
  return (
    <section aria-labelledby="reason-title">
      <h3 className="text-lg font-semibold tracking-[-0.02em] text-[#18211d]" id="reason-title">{toneCopy[mode].reasonTitle}</h3>
      <ol className="mt-3 divide-y divide-[#ded9ce] border-y border-[#ded9ce]">
        {reasons.map((reason, index) => (
          <li className="grid grid-cols-[2rem_1fr] gap-2 py-3 text-sm leading-6 text-[#455049]" key={reason}>
            <span className="font-mono text-xs text-[#7a837d]" aria-hidden="true">0{index + 1}</span>
            <span>{reasonText(reason, mode)}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
