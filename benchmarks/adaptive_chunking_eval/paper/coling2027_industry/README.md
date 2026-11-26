# COLING 2027 Industry Track — standalone paper pack

Target venue: **COLING 2027 Industry Track** (Macau, 9–14 May 2027).  
Submission deadline (CFP): **30 Nov 2026 AoE**. Notification: **15 Mar 2027**.

| File | Role |
|------|------|
| [`ACE_COLING2027_Industry_Manuscript.docx`](ACE_COLING2027_Industry_Manuscript.docx) | **Current submission DOCX** (6 figures + expanded tables/refs) |
| [`ACE_COLING2027_Industry_Manuscript（改1）.docx`](ACE_COLING2027_Industry_Manuscript（改1）.docx) | Author-edited baseline (comments preserved) |
| [`ACE_COLING2027_Industry_Manuscript（改2）.docx`](ACE_COLING2027_Industry_Manuscript（改2）.docx) | Prior expansion (figures) |
| [`ACE_COLING2027_Industry_Manuscript（改3）.docx`](ACE_COLING2027_Industry_Manuscript（改3）.docx) | Prior: ≥26 high-impact refs |
| [`ACE_COLING2027_Industry_Manuscript（改4）.docx`](ACE_COLING2027_Industry_Manuscript（改4）.docx) | Current: appendix Figures A1–A6 |
| [`manuscript_submission.md`](manuscript_submission.md) | Markdown source aligned with the DOCX |
| [`paper.md`](paper.md) | Same narrative as manuscript (synced) |
| [`paper.html`](paper.html) | HTML preview |
| [`figures/`](figures/) | Fig 1–6 (body) + Fig A1–A6 (appendix: radar/heatmap/ranks/lollipop) |
| [`REVISION_NOTES_改2.md`](REVISION_NOTES_改2.md) | How 改2 addresses 改1 comments + COLING density notes |
| [`SUBMISSION_NOTES.md`](SUBMISSION_NOTES.md) | Figure/result filtering + packaging checklist |
| [`COMPARISON_COLING2025_INDUSTRY.md`](COMPARISON_COLING2025_INDUSTRY.md) | Mapping vs COLING 2025 Industry CFP / chairs overview + 2027 changes |
| [`build_docx.py`](build_docx.py) | Regenerate the DOCX |

The repository technical report remains at [`../paper.md`](../paper.md). This folder is a **separate submission-oriented rewrite**, not a replacement.

## Positioning

- **Category:** Emerging / enabling infrastructure (governed per-document chunking), with evaluation + negative-result lessons  
- **Themes (2027 CFP):** Data & Model Governance; Evaluation & QA; Human-in-the-loop; Negative Results & Trade-Offs; domain corpora (legal/finance/arxiv)  
- **Review mode:** **Double-blind** (changed from COLING 2025 single-blind)
- **Primary live stack in draft:** `Qwen3-Embedding-8B` + Cohere `rerank-v3.5` + `rag_microloop` + `gpt-4o`
- **Lead results (ACE-advantage filter):** kit 100/100 after rerank; CLAIR full intrinsic #1 (87.8); Open RAG Bench RAG tied #1 vs `no_split` collapse on long PDFs

## Next steps before OpenReview

1. Convert `paper.md` to official COLING 2027 LaTeX style (≤6 content pages).  
2. Anonymize any remaining identifiable links/artifacts.  
3. Submit via [OpenReview Industry Track](https://openreview.net/group?id=coling-iccl.org/COLING/2027/Industry_Track).  
4. Full CFP: https://2027.coling-iccl.org/calls/industry_track/
