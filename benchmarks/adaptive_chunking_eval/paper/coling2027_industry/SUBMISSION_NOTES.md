# COLING 2027 Industry — manuscript packaging notes

## Do we need more figures?

对照 `COMPARISON_COLING2025_INDUSTRY.md` 与 COLING 2025 Industry CFP 惯例：

| 建议 | 本稿处理 |
|------|----------|
| **系统/流程框图（强烈建议）** | ✅ 已加 **Figure 1**（selection → micro-loop → dense+rerank → human gate） |
| **结果可视化（建议）** | ✅ 已加 **Figure 2**（kit 64→100；CLAIR intrinsic；ORB vs no_split） |
| 产品截图 / 可识别品牌图 | ❌ 双盲期不加 |
| 大规模部署 telemetry 图 | ❌ Emerging 定位，不硬报 Deployed ROI |

结论：**需要补图，且以 1 张流程 + 1 张优势结果图足够**；不必堆无关 dashboard。

## 结果筛选（保留有利 / 去掉无关）

**保留并前置：**
- Kit +rerank：**64→100** RAG（核心方法相关：生产检索对齐）
- CLAIR full：intrinsic Mean **#1 (87.8)**；RAG vs sentence_window
- Open RAG Bench：adaptive **90/82.5** vs **no_split 35.8/26.7**（长文档核心对比）
- FinanceBench：intrinsic **#1**；RAG 略逊仅作 **override 教训一句**

**弱化/移出正文主导叙事：**
- 短文 `no_split` “刷高”不当成生产赢家
- Offline smoke 全表（CI 车道，正文不展开）
- 可识别仓库路径 / 实名 URL（双盲）
- 与核心选择+治理无关的冗长附录方法行（附录只留关键 intrinsic 子集）

## 提交文件

| 文件 | 用途 |
|------|------|
| [`ACE_COLING2027_Industry_Manuscript.docx`](ACE_COLING2027_Industry_Manuscript.docx) | **可下载编辑的 DOCX 稿** |
| [`manuscript_submission.md`](manuscript_submission.md) | 与 DOCX 对齐的 Markdown 源 |
| [`figures/fig1_flow.png`](figures/fig1_flow.png) | Figure 1 |
| [`figures/fig2_results.png`](figures/fig2_results.png) | Figure 2 |
| [`build_docx.py`](build_docx.py) | 重生 DOCX |

## 正式投稿前仍建议

1. 用会议官方 COLING 2027 style（LaTeX/Word 模板）重排为 **≤6 页 PDF**（Industry 通常要求 PDF）。  
2. DOCX 便于内部审阅与改图；OpenReview 最终上传以会议要求为准。  
3. 双盲再扫一遍：作者、机构、可识别 URL、截图。  
4. 截止：**2026-11-30 AoE**。
