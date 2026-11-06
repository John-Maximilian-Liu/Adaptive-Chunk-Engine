"use client";
import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import Link from "next/link";

export default function DocumentDetailPage() {
  const params = useParams();
  const search = useSearchParams();
  const id = params.id as string;
  const version = search.get("version") || "";
  const [doc, setDoc] = useState<any>(null);
  const [units, setUnits] = useState<any[]>([]);
  const [parseStatus, setParseStatus] = useState("");

  useEffect(() => {
    (async () => {
      setDoc(await api(`/documents/${id}`));
      const v = version || (await api(`/documents/${id}`)).latest_version_id;
      try {
        setUnits(await api(`/document-versions/${v}/logical-units`));
        setParseStatus(units.length ? "parsed" : "ready");
      } catch {
        setParseStatus("not parsed");
      }
    })();
  }, [id, version]);

  async function parse() {
    const v = version || doc?.latest_version_id;
    setParseStatus("parsing…");
    await api(`/document-versions/${v}/parse`, { method: "POST" });
    setUnits(await api(`/document-versions/${v}/logical-units`));
    setParseStatus("parsed");
  }

  return (
    <div className="space-y-6">
      <h1 className="font-display text-3xl font-bold">{doc?.title || "Document"}</h1>
      <section className="panel p-5">
        <h2 className="text-lg font-semibold">Parsing status</h2>
        <p className="mt-2 text-sm">Status: <strong>{parseStatus || "unknown"}</strong></p>
        <button className="btn mt-3" onClick={parse}>Parse / re-parse</button>
      </section>
      <section className="panel p-5">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Logical units</h2>
          <Link className="btn-secondary no-underline" href={`/strategies?version=${version || doc?.latest_version_id}`}>Strategy workbench</Link>
        </div>
        {units.length === 0 ? <p className="text-sm text-slate/60">No logical units.</p> : (
          <ul className="space-y-2">
            {units.map((u) => (
              <li key={u.logical_unit_id} className="rounded-lg border border-sand px-3 py-2 text-sm">
                <span className="font-semibold">{u.title || u.unit_type}</span>
                <span className="ml-2 text-slate/60">#{u.ordinal} · {u.unit_type}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
