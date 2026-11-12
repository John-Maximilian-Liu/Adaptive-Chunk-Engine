# ACE × COLING Industry Track：对照 COLING 2025 审稿期望与 2027 CFP

本文档说明：**为什么把 ACE 单独拆成 COLING 2027 Industry Track 投稿版本**，以及它与 **COLING 2025 Industry Track CFP / 录用前言（paper review 视角）** 的对齐与差距。  
主稿见同目录 [`paper.md`](paper.md)。

---

## 1. 投稿目标速览

| 项 | COLING 2025 Industry | COLING 2027 Industry（本稿目标） |
|----|----------------------|----------------------------------|
| 会议 | Abu Dhabi, Jan 2025 | Macau, May 9–14, 2027 |
| 篇幅 | **6 页**正文（refs/ethics/appendix 不计） | **6 页**正文（同上） |
| 审稿 | **Single-blind** | **Double-blind**（2027 起改为双盲） |
| 录用规模（2025） | 166 投稿 / 69 录用 ≈ **41.6%** | 未公布 |
| 截止（2027） | — | **2026-11-30 AoE**；通知 2027-03-15 |
| 提交 | SoftConf | OpenReview Industry Track |
| 强调 | 实操部署、非研究 novelty | 同；三大主题：基础设施/治理、部署评估、案例与资源 |

来源：

