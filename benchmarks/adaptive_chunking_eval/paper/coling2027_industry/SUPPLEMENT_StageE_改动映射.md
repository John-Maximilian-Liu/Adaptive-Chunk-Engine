# Stage E 实验结果补充文档（不改 改8 正文）

> **用途：** 审稿意见要求的 held-out 配对实验与图表/定义勘误，**单独成文**。  
> **改8：** 本文件不修改 `manuscript_submission.md` / `ACE_COLING2027_Industry_Manuscript（改8）.docx`。  
> **锚本：** 章节锚定以审稿所据 **改5** 结构为准（与 改7 正文分节一致）；括号内注明建议插入位置。

---

## 0. 放置总表（先看这里）

| ID | 补充内容 | 建议放入原文位置 | 操作建议 |
|----|----------|------------------|----------|
| S1 | Abstract：kit「26/43→43/43」+ 非答题准确率 + 评测边界 | **Abstract** 末段成绩句 | 替换「mean 100/100」易被误读的写法；不改贡献句主干 |
| S2 | 贡献收束为「谁审查/何时值得」+ Stage E | **§1 Contributions** 列表 | 增 1 条 held-out；弱化「多榜第一」措辞 |
| S3 | RC/SC 正名；Mean 跳过缺失项 | **§4.1** 指标列举 + 式 (1) | 替换错误释义；改式 (1) |
| S4 | Stage D 有 14/55 篇选了较低内在分 | **§4.2** 或 **§6.5** | 新增一句 + 小表（可附录） |
| S5 | 裁判=证据支持；分母=文档等权含未答 | **§4.3** 末 / **§5 Score reporting** | 替换「仅已回答题均值」的错误表述 |
| S6 | Stage E 协议（四条件、诊断/隐藏） | **§5 Evaluation Protocol** 新小节 | 新增「Live Stage E」行与协议段 |
| S7 | **主表：四条件隐藏题 evidence recall** | **§6 Results** 建议作新 **§6.0/6.1** | 正文主证据；原排行榜可下沉附录 |
| S8 | AMD 2022 10-K 走读 | **§6** 紧接主表 | 新小节；串上传→告警→改锁→隐藏复测 |
| S9 | Fig.5 锁策略计数勘误 | **§6.5 + Figure 5** | 用 Stage-D JSON 重画；改正文「8/18」 |
| S10 | Kit 饱和：7/8 方法同达上限 | **§6.1** kit 段 | 补充一句，避免暗示仅 ACE 达 100 |
| S11 | 人工复核工时/拦住退化 | **§7 Lessons** + **Limitations** | 工时为模拟策略；非真人研究 |
| S12 | 公开评测边界 | **Limitations**（摘要可见一句即可） | CLAIR 题构造、FB 证据页、ORB 4 篇、FB held-out 10/18 |

---

## 1. 协议说明（对应原文 §5）

**【放置：§5 Evaluation Protocol → 新增 “Live Stage E (primary generalization)”】**

对同一批文档，按**证据段落**将 QA 分为 diagnostic / hidden。四种条件**只看诊断材料**锁定切分器，再在**同一** dense top-$K_c{=}20$ → Cohere `rerank-v3.5` top-$K{=}5$ 栈上评隐藏题：

| 条件 | 锁定规则 |
|------|----------|
| ① `strong_fixed` | Leave-one-out：其余文档 diagnostic evidence-Cov 均值最高的生产切分器 |
| ② `intrinsic` | Stage-D 候选表 $\arg\max\mu$ |
| ③ `microloop` | Stage-D top-3 + $\alpha\mu+(1-\alpha)\rho_{\mathrm{diag}}$（$\alpha{=}0.55$） |
| ④ `human_review` | 若 microloop 诊断 Cov $<$ fixed $-0.02$，在 $\{\mathrm{fixed}\}\cup\mathrm{shortlist}$ 取诊断 Cov 最大；每条告警计 **4 min**（模拟操作者） |

**主指标：** 隐藏题 evidence-term recall（**不是**答案正确率）。  
**退化：** 相对 strong_fixed，hidden Cov 下降 $\ge 0.05$。  
**资格：** CLAIR 33；FinanceBench **10/18**（需 ≥2 QA）；Open RAG Bench 4。合计目标约 47 篇。

