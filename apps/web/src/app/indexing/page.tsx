"use client";
import { useState } from "react";
import { api } from "@/lib/api";

export default function IndexingPage() {
  const [runId, setRunId] = useState("");
  const [run, setRun] = useState<any>(null);
  const [targets, setTargets] = useState<any[]>([]);
  return (
    <div className="space-y-6">
      <h1 className="font-display text-3xl font-bold">Indexing Runs</h1>
      <section className="panel flex gap-3 p-5">
        <input className="input" value={runId} onChange={(e)=>setRunId(e.target.value)} placeholder="Indexing run ID" aria-label="Indexing run" />
        <button className="btn" onClick={async()=>{ setRun(await api(`/indexing-runs/${runId}`)); setTargets(await api(`/indexing-runs/${runId}/targets`)); }}>Load</button>
        <button className="btn-secondary" onClick={async()=>setRun(await api(`/indexing-runs/${runId}/retry`,{method:"POST"}))}>Retry</button>
        <button className="btn-secondary" onClick={async()=>setRun(await api(`/indexing-runs/${runId}/cancel`,{method:"POST"}))}>Cancel</button>
      </section>
      {run && <pre className="panel overflow-auto p-4 text-sm">{JSON.stringify({run, targets}, null, 2)}</pre>}
    </div>
  );
}
