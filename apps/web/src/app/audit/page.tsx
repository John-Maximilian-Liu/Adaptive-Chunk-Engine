"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function AuditPage() {
  const [events, setEvents] = useState<any[]>([]);
  useEffect(() => { (async()=>setEvents(await api("/audit-events")))(); }, []);
  return (
    <div className="space-y-6">
      <h1 className="font-display text-3xl font-bold">Evidence & Audit History</h1>
      <section className="panel p-5">
        {events.length === 0 ? <p className="text-sm text-slate/60">No audit events.</p> : (
          <ul className="space-y-2 text-sm">
            {events.map((e)=>(
              <li key={e.audit_event_id} className="rounded border border-sand px-3 py-2">
                <strong>{e.action}</strong> · {e.entity_type}/{e.entity_id} · {e.actor_type}:{e.actor_id}
                <div className="text-xs text-slate/60">{e.timestamp}</div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
