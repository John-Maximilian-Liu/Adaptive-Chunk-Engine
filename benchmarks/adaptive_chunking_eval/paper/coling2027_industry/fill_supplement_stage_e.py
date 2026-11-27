#!/usr/bin/env python3
"""Fill [[E_*]] / [[W_*]] in SUPPLEMENT_StageE_改动映射.md only (does NOT touch 改8)."""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
RES = HERE.parents[1] / "results" / "public_benchmarks" / "heldout_paired_stage_e"
DOC = HERE / "SUPPLEMENT_StageE_改动映射.md"


def pct(x: float) -> str:
    return f"{x:.1f}"


def main() -> None:
    summary = json.loads((RES / "summary.json").read_text(encoding="utf-8"))
    walks = []
    if (RES / "walkthroughs.json").exists():
        walks = json.loads((RES / "walkthroughs.json").read_text(encoding="utf-8"))

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

    for ds, key in (
        ("clair", "CLAIR"),
        ("financebench", "FB"),
        ("open_rag_bench", "ORB"),
    ):
        block = summary["per_dataset"].get(ds) or {}
        repl[f"[[E_{key}_N]]"] = str(block.get("n_docs", ""))
        repl[f"[[E_{key}_FIXED]]"] = str(block.get("corpus_diag_best") or block.get("strong_fixed") or "")

    hum = by["human_review"]
    micro = by["microloop"]
    fixed = by["strong_fixed"]
    alerts = hum.get("review_alerts", 0)
    repl["[[E_NARRATIVE]]"] = (
        f"Across **{n}** held-out-eligible documents, strong_fixed reaches "
        f"**{pct(fixed['mean_hidden_evidence_recall'])}** mean hidden evidence recall. "
        f"Intrinsic-only **{pct(by['intrinsic']['mean_hidden_evidence_recall'])}** "
        f"(Δ {pct(by['intrinsic']['paired_delta_vs_fixed_pp'])} pp; "
        f"degraded **{pct(by['intrinsic']['degraded_rate'])}%**). "
        f"Microloop **{pct(micro['mean_hidden_evidence_recall'])}** "
        f"(Δ {pct(micro['paired_delta_vs_fixed_pp'])} pp; degraded **{pct(micro['degraded_rate'])}%**). "
        f"Human gate: **{alerts}** alerts, **{hum['review_overrides']}** overrides, "
        f"**{pct(hum['review_minutes_per_doc'])}** min/doc → "
        f"**{pct(hum['mean_hidden_evidence_recall'])}** hidden recall "
        f"(degraded **{pct(hum['degraded_rate'])}%**)."
    )

    lower = json.loads((RES / "stage_d_lower_intrinsic.json").read_text(encoding="utf-8"))
    amd_l = next(r for r in lower if r["doc_id"] == "AMD_2022_10K")
    # keep Stage-D facts already in prose; fill Stage-E walk
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
        repl["[[W_NARRATIVE]]"] = (
            f"Diagnostic alert={'yes' if amd_w['alert'] else 'no'}; "
            f"override={'yes' if amd_w['overrode'] else 'no'} "
            f"({amd_w['review_minutes']} min). "
            f"Hidden recall: microloop {pct(100*h[locked['microloop']])} → "
            f"human {pct(100*h[locked['human_review']])} "
            f"(strong_fixed {pct(100*h[locked['strong_fixed']])})."
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
            repl[k] = "TBD（等 Stage E 跑完）"

    text = DOC.read_text(encoding="utf-8")
    for k, v in repl.items():
        text = text.replace(k, v)
    # stamp status
    import datetime as dt

    stamp = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    text = re.sub(
        r"- Runner：.*",
        f"- Runner：完成于 {stamp}；数值已写入 Table S1–S3。",
        text,
        count=1,
    )
    leftover = sorted(set(re.findall(r"\[\[[A-Z0-9_]+\]\]", text)))
    DOC.write_text(text, encoding="utf-8")
    print("Filled", DOC)
    if leftover:
        print("Leftover:", leftover)


if __name__ == "__main__":
    main()