- [COLING 2025 Industry Track CFP](https://coling2025.org/calls/industry_track/)
- [COLING 2025 Industry Track proceedings / chairs overview](https://aclanthology.org/2025.coling-industry.pdf)
- [COLING 2027 Industry Track CFP（SIGDIAL 转发）](https://list.sigdial.org/empathy/thread/QPV4NRC7W7BSUQQDLIOAPZZAL4UGRQVV)
- OpenReview: `coling-iccl.org/COLING/2027/Industry_Track`

---

## 2. COLING 2025「审稿视角」在看什么

CFP 明确：**重点不是 research novelty，而是复杂真实环境中的落地**；用户应超出 NLP 研究社区。三类投稿：

| 类别 | 审稿期望 | ACE 对照 |
|------|----------|----------|
| **Deployed** | 真实问题、业务价值、方案决策、部署困难、经验教训 | 部分满足：有控制面与评测闭环，但本文**不以大规模生产 telemetry / 上线 ROI** 为主证据 → **不宜硬报 Deployed** |
| **Emerging** | 面向真实问题的系统；**可不已上线**；含 **enabling infrastructure** | **最贴合**：Strategy Registry + 审计清单 + 双协议评测 kit |
| **Discovery** | 从实践数据得到可行动洞察 | 部分满足：intrinsic ≠ RAG 的负结果/权衡属于 Discovery 味道，但主叙事仍是系统+评测 |

**Evaluation Criteria（2025）**：originality / technical excellence / significance / readability；实证须方法透明、可复现（数据可保密）。

2025 chairs overview 还显示录用主题高度 LLM 化（应用、评测、领域适配、对话、多模态等），RAG/检索类是常见工业议题；同季相关工业工作如 ACL 2025 Industry 的 AutoChunker 也说明 **chunking + RAG 评测** 是审稿人熟悉的问题空间。

---

## 3. COLING 2027 CFP 主题映射（相对 2025 的演进）

2027 把兴趣点收成三大主题（仍保留实操优先）：

| 2027 主题 | ACE 稿中的落点 | 强度 |
|-----------|----------------|------|
| **System Design, Infrastructure & Operational Efficiency** — Data & Model Governance；Enabling Infrastructure；offline vs online | ReproductionManifest、CanonicalChunk、Offline CI vs Live neural | 强 |
| **Deployed Methods & System Evaluation** — Evaluation & QA；Human-in-the-loop；**Negative Results & Trade-Offs** | 双协议评测；人工优化门；ACE-kit live 负结果 | 强 |
| **Novel Applications, Case Studies & Resources** — finance/legal；datasets；best practices | CLAIR / FinanceBench / Open RAG Bench；§6 Practitioner Lessons | 中–强 |

**相对 2025 的关键变化（投稿时必须遵守）：**

1. **双盲**：review PDF 不得含作者名、机构、可识别仓库/产品截图；匿名仓库链接。  
2. 主题措辞更强调 **governance、lifecycle、negative results** —— 正好强化 ACE「治理门 + 负结果」叙事，而不是只报刷榜第一。

---

## 4. 本稿 vs 仓库内原技术报告（`paper/paper.md`）

| 维度 | 原技术报告 | COLING 2027 Industry 独立稿 |
|------|------------|-----------------------------|
| 受众 | 仓库读者 / 研究备忘 | Industry Track 审稿人 |
| 篇幅姿态 | 偏完整实验手册 | **压到 ~6 页叙事** |
| 叙事中心 | 方法 + 全表结果 | **问题→控制面→评测协议→教训/负结果** |
| 匿名 | 署名技术报告 | **双盲匿名** |
| 工业要素 | 有但偏说明 | 显式对齐 CFP 主题与 Emerging |
| 表格 | 较全 | 摘要表 + appendix 指针 |
| 对比公开基线 | 有 | 保留，但强调 **rank-order** |

独立稿**不替换**原报告；原报告继续作为完整结果与复现入口。

---

## 5. 对照「会中招 / 会加分」清单（按 2025 CFP + 2027 主题自检）

| 审稿关注点 | 本稿现状 | 风险与补强建议 |
|------------|----------|----------------|
| 真实用户超出 NLP lab | 企业 RAG 控制面定位清晰 | 若有可公开的内部试点/用户角色，可在 camera-ready 补一句 |
| Enabling infrastructure | Strategy Registry + Manifest | 加一张系统框图（LaTeX 定稿时） |
| 方法可复现 | `make eval*` 命令 + 公开基准适配器 | 双盲期用匿名附件/匿名 repo |
| 实证透明 | 双协议、answered 分数、成本 | 写明 smoke vs full，避免被批「夸大」 |
| 负结果 / 权衡 | ACE-kit live、FinanceBench 覆盖 | **保留并前置**——这是 Industry 加分项 |
| 业务价值 / opportunity size | 偏弱（无 Deployed 案例） | 定位 Emerging；勿声称大规模已部署 ROI |
| 与 AutoChunker 等区分 | ACE = **per-doc 策略选择 + 治理**，非新 chunker 算法 | 引言明确「productize selection + audit」，避免被当成又一 chunker 变体 |
| 双盲合规 | 稿内已 Anonymous | 定稿转 ACL/COLING style；去掉 GitHub 实名链接 |

---

## 6. 与 2025 录用前言（chairs overview）的「主题契合度」判断

COLING 2025 Industry 录用分布强调：LLM 应用与评测、NLP 应用（含 QA）、对话、多模态、知识管理等。ACE 落在：

- **LLM applications / evaluation**（gpt-4o judge + embedding RAG）
- **QA / retrieval pipelines**（FinanceBench、Open RAG Bench）
- **domain adaptation 周边**（legal/finance/arxiv 文档形态差异）

契合度：**高（评测与基础设施类）**；若审稿人用 Deployed 标准硬套，会嫌缺线上 A/B——应用 §5–6 的负结果与治理叙事回应「为何不报 Deployed」。

---

## 7. 投稿行动清单

1. 用 COLING 2027 official style（会议站模板）把 `paper.md` 转成 **≤6 页** PDF。  
2. 双盲检查：作者、机构、可识别 URL、截图。  
3. OpenReview 提交：<https://openreview.net/group?id=coling-iccl.org/COLING/2027/Industry_Track>  
4. 类别/主题标签（若表单要求）：勾选 **Emerging / Enabling infrastructure** + **Evaluation & Negative Results**。  
5. 可选补充材料：匿名 `results/` 表；**正文必须自洽**（审稿人可不看附录）。  
6. 截止：**2026-11-30 AoE**。

---

## 8. 一句话结论

相对 COLING 2025 Industry Track 的审稿逻辑，ACE 独立稿应打 **「Emerging 基础设施 + 部署评测/负结果」**，而不是刷 SOTA 的 research novelty 稿；2027 的双盲与 governance/negative-results 主题进一步支持当前叙事。与仓库原技术报告相比，本目录版本是**专为 Industry Track 裁剪与匿名化的投稿分支**。
