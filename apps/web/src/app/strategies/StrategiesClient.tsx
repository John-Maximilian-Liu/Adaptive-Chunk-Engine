"use client";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";

export default function StrategiesPage() {
  const search = useSearchParams();
  const [strategies, setStrategies] = useState<any[]>([]);
  const [units, setUnits] = useState<any[]>([]);
  const [plan, setPlan] = useState<any>(null);
  const [filter, setFilter] = useState("all");
  const [versionId, setVersionId] = useState(search.get("version") || "");
  const [msg, setMsg] = useState("");

  useEffect(() => {
    (async () => {
      setStrategies(await api("/strategies"));
      if (!versionId) {
        const seed = await api("/admin/seed", { method: "POST" });
        setVersionId(seed.demo_document.latest_version_id);
      }
    })();
  }, []);

  useEffect(() => {
    if (!versionId) return;
    (async () => setUnits(await api(`/document-versions/${versionId}/logical-units`)))();
  }, [versionId]);

  const filtered = useMemo(() => {
    return units.filter((u) => {
      if (filter === "table") return (u.profile?.formula_heavy === false && u.unit_type === "sheet") || u.unit_type === "sheet";
      if (filter === "formula") return u.profile?.formula_heavy;
      if (filter === "continuation") return u.profile?.continuation_candidate || u.continuation_group_id;
      if (filter === "low_confidence") return (u.profile?.confidence || 1) < 0.6;
      return true;
    });
  }, [units, filter]);

  async function autoPlan() {
    setMsg("Generating plan…");
    const p = await api(`/document-versions/${versionId}/chunk-plans:auto`, { method: "POST" });
    setPlan(p);
    setMsg(p.status);
  }

  async function updateUnit(unitId: string, strategyId: string) {
    if (!plan) return;
    const updated = await api(`/chunk-plans/${plan.plan_id}/logical-units/${unitId}`, {
      method: "PATCH",
      body: JSON.stringify({ strategy_id: strategyId, mode: "manual", parameters: { chunk_size: 512, chunk_overlap: 64 } }),
    });
    setPlan(updated);
  }

  async function overrideRegion(regionId: string) {
    if (!plan) return;
    const updated = await api(`/chunk-plans/${plan.plan_id}/regions/${regionId}`, {
      method: "PATCH",
      body: JSON.stringify({ strategy_id: "no_split", mode: "manual", parameters: {} }),
    });
    setPlan(updated);
  }

  return (
    <div className="space-y-6">
      <h1 className="font-display text-3xl font-bold">Strategy Workbench</h1>
      <section className="panel flex flex-wrap items-end gap-3 p-5">
        <div>
          <label className="label" htmlFor="version">Document version</label>
          <input id="version" className="input" value={versionId} onChange={(e) => setVersionId(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="filter">Filter</label>
          <select id="filter" className="input" value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="all">All units</option>
            <option value="table">Table units</option>
            <option value="formula">Formula-heavy sheets</option>
            <option value="continuation">Cross-unit continuation</option>
            <option value="low_confidence">Low-confidence</option>
            <option value="manual">Manually modified</option>
            <option value="changed">Changed-strategy</option>
            <option value="eval_fail">Evaluation failure units</option>
          </select>
        </div>
        <button className="btn" onClick={autoPlan}>Auto-generate plan</button>
        {msg && <p className="text-sm text-lagoon">{msg}</p>}
      </section>

      <section className="panel p-5">
        <h2 className="mb-3 text-lg font-semibold">Available strategies</h2>
        <div className="grid gap-2 md:grid-cols-2">
          {strategies.map((s) => (
            <div key={s.strategy_id} className="rounded-lg border border-sand px-3 py-2 text-sm">
              <div className="flex items-center justify-between">
                <strong>{s.display_name}</strong>
                <span className={s.dependency_available && s.enabled ? "text-lagoon" : "text-coral"}>
                  {s.health_status}{s.health_reason ? ` — ${s.health_reason}` : ""}
                </span>
              </div>
              <p className="text-xs text-slate/60">{s.strategy_id} · {s.provider}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="panel p-5">
        <h2 className="mb-3 text-lg font-semibold">Logical-unit strategies</h2>
        <ul className="space-y-3">
          {filtered.map((u) => {
            const cfg = plan?.effective_plan?.unit_strategies?.find((s: any) => s.logical_unit_id === u.logical_unit_id);
            return (
              <li key={u.logical_unit_id} className="rounded-lg border border-sand p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-semibold">{u.title || u.unit_type}</p>
                    <p className="text-xs text-slate/60">{u.logical_unit_id}</p>
                  </div>
                  <select
                    aria-label={`Strategy for ${u.title || u.unit_type}`}
                    className="input max-w-xs"
                    value={cfg?.strategy_id || ""}
                    onChange={(e) => updateUnit(u.logical_unit_id, e.target.value)}
                  >
                    <option value="">Select strategy</option>
                    {strategies.filter((s) => s.enabled !== false).map((s) => (
                      <option key={s.strategy_id} value={s.strategy_id}>{s.display_name}</option>
                    ))}
                  </select>
                </div>
                <div className="mt-2 flex gap-2 text-xs">
                  <span className="rounded bg-sand px-2 py-1">mode: {cfg?.mode || "auto"}</span>
                  <button className="btn-secondary" onClick={() => u.regions?.[0] && overrideRegion(u.regions[0].region_id || Object.keys(u.regions[0])[0])}>Region override</button>
                </div>
              </li>
            );
          })}
        </ul>
      </section>

      {plan && (
        <section className="panel p-5">
          <h2 className="mb-2 text-lg font-semibold">Chunk plan review</h2>
          <p className="text-sm">Plan {plan.plan_id} · status {plan.status} · valid {String(plan.validation?.valid)}</p>
          <pre className="mt-3 max-h-80 overflow-auto rounded bg-ink p-3 text-xs text-white">{JSON.stringify(plan.effective_plan, null, 2)}</pre>
          <button className="btn mt-3" onClick={async () => {
            await api(`/chunk-plans/${plan.plan_id}/review`, { method: "POST", body: JSON.stringify({ decision: "approve" }) });
            const run = await api("/chunk-runs", { method: "POST", body: JSON.stringify({ plan_id: plan.plan_id }) });
            setMsg(`Chunk run ${run.chunk_run_id} → ${run.status}, chunks=${run.chunk_count}`);
          }}>Approve & run chunking</button>
        </section>
      )}
    </div>
  );
}
