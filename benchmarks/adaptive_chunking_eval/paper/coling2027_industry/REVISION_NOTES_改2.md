# 改2 revision notes (respecting 改1 edits + comments)

## Author comments in `ACE_COLING2027_Industry_Manuscript（改1）.docx`

| Comment | Response in 改2 |
|---------|-----------------|
| “Still” too absolute | Kept 改1 wording: **often rely on** |
| “control plane” too strong for RAG | Kept 改1: **auditable framework for per-document chunking selection**; conclusion aligned |
| Clarify 100/100 (counts vs rates) | Explicitly **mean scores on 0–100** + **answered** fractions (e.g., 43/43) in abstract, protocol, tables, lessons |
| Figure 1 logic mismatch | Kept author flowchart (`image2`) + rewritten §4 prose/caption; regenerated result figs only |
| Conclusion should match abstract | Conclusion starts with **ACE extends… auditable framework…** |
| Citation format (APA?) | Switched to **ACL author–year** body cites + ACL-style bibliography (not APA) |

## Density vs COLING 2025 Industry samples

| Paper | Pages | Figs (approx) | Notes |
|-------|------:|---------------|-------|
| 2025.coling-industry.43 | 6 | 2 | Closest page budget; still has multi-table body |
| 2025.coling-industry.33 | 11 | 9 | Figure-heavy systems paper |
| 2025.coling-industry.4 | 19 | 5 | Long Industry + taxonomy |
| **This draft (改2)** | DOCX long-form → convert to ≤6p PDF | **6** | Added Related Work, selection mix, cross-corpus figs, FinanceBench RAG table, refs |

## New experimental content (from Stage A–D results)

- **Fig 3** cross-corpus RAG (adaptive vs contrast)
- **Fig 4** kit stage A→C progression
- **Fig 5** per-doc locked strategy mix (CLAIR / FinanceBench)
- **Fig 6** intrinsic Mean across corpora
- FinanceBench live RAG table in body
- Expanded references (Lewis; Gao survey; Teixeira de Lima COLING’25; AutoChunker; Zheng LLM-as-judge; FinanceBench; Open RAG Bench)

## Files

- `ACE_COLING2027_Industry_Manuscript.docx` / `…（改2）.docx`
- Source: `manuscript_submission.md`
- Figures: `figures/fig1_flow.png` … `fig6_intrinsic_cross.png`
