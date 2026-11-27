#!/usr/bin/env python3
"""Fill [[E_*]] / [[W_*]] placeholders in manuscript_submission.md from Stage-E artifacts."""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
RES = HERE.parents[1] / "results" / "public_benchmarks" / "heldout_paired_stage_e"
MS = HERE / "manuscript_submission.md"


def pct(x: float) -> str:
    return f"{x:.1f}"


def main() -> None:
    summary = json.loads((RES / "summary.json").read_text(encoding="utf-8"))
    rows = json.loads((RES / "per_document.json").read_text(encoding="utf-8"))
    walks = []
    wp = RES / "walkthroughs.json"
    if wp.exists():
        walks = json.loads(wp.read_text(encoding="utf-8"))

    by = {c["condition"]: c for c in summary["overall"]["conditions"]}
    n = by["strong_fixed"]["n_docs"]
    repl = {
        "[[E_N]]": str(n),
        "[[E_FIXED]]": pct(by["strong_fixed"]["mean_hidden_evidence_recall"]),
        "[[E_INTR]]": pct(by["intrinsic"]["mean_hidden_evidence_recall"]),
        "[[E_INTR_D]]": pct(by["intrinsic"]["paired_delta_vs_fixed_pp"]),
        "[[E_INTR_DEG]]": pct(by["intrinsic"]["degraded_rate"]),
        "[[E_MICRO]]": pct(by["microloop"]["mean_hidden_evidence_recall"]),
        "[[E_MICRO_D]]": pct(by["microloop"]["paired_delta_vs_fixed_pp"]),
        "[[E_MICRO_DEG]]": pct(by["microloop"]["degraded_rate"]),
        "[[E_HUM]]": pct(by["human_review"]["mean_hidden_evidence_recall"]),
        "[[E_HUM_D]]": pct(by["human_review"]["paired_delta_vs_fixed_pp"]),
        "[[E_HUM_DEG]]": pct(by["human_review"]["degraded_rate"]),
        "[[E_OVERRIDES]]": str(by["human_review"]["review_overrides"]),
        "[[E_MIN_DOC]]": pct(by["human_review"]["review_minutes_per_doc"]),
    }

    # narrative
    hum = by["human_review"]
    micro = by["microloop"]
    fixed = by["strong_fixed"]
    alerts = hum.get("review_alerts", 0)
    narrative = (
        f"Across **{n}** held-out-eligible documents, strong_fixed reaches "
        f"**{pct(fixed['mean_hidden_evidence_recall'])}** mean hidden evidence recall. "
        f"Intrinsic-only is **{pct(by['intrinsic']['mean_hidden_evidence_recall'])}** "
        f"(Δ {pct(by['intrinsic']['paired_delta_vs_fixed_pp'])} pp; "
        f"degraded **{pct(by['intrinsic']['degraded_rate'])}%**). "
        f"Adding diagnostic retrieval feedback (microloop) yields "
        f"**{pct(micro['mean_hidden_evidence_recall'])}** "
        f"(Δ {pct(micro['paired_delta_vs_fixed_pp'])} pp; degraded **{pct(micro['degraded_rate'])}%**). "
        f"The simulated human gate fires on **{alerts}** alerts, overrides **{hum['review_overrides']}** locks, "
        f"costs **{pct(hum['review_minutes_per_doc'])}** min/doc on average, and lands at "
        f"**{pct(hum['mean_hidden_evidence_recall'])}** hidden recall with degraded rate "
        f"**{pct(hum['degraded_rate'])}%**. Bootstrap 95% CIs are in `summary.json`."
    )
    repl["[[E_NARRATIVE]]"] = narrative

    # AMD walkthrough from Stage-D lower + Stage-E walk JSON
    lower = json.loads((RES / "stage_d_lower_intrinsic.json").read_text(encoding="utf-8"))
    amd_l = next(r for r in lower if r["doc_id"] == "AMD_2022_10K")
    repl["[[W_BEST_MICRO]]"] = pct(amd_l["best_micro"])
    repl["[[W_SEL_MICRO]]"] = pct(amd_l["micro"])

    amd_w = next((w for w in walks if w["doc_id"] == "AMD_2022_10K"), None)
    if amd_w:
        locked = amd_w["locked"]
        h = amd_w["hidden_cov_all"]
        repl.update(
            {
                "[[W_FIXED]]": locked["strong_fixed"],
                "[[W_FIXED_H]]": pct(100.0 * h[locked["strong_fixed"]]),
                "[[W_INTR]]": locked["intrinsic"],
                "[[W_INTR_H]]": pct(100.0 * h[locked["intrinsic"]]),
                "[[W_MICRO]]": locked["microloop"],
                "[[W_MICRO_H]]": pct(100.0 * h[locked["microloop"]]),
                "[[W_HUM]]": locked["human_review"],
                "[[W_HUM_H]]": pct(100.0 * h[locked["human_review"]]),
            }
        )
        alert = amd_w["alert"]
        over = amd_w["overrode"]
        repl["[[W_NARRATIVE]]"] = (
            f"Diagnostic alert={'yes' if alert else 'no'}; "
            f"operator override={'yes' if over else 'no'} "
            f"({amd_w['review_minutes']} min credited). "
            f"Hidden recall moves from {pct(100*h[locked['microloop']])} under Auto "
            f"to {pct(100*h[locked['human_review']])} after review "
            f"(strong_fixed={pct(100*h[locked['strong_fixed']])})."
        )
    else:
        for k in (
            "[[W_FIXED]]",
            "[[W_FIXED_H]]",
            "[[W_INTR]]",
            "[[W_INTR_H]]",
            "[[W_MICRO]]",
            "[[W_MICRO_H]]",
            "[[W_HUM]]",
            "[[W_HUM_H]]",
            "[[W_NARRATIVE]]",
        ):
            repl[k] = "TBD"

    text = MS.read_text(encoding="utf-8")
    for k, v in repl.items():
        text = text.replace(k, v)
    leftover = sorted(set(re.findall(r"\[\[[A-Z0-9_]+\]\]", text)))
    MS.write_text(text, encoding="utf-8")
    print("Filled", MS)
    if leftover:
        print("Leftover placeholders:", leftover)
    else:
        print("No placeholders left.")


if __name__ == "__main__":
    main()
