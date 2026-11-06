"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

export default function DocumentsPage() {
  const [docs, setDocs] = useState<any[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  async function refresh() {
    const dash = await api("/dashboard");
    // list via seed demo + uploaded by fetching strategies path workaround: use parse of known docs through local state
    setDocs((prev) => prev);
  }

  useEffect(() => {
    (async () => {
      try {
        const seed = await api("/admin/seed", { method: "POST" });
        const demo = seed.demo_document;
        setDocs([demo]);
      } catch (e: any) {
        setError(e.message);
      }
    })();
  }, []);

  async function upload() {
    if (!file) return;
    setStatus("Uploading…");
    setError("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      const doc = await api("/documents", { method: "POST", body: fd });
      setDocs((d) => [doc, ...d]);
      setStatus("Uploaded. Parsing…");
      const versionId = doc.latest_version_id;
      await api(`/document-versions/${versionId}/parse`, { method: "POST" });
      setStatus("Parsed successfully.");
    } catch (e: any) {
      setError(e.message);
      setStatus("");
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="font-display text-3xl font-bold">Documents</h1>
      <section className="panel space-y-4 p-5">
        <h2 className="text-lg font-semibold">Upload</h2>
        <p className="text-sm text-slate/70">PDF, DOCX, PPTX, XLSX, CSV, Markdown, plain text, PNG/JPEG/TIFF.</p>
        <input aria-label="Document file" type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} />
        <button className="btn" onClick={upload} disabled={!file}>Upload & parse</button>
        {status && <p className="text-sm text-lagoon">{status}</p>}
        {error && <p className="text-sm text-coral">{error}</p>}
      </section>
      <section className="panel p-5">
        <h2 className="mb-3 text-lg font-semibold">Document overview</h2>
        {docs.length === 0 ? <p className="text-sm text-slate/60">No documents yet.</p> : (
          <ul className="space-y-2">
            {docs.map((d) => (
              <li key={d.document_id} className="flex items-center justify-between rounded-lg border border-sand px-3 py-2">
                <div>
                  <p className="font-semibold">{d.title}</p>
                  <p className="text-xs text-slate/60">{d.source_format} · {d.document_id}</p>
                </div>
                <Link className="btn-secondary no-underline" href={`/documents/${d.document_id}?version=${d.latest_version_id}`}>Open</Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
