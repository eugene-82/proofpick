import type { SourceSummary } from "@/lib/types";

export function SourceList({ sources }: { sources: SourceSummary[] }) {
  const uniqueSources = Array.from(new Map(sources.map((source) => [source.url, source])).values());
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 sm:p-8">
      <h3 className="text-xl font-bold text-white">확인한 출처</h3>
      <p className="mt-1 text-sm text-slate-400">주요 주장 옆에서도 원문 링크를 확인할 수 있습니다.</p>
      {uniqueSources.length === 0 ? (
        <p className="mt-4 text-sm text-slate-500">표시할 출처가 없습니다.</p>
      ) : (
        <ul className="mt-4 grid gap-3 sm:grid-cols-2">
          {uniqueSources.map((source) => (
            <li className="min-w-0 rounded-xl border border-slate-800 bg-slate-950/50 p-4" key={source.url}>
              <a
                className="block truncate font-medium text-sky-300 underline-offset-4 hover:underline focus-visible:underline"
                href={source.url}
                rel="noopener noreferrer"
                target="_blank"
              >
                {source.title || source.domain} ↗
              </a>
              <p className="mt-1 text-xs text-slate-500">{source.domain}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
