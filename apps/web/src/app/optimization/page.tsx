"use client";
import { useState } from "react";
import { api } from "@/lib/api";

export default function OptimizationPage() {
  const [proposalId, setProposalId] = useState("");
  const [proposal, setProposal] = useState<any>(null);
  const [nextExp, setNextExp] = useState<any>(null);
  const [msg, setMsg] = useState("");

  async function load() { setProposal(await api(`/optimization-proposals/${proposalId}`)); }
  async function createNext() {
    const exp = await api(`/optimization-proposals/${proposalId}/create-next-experiment`, { method: "POST" });
    setNextExp(exp);
    setMsg("Next experiment created — chunking was NOT auto-started.");
  }

  return (
    <div className="space-y-6">
      <h1 className="font-display text-3xl font-bold">Optimization Proposal Review</h1>
      <section className="panel flex gap-3 p-5">
        <input className="input" value={proposalId} onChange={(e)=>setProposalId(e.target.value)} placeholder="Proposal ID" aria-label="Proposal id" />
        <button className="btn" onClick={load}>Load</button>
      </section>
      {proposal && (
        <section className="panel space-y-3 p-5">
          <p>Status: {proposal.status}</p>
          <p className="text-sm">Stopping recommendation: {JSON.stringify(proposal.stopping_recommendation)}</p>
          <ul className="space-y-2 text-sm">
            {(proposal.changes||[]).map((c:any)=>(
              <li key={c.change_id} className="rounded border border-sand p-3">
                <code>{c.op} {c.path}</code>: {JSON.stringify(c.before)} → {JSON.stringify(c.after)}
              </li>
            ))}
          </ul>
          <div className="flex gap-2">
            <button className="btn" onClick={async()=>setProposal(await api(`/optimization-proposals/${proposalId}/review`,{method:"POST",body:JSON.stringify({decision:"accept"})}))}>Accept</button>
            <button className="btn-secondary" onClick={async()=>setProposal(await api(`/optimization-proposals/${proposalId}/review`,{method:"POST",body:JSON.stringify({decision:"reject"})}))}>Reject</button>
            <button className="btn" onClick={createNext}>Create next experiment (manual)</button>
          </div>
          {msg && <p className="text-sm text-lagoon">{msg}</p>}
          {nextExp && <pre className="overflow-auto rounded bg-ink p-3 text-xs text-white">{JSON.stringify(nextExp,null,2)}</pre>}
        </section>
      )}
    </div>
  );
}
