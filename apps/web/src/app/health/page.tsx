"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function HealthPage() {
  const [live, setLive] = useState<any>(null);
  const [ready, setReady] = useState<any>(null);
  const [deps, setDeps] = useState<any>(null);
  const [version, setVersion] = useState<any>(null);
  useEffect(() => {
    (async () => {
      setLive(await api("/health/live"));
      setReady(await api("/health/ready"));
      setDeps(await api("/health/dependencies"));
      setVersion(await api("/version"));
    })();
  }, []);
  return (
    <div className="space-y-6">
      <h1 className="font-display text-3xl font-bold">System Health</h1>
      <pre className="panel overflow-auto p-4 text-sm">{JSON.stringify({ live, ready, version, deps }, null, 2)}</pre>
    </div>
  );
}
