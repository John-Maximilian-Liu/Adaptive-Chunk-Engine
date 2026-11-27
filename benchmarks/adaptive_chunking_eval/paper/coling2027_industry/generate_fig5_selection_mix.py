#!/usr/bin/env python3
"""Regenerate fig5_selection_mix.png from Stage-D adaptive_ace locks (single source of truth)."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
STAGE_D = ROOT / "results" / "public_benchmarks" / "openrouter_full_stage_d"
OUT = Path(__file__).resolve().parent / "figures" / "fig5_selection_mix.png"

ORDER = [
    "fixed_token_256",
    "fixed_token_512",
    "recursive_text",
    "recursive_text_1100",
    "sentence_window",
    "heading_section",
]
SHORT = {
    "fixed_token_256": "fixed_256",
    "fixed_token_512": "fixed_512",
    "recursive_text": "rec",
    "recursive_text_1100": "rec_1100",
    "sentence_window": "sent_win",
    "heading_section": "heading",
}
CORPORA = [
    ("clair", "CLAIR (n=33)"),
    ("financebench", "FinanceBench (n=18)"),
    ("open_rag_bench", "Open RAG Bench (n=4)"),
]


def main() -> None:
    mixes = {}
    for key, _ in CORPORA:
        data = json.loads((STAGE_D / f"{key}.json").read_text(encoding="utf-8"))
        c = Counter(
            row["selected"]
            for row in data["per_document"]
            if row.get("method") == "adaptive_ace"
        )
        mixes[key] = c
        print(key, dict(c), "n=", sum(c.values()))

    fig, axes = plt.subplots(1, 3, figsize=(11.2, 3.6), sharey=False)
    colors = {
        "fixed_token_256": "#94a3b8",
        "fixed_token_512": "#64748b",
        "recursive_text": "#0d9488",
        "recursive_text_1100": "#1e3a5f",
        "sentence_window": "#ca8a04",
        "heading_section": "#7c3aed",
    }
    for ax, (key, title) in zip(axes, CORPORA):
        c = mixes[key]
        labels = [SHORT[s] for s in ORDER if c.get(s, 0)]
        vals = [c[s] for s in ORDER if c.get(s, 0)]
        cols = [colors[s] for s in ORDER if c.get(s, 0)]
        bars = ax.bar(range(len(vals)), vals, color=cols, edgecolor="white", width=0.72)
        ax.set_xticks(range(len(vals)))
        ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=8)
        ax.set_title(title, fontsize=11)
        ax.set_ylabel("Documents locked" if key == "clair" else "")
        ymax = max(vals) + 1
        ax.set_ylim(0, ymax)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.08, str(v), ha="center", va="bottom", fontsize=9)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    fig.suptitle("Figure 5  Per-document strategy locks (Stage-D adaptive_ace)", fontsize=12, y=1.02)
    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=180, bbox_inches="tight")
    print("Wrote", OUT)


if __name__ == "__main__":
    main()
