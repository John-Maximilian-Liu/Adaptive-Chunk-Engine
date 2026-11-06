import { Suspense } from "react";
import StrategiesClient from "./StrategiesClient";

export default function Page() {
  return (
    <Suspense fallback={<p className="text-sm text-slate">Loading strategy workbench…</p>}>
      <StrategiesClient />
    </Suspense>
  );
}
