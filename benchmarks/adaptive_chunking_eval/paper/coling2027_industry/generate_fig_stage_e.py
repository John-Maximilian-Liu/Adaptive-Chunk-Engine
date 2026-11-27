#!/usr/bin/env python3
"""Generate Stage-E held-out figures from summary.json / per_document.json."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "results" / "public_benchmarks" / "heldout_paired_stage_e"
FIG = Path(__file__).resolve().parent / "figures"

CONDS = ["strong_fixed", "intrinsic", "microloop", "human_review"]
LABELS = {
    "strong_fixed": "① strong fixed",
    "intrinsic": "② intrinsic",
    "microloop": "③ + microloop",
    "human_review": "④ + human review",
}
COLORS = ["#64748b", "#0d9488", "#1d4ed8", "#b45309"]


def main() -> None:
    summary = json.loads((RES / "summary.json").read_text(encoding="utf-8"))
    rows = json.loads((RES / "per_document.json").read_text(encoding="utf-8"))
    FIG.mkdir(parents=True, exist_ok=True)

    # Fig: overall mean hidden recall + degraded rate
    conds = summary["overall"]["conditions"]
    by = {c["condition"]: c for c in conds}
    fig, ax1 = plt.subplots(figsize=(8.2, 4.0))
    x = np.arange(len(CONDS))
    recalls = [by[c]["mean_hidden_evidence_recall"] for c in CONDS]
    deg = [by[c]["degraded_rate"] for c in CONDS]
    bars = ax1.bar(x - 0.18, recalls, width=0.36, color=COLORS, edgecolor="white", label="Mean hidden evidence recall")
    ax2 = ax1.twinx()
    ax2.plot(x + 0.18, deg, "o--", color="#b91c1c", label="Degraded docs %", markersize=8)
    ax1.set_xticks(x)
    ax1.set_xticklabels([LABELS[c] for c in CONDS], fontsize=9)
    ax1.set_ylabel("Hidden evidence recall (0–100)")
    ax2.set_ylabel("Degraded document rate (%)")
    ax1.set_ylim(0, 105)
    ax2.set_ylim(0, max(deg + [5]) * 1.35)
    for b, v, c in zip(bars, recalls, CONDS):
        ci = by[c]["hidden_recall_ci95"]
        ax1.text(b.get_x() + b.get_width() / 2, v + 1.2, f"{v:.1f}", ha="center", fontsize=8)
        ax1.plot([b.get_x() + b.get_width() / 2] * 2, ci, color="#111827", linewidth=1.2)
    ax1.set_title("Stage E — held-out paired conditions (shared dense+rerank stack)")
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="lower right", fontsize=8)
    ax1.spines["top"].set_visible(False)
    fig.tight_layout()
    out1 = FIG / "fig_stage_e_heldout.png"
    fig.savefig(out1, dpi=180, bbox_inches="tight")
    print("Wrote", out1)

    # Paired deltas plot
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    deltas = [by[c]["paired_delta_vs_fixed_pp"] for c in CONDS]
    ax.bar(range(4), deltas, color=COLORS, edgecolor="white")
    ax.axhline(0, color="#111827", linewidth=0.8)
    ax.set_xticks(range(4))
    ax.set_xticklabels([LABELS[c] for c in CONDS], fontsize=9)
    ax.set_ylabel("Paired Δ hidden recall vs strong_fixed (pp)")
    ax.set_title("Stage E — paired gains on held-out questions")
    for i, v in enumerate(deltas):
        ax.text(i, v + (0.4 if v >= 0 else -0.8), f"{v:+.1f}", ha="center", fontsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    out2 = FIG / "fig_stage_e_paired_delta.png"
    fig.savefig(out2, dpi=180, bbox_inches="tight")
    print("Wrote", out2)

    # Review funnel
    hr = [r for r in rows if r["condition"] == "human_review"]
    n = len(hr)
    alerts = sum(1 for r in hr if r.get("review_alert"))
    overrides = sum(1 for r in hr if r.get("review_overrode"))
    rescued = sum(
        1
        for r in hr
        if r.get("review_overrode") and not r.get("degraded_vs_fixed")
    )
    print(f"review funnel: n={n} alerts={alerts} overrides={overrides} non-degraded_after_override={rescued}")


if __name__ == "__main__":
    main()
