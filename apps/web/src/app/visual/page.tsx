"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function VisualPage() {
  const [versionId, setVersionId] = useState("");
  const [policy, setPolicy] = useState({ enabled:true, mode:"auto", generate_ocr:true, generate_caption:true, generate_svg:true, svg_strategy:"auto", svg_indexing_granularity:"group", minimum_confidence:0.8, fallback_behavior:"retain_raster", original_raster_retention:true });
  const [result, setResult] = useState<any>(null);

  useEffect(() => { (async()=>{ const seed = await api("/admin/seed",{method:"POST"}); setVersionId(seed.demo_document.latest_version_id); })(); }, []);

  async function run() {
    const res = await api(`/document-versions/${versionId}/visual-process`, { method:"POST", body: JSON.stringify({
      policy, image_kind: "diagram",
      existing_svg: undefined,
      scene_graph: { nodes:[{node_id:"n1",label:"Ingest",node_type:"process",bbox:[20,20,120,60]},{node_id:"n2",label:"Index",node_type:"process",bbox:[20,100,120,140]}], edges:[{edge_id:"e1",source_node_id:"n1",target_node_id:"n2",label:"next"}], groups:[{group_id:"g1",label:"Pipeline",node_ids:["n1","n2"]}] },
      ocr_text: "Ingest to Index",
      caption: "Document processing pipeline",
    })});
    setResult(res);
  }

  return (
    <div className="space-y-6">
      <h1 className="font-display text-3xl font-bold">Visual Review Workbench</h1>
      <section className="panel grid gap-3 p-5 md:grid-cols-2">
        {Object.entries(policy).map(([k,v]) => (
          <label key={k} className="text-sm">
            <span className="label">{k}</span>
            {typeof v === "boolean" ? (
              <input type="checkbox" checked={v} onChange={(e)=>setPolicy({...policy,[k]:e.target.checked})} />
            ) : (
              <input className="input" value={String(v)} onChange={(e)=>setPolicy({...policy,[k]: k.includes("confidence") ? Number(e.target.value) : e.target.value})} />
            )}
          </label>
        ))}
        <button className="btn md:col-span-2" onClick={run}>Run visual processing</button>
      </section>
      {result && (
        <section className="panel space-y-3 p-5">
          <h2 className="font-semibold">Results</h2>
          <p className="text-sm">Strategy: {result.results?.[0]?.strategy}</p>
          <p className="text-sm">Warnings: {(result.results?.[0]?.warnings||[]).join(", ") || "none"}</p>
          <pre className="max-h-96 overflow-auto rounded bg-ink p-3 text-xs text-white">{JSON.stringify(result,null,2)}</pre>
          <div className="flex gap-2">
            <button className="btn" onClick={async()=>{
              const id = result.results?.[0]?.artifacts?.[0]?.visual_artifact_id;
              if (id) await api(`/visual-artifacts/${id}/review`, { method:"POST", body: JSON.stringify({ decision:"approved" })});
            }}>Approve</button>
            <button className="btn-secondary" onClick={async()=>{
              const id = result.results?.[0]?.artifacts?.[0]?.visual_artifact_id;
              if (id) await api(`/visual-artifacts/${id}/review`, { method:"POST", body: JSON.stringify({ decision:"rejected" })});
            }}>Reject</button>
          </div>
        </section>
      )}
    </div>
  );
}
