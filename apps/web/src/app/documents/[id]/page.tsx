import { Suspense } from "react";
import DocumentClient from "./DocumentClient";

export default function Page() {
  return (
    <Suspense fallback={<p className="text-sm text-slate">Loading document…</p>}>
      <DocumentClient />
    </Suspense>
  );
}
