export default function Home() {
  return (
    <main className="min-h-screen bg-slate-950 px-6 py-16 text-slate-100">
      <section className="mx-auto max-w-3xl rounded-2xl border border-slate-800 bg-slate-900/70 p-8 shadow-2xl shadow-slate-950 sm:p-12">
        <p className="text-sm font-semibold tracking-[0.2em] text-sky-400">PROOFPICK</p>
        <h1 className="mt-4 text-4xl font-bold tracking-tight sm:text-5xl">Decide with evidence, not hype.</h1>
        <p className="mt-5 max-w-2xl text-lg leading-8 text-slate-300">ProofPick will help you evaluate products through evidence gathered from multiple public sources.</p>
        <form className="mt-8 flex flex-col gap-3 sm:flex-row">
          <label className="sr-only" htmlFor="product-query">Product name or URL</label>
          <input id="product-query" className="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-slate-100 outline-none placeholder:text-slate-500 focus:border-sky-400" placeholder="Enter a product name or URL" type="text" />
          <button className="rounded-lg bg-sky-400 px-5 py-3 font-semibold text-slate-950" type="submit">Check evidence</button>
        </form>
        <p className="mt-5 text-sm text-slate-400">Product analysis is coming in the next build steps.</p>
      </section>
    </main>
  );
}
