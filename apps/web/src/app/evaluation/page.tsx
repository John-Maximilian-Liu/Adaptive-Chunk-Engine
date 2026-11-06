"use client";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

export default function EvaluationPage() {
  const [profile, setProfile] = useState<any>(null);
  const [run, setRun] = useState<any>(null);
  const [metrics, setMetrics] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      const profiles = await api("/evaluation-profiles");
      setProfile(profiles[0] || await api("/evaluation-profiles", { method:"POST", body: JSON.stringify({ name: "UI Profile" }) }));
    })();
  }, []);

  const enabledWeights = useMemo(() => {
    if (!profile?.metrics) return {};
    const enabled = profile.metrics.filter((m: any) => m.enabled);
    const sum = enabled.reduce((a: number, m: any) => a + (m.configured_weight || 0), 0) || 1;
    return Object.fromEntries(enabled.map((m: any) => [m.name, (m.configured_weight || 0) / sum]));
  }, [profile]);

  async function saveProfile() {
    if (!profile) return;
    try {
      const updated = await api(`/evaluation-profiles/${profile.evaluation_profile_id}`, { method: "PATCH", body: JSON.stringify(profile) });
      setProfile(updated);
      setError("");
    } catch (e: any) {
      setError(e.message);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="font-display text-3xl font-bold">Evaluation</h1>
      <section className="panel space-y-3 p-5">
        <h2 className="text-lg font-semibold">Evaluation profile editor</h2>
        {error && <p className="text-sm text-coral">{error}</p>}
        {profile?.metrics?.map((m: any, idx: number) => (
          <div key={m.name} className="grid grid-cols-1 gap-2 rounded border border-sand p-3 md:grid-cols-5">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={m.enabled} onChange={(e)=>{
                const metrics = [...profile.metrics]; metrics[idx] = { ...m, enabled: e.target.checked }; setProfile({ ...profile, metrics });
              }} />
              {m.label}
            </label>
            <input className="input" type="number" min={0} step={0.01} value={m.configured_weight} onChange={(e)=>{
              const metrics = [...profile.metrics]; metrics[idx] = { ...m, configured_weight: Number(e.target.value) }; setProfile({ ...profile, metrics });
            }} aria-label={`${m.name} weight`} />
            <p className="text-xs text-slate/60">effective: {(enabledWeights[m.name] ?? 0).toFixed(3)}</p>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={m.hard_gate} onChange={(e)=>{
                const metrics = [...profile.metrics]; metrics[idx] = { ...m, hard_gate: e.target.checked }; setProfile({ ...profile, metrics });
              }} /> hard gate
            </label>
            <input className="input" type="number" step={0.01} value={m.target ?? 0} onChange={(e)=>{
              const metrics = [...profile.metrics]; metrics[idx] = { ...m, target: Number(e.target.value) }; setProfile({ ...profile, metrics });
            }} aria-label={`${m.name} target`} />
          </div>
        ))}
        <button className="btn" onClick={saveProfile}>Save profile</button>
      </section>
      <section className="panel p-5">
        <h2 className="mb-2 text-lg font-semibold">Evaluation dashboard</h2>
        <p className="text-sm">Evaluation Accuracy (composite_retrieval_score): <strong>{metrics?.evaluation_accuracy ?? "—"}</strong></p>
        {metrics?.metrics && (
          <ul className="mt-3 space-y-1 text-sm">
            {metrics.metrics.map((m: any) => (
              <li key={m.name}>{m.name}: raw={m.raw_value?.toFixed?.(3) ?? m.raw_value} · contrib={m.contribution?.toFixed?.(3)} · gate={String(m.gate_passed)}</li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