**复现：** `benchmarks/adaptive_chunking_eval/run_heldout_paired.py`  
**产物：** `results/public_benchmarks/heldout_paired_stage_e/{summary,per_document,tables,walkthroughs}.*`

> 数值区：`[[E_*]]` 由 Stage E 跑完后脚本写入**本补充文档**，不写回改8。

---

## 2. 主结果表（对应原文 §6 主证据）

**【放置：建议新开 §6.0 / §6.1 “Held-out paired comparison”；原 §6.1–6.4 排行榜可迁附录】**

### Table S1 — Overall（隐藏题）

| Condition | Docs | Mean hidden evidence recall | Δ vs fixed (pp) | Degraded % | Review overrides | Review min/doc |
|-----------|-----:|----------------------------:|----------------:|-----------:|-----------------:|---------------:|
| ① strong_fixed | [[E_N]] | [[E_FIXED]] | 0.0 | — | — | 0.0 |
| ② intrinsic | [[E_N]] | [[E_INTR]] | [[E_INTR_D]] | [[E_INTR_DEG]] | — | 0.0 |
| ③ microloop | [[E_N]] | [[E_MICRO]] | [[E_MICRO_D]] | [[E_MICRO_DEG]] | — | 0.0 |
| ④ human_review | [[E_N]] | [[E_HUM]] | [[E_HUM_D]] | [[E_HUM_DEG]] | [[E_OVERRIDES]] | [[E_MIN_DOC]] |

[[E_NARRATIVE]]

### Table S2 — Per corpus（摘要）

| Corpus | strong_fixed | n | notes |
|--------|--------------|--:|-------|
| CLAIR | [[E_CLAIR_FIXED]] | [[E_CLAIR_N]] | |
| FinanceBench | [[E_FB_FIXED]] | [[E_FB_N]] | Stage-D 18 篇中仅 ≥2 QA 可 held-out |
| Open RAG Bench | [[E_ORB_FIXED]] | [[E_ORB_N]] | 长 PDF |

（分条件明细见跑完后的 `tables.md`。）

**图：** `figures/fig_stage_e_heldout.png`、`figures/fig_stage_e_paired_delta.png`（跑完生成）  
**【放置：§6 主图；原文 Fig.2–4 优势重复图可下沉附录】**

---

## 3. 财报走读 AMD_2022_10K（对应原文 §6 叙事）

**【放置：§6 新小节 “Walkthrough — AMD 2022 10-K”；串产品主流程】**

Stage D 事实（已有，可先写入正文而不等 Stage E）：

- 内在最高：`sentence_window` Mean **86.41**
- 锁定：`recursive_text` Mean **82.37**（较低内在分）
- 诊断 micro：选中 **99.65** vs 内在最优策略 **82.44** → 典型反馈改锁

### Table S3 — Stage E locks on AMD_2022_10K

| Condition | Locked strategy | Hidden evidence recall |
|-----------|-----------------|-----------------------:|
| ① strong_fixed | [[W_FIXED]] | [[W_FIXED_H]] |
| ② intrinsic | [[W_INTR]] | [[W_INTR_H]] |
| ③ microloop | [[W_MICRO]] | [[W_MICRO_H]] |
| ④ human_review | [[W_HUM]] | [[W_HUM_H]] |

[[W_NARRATIVE]]

---

## 4. 定义与表述勘误（对应 §4 / Abstract / §5）

### 4.1 指标正名 — 【放置：§4.1】

| 符号 | 原文（改5）易错写法 | 应改为（与实现/`intrinsic_metrics.py` 一致） |
|------|---------------------|-----------------------------------------------|
| RC | retrieval/coverage-oriented completeness | **References Completeness** |
| ICC | （可保留） | Intrachunk Cohesion |
| DCC | （可保留） | Document Contextual Coherence |
| BI | （可保留） | Block Integrity |
| SC | structural coverage | **Size Compliance** |

式 (1)：应对缺失项取**可用子集**均值（代码 `IntrinsicScore.mean`），而非固定除以 5。

### 4.2 裁判与分母 — 【放置：§4.3 + §5 Score reporting】

