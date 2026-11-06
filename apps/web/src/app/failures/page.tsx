"use client";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

export default function FailuresPage() {
  const [runId, setRunId] = useState("");
  const [failures, setFailures] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [category, setCategory] = useState("ALL");
  const [proposal, setProposal] = useState<any>(null);

  const filtered = useMemo(() => failures.filter((f) => category === "ALL" || f.primary_category === category), [failures, category]);
  const dist = useMemo(() => {
    const d: Record<string, number> = {};
    for (const f of failures) d[f.primary_category] = (d[f.primary_category] || 0) + 1;
    return d;
  }, [failures]);

  async function load() {
    setFailures(await api(`/evaluation-runs/${runId}/failures`));
  }

  return (
    <div className="space-y-6">
      <h1 className="font-display text-3xl font-bold">Failure Analysis Workbench</h1>
      <section className="panel flex gap-3 p-5">
        <input className="input" placeholder="Evaluation run ID" value={runId} onChange={(e)=>setRunId(e.target.value)} aria-label="Evaluation run id" />
        <button className="btn" onClick={load}>Load failures</button>
      </section>
      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Object.entries(dist).map(([k,v]) => (
          <div key={k} className="panel p-4"><p className="text-xs uppercase text-slate/60">{k}</p><p className="font-display text-2xl font-bold">{v}</p></div>
        ))}
        <div className="panel p-4"><p className="text-xs uppercase text-slate/60">Total</p><p className="font-display text-2xl font-bold">{failures.length}</p></div>
      </section>
      <div className="grid gap-4 lg:grid-cols-[220px_1fr_1fr]">
        <aside className="panel p-4" aria-label="Filters">
          <p className="mb-2 text-sm font-semibold">Filter</p>
          {["ALL","PARSER","CHUNKING","INDEXING","RETRIEVAL","QA_GROUND_TRUTH"].map((c)=>(
            <button key={c} className={`mb-1 block w-full rounded px-2 py-1 text-left text-sm ${category===c?"bg-lagoon text-white":"hover:bg-sand"}`} onClick={()=>setCategory(c)}>{c}</button>
          ))}
        </aside>
        <section className="panel max-h-[70vh] overflow-auto p-4">
          <h2 className="mb-2 font-semibold">Failure list</h2>
          {filtered.map((f)=>(
            <button key={f.failure_id} className="mb-2 block w-full rounded border border-sand px-3 py-2 text-left text-sm" onClick={()=>setSelected(f)}>
              <strong>{f.primary_category}</strong> · {f.reason_codes?.join(", ")}
              <div className="text-xs text-slate/60">{f.recommended_action}</div>
            </button>
          ))}
        </section>
        <section className="panel space-y-3 p-4">
          <h2 className="font-semibold">Inspector</h2>
          {!selected ? <p className="text-sm text-slate/60">Select a failure.</p> : (
            <>
              <pre className="max-h-64 overflow-auto rounded bg-ink p-3 text-xs text-white">{JSON.stringify(selected, null, 2)}</pre>
              <p className="text-sm">Safe to optimize via chunk config: <strong>{String(selected.safe_to_optimize_via_chunk_config)}</strong></p>
              <div className="flex flex-wrap gap-2">
                <button className="btn" onClick={async()=>{
                  const p = await api(`/evaluation-runs/${runId}/optimization-proposals`, { method:"POST" });
                  setProposal(p);
                }}>Create proposal</button>
                {proposal && (
                  <>
                    <button className="btn-secondary" onClick={async()=>setProposal(await api(`/optimization-proposals/${proposal.proposal_id}/review`,{method:"POST",body:JSON.stringify({decision:"accept"})}))}>Accept</button>
                    <button className="btn-secondary" onClick={async()=>setProposal(await api(`/optimization-proposals/${proposal.proposal_id}/review`,{method:"POST",body:JSON.stringify({decision:"reject"})}))}>Reject</button>
                  </>
                )}
              </div>
              {proposal && <pre className="max-h-48 overflow-auto rounded bg-slate p-3 text-xs text-white">{JSON.stringify(proposal, null, 2)}</pre>}
            </>
          )}
        </section>
      </div>
    </div>
  );
}
