"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function ConnectionsPage() {
  const [llm, setLlm] = useState<any[]>([]);
  const [emb, setEmb] = useState<any[]>([]);
  const [sinks, setSinks] = useState<any[]>([]);
  const [msg, setMsg] = useState("");

  async function refresh() {
    setLlm(await api("/llm-profiles"));
    setEmb(await api("/embedding-profiles"));
    setSinks(await api("/vector-sink-profiles"));
  }
  useEffect(() => { refresh(); }, []);

  return (
    <div className="space-y-6">
      <h1 className="font-display text-3xl font-bold">Connections</h1>
      <p className="text-sm text-slate/70">Secrets are write-only. Values are never returned after save.</p>
      {msg && <p className="text-sm text-lagoon">{msg}</p>}

      <section className="panel space-y-3 p-5">
        <h2 className="font-semibold">LLM (OpenAI / Azure OpenAI / Mock)</h2>
        <button className="btn" onClick={async()=>{
          await api("/llm-profiles", { method:"POST", body: JSON.stringify({ name:"OpenAI", provider:"openai", model:"gpt-4o-mini", api_key:"sk-demo-not-returned" })});
          setMsg("OpenAI profile saved (secret not retrievable)");
          refresh();
        }}>Add OpenAI profile</button>
        <button className="btn-secondary" onClick={async()=>{
          await api("/llm-profiles", { method:"POST", body: JSON.stringify({ name:"Azure OpenAI", provider:"azure_openai", model:"gpt-4o", base_url:"https://example.openai.azure.com", deployment_name:"gpt4", api_key:"azure-demo" })});
          refresh();
        }}>Add Azure OpenAI profile</button>
        <ul className="text-sm">{llm.map(p=> <li key={p.llm_profile_id}>{p.name} · {p.provider} · has_credential={String(p.has_credential)}</li>)}</ul>
      </section>

      <section className="panel space-y-3 p-5">
        <h2 className="font-semibold">Embedding profiles</h2>
        <ul className="text-sm">{emb.map(p=> <li key={p.embedding_profile_id}>{p.name} · {p.provider} · dims={p.dimensions}</li>)}</ul>
      </section>

      <section className="panel space-y-3 p-5">
        <h2 className="font-semibold">Vector destinations</h2>
        <button className="btn-secondary" onClick={async()=>{
          await api("/vector-sink-profiles", { method:"POST", body: JSON.stringify({ name:"Azure AI Search", sink_type:"azure_ai_search", collection_or_index:"ace-chunks", connection:{ endpoint:"https://example.search.windows.net" }, api_key:"search-demo" })});
          refresh();
        }}>Add Azure AI Search</button>
        <button className="btn-secondary" onClick={async()=>{
          await api("/vector-sink-profiles", { method:"POST", body: JSON.stringify({ name:"Dify KB", sink_type:"dify", collection_or_index:"ds1", connection:{ base_url:"https://api.dify.ai/v1", dataset_id:"ds1" }, api_key:"dify-demo", embedding_ownership:"sink_managed", required:false })});
          refresh();
        }}>Add Dify Knowledge Base</button>
        <ul className="text-sm">{sinks.map(p=> <li key={p.vector_sink_profile_id}>{p.name} · {p.sink_type} · required={String(p.required)}</li>)}</ul>
      </section>
    </div>
  );
}