- 裁判输入：问题 + 金标 + 检索片段；**无系统生成答案** → 勿称「答案准确率」。
- 语料 RAG 均值：先对每篇**全部题**聚合，再文档等权（不是「只对已回答题」）。
- Kit 无重排基线：mean **64.17 / 64.58**，answered **26/43**；加重排后 **43/43**，且 Stage C **8 法中 7 法**同达 100/100（`sentence_window` 除外）。

**【放置：Abstract 成绩句 + §6.1】** → 见 S1 / S10。

### 4.3 Micro-loop 改锁统计 — 【放置：§4.2 或 §6.5】

| 语料 | 文档数 | 选了严格较低内在分 | 达到/并列内在最高 |
|------|-------:|-------------------:|------------------:|
| CLAIR | 33 | 8 | 25 |
| FinanceBench | 18 | 3 | 15 |
| Open RAG Bench | 4 | 3 | 1 |
| **合计** | **55** | **14** | **41** |

例（审稿已举，可进正文或脚注）：《欧洲人权公约》— `sentence_window` 内在 85.77 vs `fixed_token_512` 84.16；诊断 Cov 73.56% vs 100% → 锁后者。

---

## 5. Figure 5 计数勘误（对应 §6.5）

**【放置：§6.5 正文数字 + 重画 figures/fig5_selection_mix.png】**

来源：`openrouter_full_stage_d/*.json` 中 `method==adaptive_ace` 的 `selected`。

| Corpus | 锁策略计数（正确） |
|--------|-------------------|
| CLAIR (n=33) | fixed_512 **17**, fixed_256 7, rec_1100 4, rec 2, sent_win 2, heading 1 |
| FinanceBench (n=18) | fixed_512 **6**, rec **5**, rec_1100 **5**, sent_win 1, fixed_256 1 |
| Open RAG Bench (n=4) | fixed_512 1, rec 1, rec_1100 1, heading 1 |

**改正：** 原文「FinanceBench locks … recursive_text_1100 (8/18)」→ 应为 **5/18**（rec_1100），fixed_512 为 **6/18**。

---

## 6. 建议写入 Abstract 的替换句（对应 Abstract）

**【放置：Abstract 后半成绩/边界句；勿再暗示答题准确率】**

> Under a production-like stack, aligning evaluation with rerank raises the controlled kit from **26/43** to **43/43** questions meeting the answerable-evidence criterion (judge scores 64.2/64.6→100/100; **7 of 8** Stage-C methods saturate). Because Stage-D selection and scoring reused the same probes, we add **Stage E**: diagnostic vs held-out questions and four locks (strong fixed / intrinsic / +microloop / +human review), reporting **hidden evidence-term recall**, degradation rate, and review minutes—not answer accuracy. Public retrieval is gold-document-only; CLAIR items are title-constructed; FinanceBench uses preselected evidence pages; Open RAG Bench uses 4 PDFs.

---

## 7. Limitations / Lessons 增补

**【放置：§7 增一条；Limitations 扩写】**

- 人工复核为与产品审批门一致的**模拟策略**（告警定额 4 min），非 timed 用户研究。  
- Stage E 主指标为 evidence-term recall；若保留「答案正确性」需另做冻结生成器盲评。  
- FinanceBench held-out 仅 **10/18** 篇有 ≥2 QA。

---

## 8. 与改8 的关系

| 文件 | 状态 |
|------|------|
| `ACE_COLING2027_Industry_Manuscript（改8）.docx` / `manuscript_submission.md` | **不改**（本补充不回填占位符） |
| 本文件 `SUPPLEMENT_StageE_改动映射.md` | Stage E 结果 + 插入位置索引 |
| `REVIEW_RESPONSE_改8.md` | 设计备忘（可保留） |
| `fill_supplement_stage_e.py` | 只填充**本补充文档**中的 `[[…]]` |

作者可按 §0 总表手工把 S1–S12 粘进改5/改7 结构的下一版，而不必采用改8 已改写的正文骨架。

---

## 9. 跑数状态

- Runner：进行中 / 完成后将更新下方时间戳与 Table S1–S3。  
- 最近检查：见 git 提交说明与 `heldout_paired_stage_e/summary.json`。  
- 填充命令（结果齐后）：

```bash
python3 benchmarks/adaptive_chunking_eval/paper/coling2027_industry/fill_supplement_stage_e.py
python3 benchmarks/adaptive_chunking_eval/paper/coling2027_industry/generate_fig_stage_e.py
```
