#!/usr/bin/env python3
"""Regenerate appendix Figures A1–A6 (ACE-advantage visualizations)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

FIG = Path(__file__).resolve().parent / "figures"
ACCENT = "#2f6fed"
GOLD = "#d4a017"
RED = "#c44e52"
GREEN = "#2a9d8f"
GRAY = "#7a8699"


def style():
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.facecolor": "white",
            "axes.facecolor": "#fbfcfe",
            "axes.grid": True,
            "grid.alpha": 0.25,
            "grid.linestyle": "--",
        }
    )


def fig_a1():
    metrics = ["RC", "ICC", "DCC", "BI", "SC"]
    series = {
        "adaptive_ace": [99.92, 52.12, 86.85, 99.13, 99.62],
        "sentence_window": [97.57, 54.76, 91.3, 90.65, 88.32],
        "no_split": [100.0, 53.63, 100.0, 100.0, 3.03],
        "fixed_token_512": [100.0, 49.06, 86.65, 99.55, 100.0],
    }
    colors = {
        "adaptive_ace": ACCENT,
        "sentence_window": GOLD,
        "no_split": RED,
        "fixed_token_512": GRAY,
    }
    n = len(metrics)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]
    fig = plt.figure(figsize=(7.2, 6.0))
    ax = fig.add_subplot(111, polar=True)
    for name, vals in series.items():
        v = vals + vals[:1]
        ax.plot(
            angles,
            v,
            color=colors[name],
            lw=2.8 if name == "adaptive_ace" else 1.6,
            label=name,
            marker="o",
            markersize=6 if name == "adaptive_ace" else 4,
        )
        ax.fill(angles, v, color=colors[name], alpha=0.12 if name == "adaptive_ace" else 0.05)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metrics, fontsize=11)
    ax.set_ylim(0, 100)
    ax.set_title(
        "Appendix Fig. A1  CLAIR intrinsic profile\n(adaptive leads Mean; no_split collapses SC)",
        pad=18,
        fontsize=12,
    )
    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.12), fontsize=9, frameon=False)
    fig.tight_layout()
    fig.savefig(FIG / "figA1_clair_radar.png", dpi=200, bbox_inches="tight")
    plt.close()


def fig_a2():
    methods = [
        "adaptive_ace",
        "recursive_text_1100",
        "recursive_text",
        "fixed_token_512",
        "heading_section",
        "no_split",
        "sentence_window",
    ]
    domains = ["technical", "legal", "sustainability"]
    data = {
        "adaptive_ace": [90.65, 89.35, 88.98],
        "recursive_text_1100": [90.58, 89.0, 88.98],
        "recursive_text": [90.54, 89.23, 88.81],
        "fixed_token_512": [89.97, 88.71, 88.31],
        "heading_section": [81.66, 88.71, 88.31],
        "no_split": [77.84, 69.97, 69.44],
        "sentence_window": [61.2, 52.57, 54.17],
    }
    mat = np.array([data[m] for m in methods])
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    im = ax.imshow(mat, cmap=plt.cm.Blues, aspect="auto", vmin=50, vmax=92)
    ax.set_xticks(range(len(domains)))
    ax.set_xticklabels([d.title() for d in domains], fontsize=11)
    ax.set_yticks(range(len(methods)))
    ax.set_yticklabels(methods, fontsize=10)
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            val = mat[i, j]
            ax.text(
                j,
                i,
                f"{val:.1f}",
                ha="center",
                va="center",
                color="white" if val > 80 else "#123",
                fontsize=9,
                fontweight="bold" if i == 0 else "normal",
            )
    ax.add_patch(plt.Rectangle((-0.5, -0.5), len(domains), 1, fill=False, edgecolor=GOLD, lw=2.5))
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Intrinsic Mean")
    ax.set_title(
        "Appendix Fig. A2  ACE kit domain × method heatmap (Stage C)\nadaptive_ace leads every domain",
        fontsize=12,
    )
    ax.grid(False)
    fig.tight_layout()
    fig.savefig(FIG / "figA2_domain_heatmap.png", dpi=200, bbox_inches="tight")
    plt.close()


def fig_a3():
    corpora = ["CLAIR\n(intrinsic)", "FinanceBench\n(intrinsic)", "Open RAG Bench\n(RAG RC)"]
    ranks = {
        "adaptive_ace": [1, 1, 1],
        "fixed_token_512": [2, 3, 1],
        "recursive_text_1100": [5, 2, 4],
        "sentence_window": [6, 6, 5],
    }
    styles = {
        "adaptive_ace": (ACCENT, 3.0, "o", 10),
        "fixed_token_512": (GRAY, 1.6, "s", 7),
        "recursive_text_1100": (GREEN, 1.6, "^", 7),
        "sentence_window": (GOLD, 1.6, "D", 7),
    }
    fig, ax = plt.subplots(figsize=(8.4, 4.6))
    x = np.arange(len(corpora))
    for name, rs in ranks.items():
        c, lw, m, ms = styles[name]
        ax.plot(x, rs, color=c, lw=lw, marker=m, markersize=ms, label=name)
        for xi, yi in zip(x, rs):
            ax.text(
                xi,
                yi - 0.18 if name == "adaptive_ace" else yi + 0.22,
                str(yi),
                ha="center",
                fontsize=9,
                color=c,
                fontweight="bold" if name == "adaptive_ace" else "normal",
            )
    ax.set_xticks(x)
    ax.set_xticklabels(corpora)
    ax.set_ylabel("Rank (1 = best)")
    ax.set_ylim(6.8, 0.4)
    ax.set_title("Appendix Fig. A3  Cross-corpus rank trajectories (ACE-advantage lens)", fontsize=12)
    ax.legend(frameon=False, fontsize=9, loc="lower left")
    ax.axhspan(0.5, 1.5, color=ACCENT, alpha=0.06)
    fig.tight_layout()
    fig.savefig(FIG / "figA3_rank_trajectories.png", dpi=200, bbox_inches="tight")
    plt.close()


def fig_a4():
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.2))
    ax = axes[0]
    methods_k = ["adaptive", "rec_1100", "fixed_512", "heading", "sent_win"]
    ans = [43, 43, 43, 43, 25]
    tot = 43
    rc_k = [100, 100, 100, 100, 70.42]
    x = np.arange(len(methods_k))
    w = 0.38
    ax.bar(x - w / 2, [a / tot * 100 for a in ans], width=w, color=ACCENT, label="Answered %")
    ax.bar(x + w / 2, rc_k, width=w, color=GREEN, label="Mean RAG RC")
    ax.set_xticks(x)
    ax.set_xticklabels(methods_k, rotation=20, ha="right")
    ax.set_ylim(0, 115)
    ax.set_title("ACE kit (43 Q): saturation after rerank")
    ax.legend(fontsize=8, frameon=False)

    ax = axes[1]
    methods_o = ["adaptive", "fixed_512", "rec_1100", "sent_win", "no_split"]
    ans_o = [10, 10, 9, 9, 3]
    tot_o = 12
    rc_o = [90, 90, 83.33, 80, 35.83]
    x = np.arange(len(methods_o))
    colors_o = [ACCENT, GRAY, GREEN, GOLD, RED]
    ax.bar(x, rc_o, color=colors_o, alpha=0.9, label="Mean RAG RC")
    ax.plot(x, [a / tot_o * 100 for a in ans_o], color="#222", marker="D", lw=1.5, label="Answered %")
    ax.set_xticks(x)
    ax.set_xticklabels(methods_o, rotation=20, ha="right")
    ax.set_ylim(0, 115)
    ax.set_title("Open RAG Bench: long-PDF no_split collapse")
    ax.legend(fontsize=8, frameon=False)
    ax.annotate(
        "collapse",
        xy=(4, 35.83),
        xytext=(3.0, 55),
        arrowprops=dict(arrowstyle="->", color=RED),
        color=RED,
        fontsize=9,
    )
    fig.suptitle("Appendix Fig. A4  Answer coverage vs mean RAG completeness", fontsize=12, y=1.02)
    fig.tight_layout()
    fig.savefig(FIG / "figA4_answered_vs_rag.png", dpi=200, bbox_inches="tight")
    plt.close()


def fig_a5():
    fig, ax = plt.subplots(figsize=(8.6, 4.4))
    methods_f = ["adaptive_ace", "rec_1100", "fixed_512", "sent_win", "no_split"]
    mean_f = [91.61, 90.64, 89.82, 88.02, 83.77]
    rag_ac = [88.89, 93.52, 89.07, 76.85, 91.67]
    x = np.arange(len(methods_f))
    w = 0.36
    ax.bar(x - w / 2, mean_f, width=w, color=ACCENT, label="Intrinsic Mean")
    ax.bar(x + w / 2, rag_ac, width=w, color="#e8a54b", label="Live RAG AC")
    ax.set_xticks(x)
    ax.set_xticklabels(methods_f)
    ax.set_ylim(70, 100)
    ax.set_ylabel("Score")
    ax.set_title(
        "Appendix Fig. A5  FinanceBench: intrinsic lead with RAG residual\n"
        "(why Auto stays a proposal under human review)",
        fontsize=12,
    )
    ax.legend(frameon=False, fontsize=9)
    ax.annotate(
        "Mean #1",
        xy=(0, 91.61),
        xytext=(-0.2, 97),
        color=ACCENT,
        fontsize=9,
        arrowprops=dict(arrowstyle="->", color=ACCENT),
    )
    ax.annotate(
        "RAG override lesson",
        xy=(1, 93.52),
        xytext=(1.5, 98),
        color="#a66b00",
        fontsize=9,
        arrowprops=dict(arrowstyle="->", color="#a66b00"),
    )
    fig.tight_layout()
    fig.savefig(FIG / "figA5_financebench_tradeoff.png", dpi=200, bbox_inches="tight")
    plt.close()


def fig_a6():
    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    mets = ["RC", "ICC", "DCC", "BI", "SC", "Mean"]
    adap = [99.92, 52.12, 86.85, 99.13, 99.62, 87.8]
    sent_vals = [97.57, 54.76, 91.3, 90.65, 88.32, 84.52]
    y = np.arange(len(mets))
    ax.hlines(y, sent_vals, adap, color="#cfd8e3", lw=3, zorder=1)
    ax.scatter(sent_vals, y, s=70, color=GOLD, zorder=2, label="sentence_window")
    ax.scatter(adap, y, s=110, color=ACCENT, zorder=3, label="adaptive_ace")
    for yi, a, s in zip(y, adap, sent_vals):
        ax.text(
            max(a, s) + 1.2,
            yi,
            f"{a - s:+.1f}",
            va="center",
            fontsize=8,
            color=ACCENT if a >= s else RED,
        )
    ax.set_yticks(y)
    ax.set_yticklabels(mets)
    ax.set_xlim(45, 110)
    ax.set_xlabel("Score")
    ax.set_title("Appendix Fig. A6  CLAIR metric deltas: adaptive vs sentence_window", fontsize=12)
    ax.legend(frameon=False, loc="lower right")
    ax.axvline(87.8, color=ACCENT, ls=":", alpha=0.5)
    fig.tight_layout()
    fig.savefig(FIG / "figA6_clair_lollipop.png", dpi=200, bbox_inches="tight")
    plt.close()


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    style()
    fig_a1()
    fig_a2()
    fig_a3()
    fig_a4()
    fig_a5()
    fig_a6()
    print("Wrote", sorted(FIG.glob("figA*.png")))


if __name__ == "__main__":
    main()
