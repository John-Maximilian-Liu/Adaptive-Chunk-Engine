"use client";
import { useState } from "react";
import { api } from "@/lib/api";

export default function ExperimentsPage() {
  const [runId, setRunId] = useState("");
  const [cmp, setCmp] = useState<any>(null);
  return (
    <div className="space-y-6">
      <h1 className="font-display text-3xl font-bold">Experiment Comparison</h1>
      <section className="panel flex gap-3 p-5">
        <input className="input" value={runId} onChange={(e)=>setRunId(e.target.value)} placeholder="Evaluation run ID" aria-label="Eval run" />
        <button className="btn" onClick={async()=>setCmp(await api(`/evaluation-runs/${runId}/comparison`))}>Compare</button>
      </section>
      {cmp && <pre className="panel overflow-auto p-4 text-sm">{JSON.stringify(cmp,null,2)}</pre>}
    </div>
  );
}
