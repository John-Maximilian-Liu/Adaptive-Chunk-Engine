"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";

const LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/documents", label: "Documents" },
  { href: "/strategies", label: "Strategy Workbench" },
  { href: "/chunks", label: "Chunks" },
  { href: "/qa", label: "QA" },
  { href: "/evaluation", label: "Evaluation" },
  { href: "/failures", label: "Failures" },
  { href: "/optimization", label: "Optimization" },
  { href: "/experiments", label: "Experiments" },
  { href: "/connections", label: "Connections" },
  { href: "/indexing", label: "Indexing" },
  { href: "/audit", label: "Audit" },
  { href: "/visual", label: "Visual" },
  { href: "/health", label: "Health" },
];

export function Nav() {
  const pathname = usePathname();
  return (
    <aside className="panel sticky top-4 flex h-[calc(100vh-2rem)] w-64 shrink-0 flex-col overflow-hidden p-4 animate-rise">
      <div className="mb-6">
        <p className="font-display text-2xl font-bold tracking-tight text-ink">Chunk Engine</p>
        <p className="mt-1 text-xs text-slate/70">Adaptive RAG governance</p>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto pr-1" aria-label="Primary">
        {LINKS.map((l) => {
          const active = pathname === l.href || (l.href !== "/" && pathname.startsWith(l.href));
          return (
            <Link
              key={l.href}
              href={l.href}
              className={clsx(
                "block rounded-lg px-3 py-2 text-sm no-underline transition",
                active ? "bg-lagoon text-white" : "text-slate hover:bg-sand/60",
              )}
            >
              {l.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
