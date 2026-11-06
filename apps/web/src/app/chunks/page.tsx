"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function ChunksPage() {
  const [runId, setRunId] = useState("");
  const [run, setRun] = useState<any>(null);
  const [chunks, setChunks] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);

  async function load() {
    if (!runId) return;
    setRun(await api(`/chunk-runs/${runId}`));
    setChunks(await api(`/chunk-runs/${runId}/chunks`));
  }

  return (
    <div className="space-y-6">
      <h1 className="font-display text-3xl font-bold">Chunk Explorer</h1>
      <section className="panel flex gap-3 p-5">
        <input className="input" aria-label="Chunk run id" placeholder="Chunk run ID" value={runId} onChange={(e) => setRunId(e.target.value)} />
        <button className="btn" onClick={load}>Load</button>
      </section>
      {run && <p className="text-sm">Status: {run.status} · chunks: {run.chunk_count} · progress {run.progress_percent}%</p>}
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="panel max-h-[70vh] overflow-auto p-4">
          <h2 className="mb-2 font-semibold">Chunks</h2>
          {chunks.length === 0 ? <p className="text-sm text-slate/60">Empty.</p> : chunks.map((c) => (
            <button key={c.chunk_id} className="mb-2 block w-full rounded border border-sand px-3 py-2 text-left text-sm hover:bg-mist" onClick={() => setSelected(c)}>
              <strong>#{c.ordinal}</strong> {c.canonical_strategy} · {c.token_count} tok
              <div className="line-clamp-2 text-slate/70">{c.text}</div>
            </button>
          ))}
        </section>
        <section className="panel p-4">
          <h2 className="mb-2 font-semibold">Evidence</h2>
          {!selected ? <p className="text-sm text-slate/60">Select a chunk.</p> : (
            <pre className="overflow-auto rounded bg-ink p-3 text-xs text-white">{JSON.stringify({
              chunk_id: selected.chunk_id,
              strategy: selected.canonical_strategy,
              element_ids: selected.element_ids,
              locators: selected.locators,
              reason_codes: selected.reason_codes,
              text: selected.text,
            }, null, 2)}</pre>
          )}
        </section>
      </div>
    </div>
  );
}
