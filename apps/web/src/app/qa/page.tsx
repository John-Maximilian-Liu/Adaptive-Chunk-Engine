"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const TYPES = ["direct_fact","definition","conditional","cross_paragraph","cross_unit","table_lookup","table_aggregation","formula_reasoning","hard_negative","multi_hop"];

export default function QAPage() {
  const [versionId, setVersionId] = useState("");
  const [dataset, setDataset] = useState<any>(null);
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(20);
  const [mode, setMode] = useState("percentage");
  const [dist, setDist] = useState<Record<string, number>>(() => Object.fromEntries(TYPES.map((t,i)=>[t, i===0?20: i<5?10:5])));
  const [msg, setMsg] = useState("");

  useEffect(() => {
    (async () => {
      const seed = await api("/admin/seed", { method: "POST" });
      setVersionId(seed.demo_document.latest_version_id);
    })();
  }, []);

  async function createDataset() {
    const d = await api("/qa-datasets", { method: "POST", body: JSON.stringify({
      document_version_id: versionId,
      name: "QA Dataset",
      distribution: { mode, total, by_type: dist },
    })});
    setDataset(d);
    setMsg("Dataset created");
  }

  async function generate() {
    const res = await api(`/qa-datasets/${dataset.qa_dataset_id}/generate`, { method: "POST", body: JSON.stringify({ count: total }) });
    setItems(await api(`/qa-datasets/${dataset.qa_dataset_id}/items`));
    setMsg(`Generated ${res.count}`);
  }

  async function uploadMinimal() {
    const res = await api(`/qa-datasets/${dataset.qa_dataset_id}/upload`, {
      method: "POST",
      body: (() => { const fd = new FormData(); fd.append("items_json", JSON.stringify([{ question: "What is Revenue for Pro?", answer: "5000" }])); return fd; })(),
    });
    await api(`/qa-datasets/${dataset.qa_dataset_id}/complete-schema`, { method: "POST" });
    setItems(await api(`/qa-datasets/${dataset.qa_dataset_id}/items`));
    setMsg(`Uploaded & schema-completed ${res.created.length}`);
  }

  const pctSum = Object.values(dist).reduce((a,b)=>a+b,0);

  return (
    <div className="space-y-6">
      <h1 className="font-display text-3xl font-bold">QA Dataset Manager</h1>
      <section className="panel space-y-3 p-5">
        <h2 className="text-lg font-semibold">Generation configuration</h2>
        <label className="label">Total count</label>
        <input className="input max-w-xs" type="number" value={total} onChange={(e)=>setTotal(Number(e.target.value))} />
        <label className="label">Distribution mode</label>
        <select className="input max-w-xs" value={mode} onChange={(e)=>setMode(e.target.value)}>
          <option value="percentage">Percentage</option>
          <option value="absolute">Absolute counts</option>
        </select>
        <div className="grid gap-2 md:grid-cols-2">
          {TYPES.map((t) => (
            <label key={t} className="flex items-center justify-between gap-2 text-sm">
              <span>{t}</span>
              <input className="input max-w-[100px]" type="number" value={dist[t]} onChange={(e)=>setDist({...dist,[t]:Number(e.target.value)})} />
            </label>
          ))}
        </div>
        <p className={`text-sm ${mode==="percentage" && Math.abs(pctSum-100)>0.01 ? "text-coral":"text-lagoon"}`}>
          {mode==="percentage" ? `Percent sum: ${pctSum}` : `Count sum: ${pctSum} / total ${total}`}
        </p>
        <div className="flex flex-wrap gap-2">
          <button className="btn" onClick={createDataset}>Create dataset</button>
          <button className="btn" disabled={!dataset} onClick={generate}>Generate QA</button>
          <button className="btn-secondary" disabled={!dataset} onClick={uploadMinimal}>Upload Q+A & complete schema</button>
        </div>
        {msg && <p className="text-sm text-lagoon">{msg}</p>}
      </section>
      <section className="panel p-5">
        <h2 className="mb-3 text-lg font-semibold">Items / schema-completion review</h2>
        {items.length === 0 ? <p className="text-sm text-slate/60">No items.</p> : items.map((qa)=>(
          <div key={qa.qa_id} className="mb-3 rounded border border-sand p-3 text-sm">
            <p className="font-semibold">{qa.question}</p>
            <p className="text-slate/70">{qa.answer}</p>
            <p className="text-xs">type={qa.question_type} · review={qa.review_status} · confidence={qa.confidence ?? "n/a"}</p>
            <button className="btn-secondary mt-2" onClick={async()=>{
              await api(`/qa-items/${qa.qa_id}`, { method:"PATCH", body: JSON.stringify({ review_status: "approved", answer: qa.answer })});
              setItems(await api(`/qa-datasets/${dataset.qa_dataset_id}/items`));
            }}>Approve edit</button>
          </div>
        ))}
      </section>
    </div>
  );
}
