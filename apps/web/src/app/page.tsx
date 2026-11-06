"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

export default function DashboardPage() {
  const [stats, setStats] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        await api("/admin/seed", { method: "POST" }).catch(() => null);
        setStats(await api("/dashboard"));
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="space-y-6">
      <header className="relative overflow-hidden rounded-2xl border border-sand bg-gradient-to-br from-ink via-slate to-lagoon p-8 text-white shadow-sm">
        <div className="pointer-events-none absolute inset-0 bg-grid opacity-20" />
        <p className="font-display text-4xl font-bold tracking-tight md:text-5xl">Chunk Engine</p>
        <p className="mt-3 max-w-2xl text-sm text-white/85 md:text-base">
          Upload documents, adapt chunk strategies, evaluate retrieval, and govern optimization with full audit evidence.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link href="/documents" className="btn no-underline">
            Upload document
          </Link>
          <Link href="/health" className="btn-secondary no-underline">
            System health
          </Link>
        </div>
      </header>

      {loading && <p className="animate-pulseSoft text-sm text-slate">Loading dashboard…</p>}
      {error && <p className="rounded-lg bg-coral/10 px-3 py-2 text-sm text-coral">{error}</p>}

      {stats && (
        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-label="Summary">
          {[
            ["Documents", stats.documents],
            ["Chunk runs", stats.chunk_runs],
            ["Experiments", stats.experiments],
            ["Evaluations", stats.evaluation_runs],
            ["Indexing runs", stats.indexing_runs],
            ["QA items", stats.qa_items],
          ].map(([label, value]) => (
            <div key={label as string} className="panel p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate/60">{label}</p>
              <p className="mt-2 font-display text-3xl font-bold text-ink">{value}</p>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}
