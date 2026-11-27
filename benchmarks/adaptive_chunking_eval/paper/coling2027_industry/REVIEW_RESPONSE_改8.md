# COLING 2027 Industry — Review response design (改8)

审稿核心缺口：选型与评分题复用；摘要“100”易被误读；图表/指标定义不一致；治理收益未量化。改8用 **Stage E held-out 配对实验** 作为正文主证据，并把贡献收束到“谁能审查/修改切分决策、以及何时值得做”。

## Stage E protocol（主实验）

同一批可分诊断/隐藏题的文档（CLAIR 33；FinanceBench ≥2 QA → 10/18；ORB 4）：

| Condition | Lock rule (diagnostic only) |
|-----------|-----------------------------|
| ① `strong_fixed` | Leave-one-out：对其余文档 diagnostic evidence-Cov 均值最高的生产切分器 |
| ② `intrinsic` | Stage-D 候选表 $\arg\max \mu$ |
| ③ `microloop` | Stage-D top-3 shortlist + $\alpha\mu+(1-\alpha)\rho_{\mathrm{diag}}$ |
| ④ `human_review` | 若 microloop diagnostic Cov < fixed − 0.02，则在 {fixed}∪shortlist 上取 diagnostic Cov 最大者；每条告警计 4 min（模拟操作者预算） |

共享：`Qwen3-Embedding-8B`、Cohere `rerank-v3.5`、top-$K_c{=}20$→$K{=}5$、相同上下文预算。先锁索引，再开隐藏题。

**主指标（非答题准确率）：** 隐藏题 evidence-term recall；退化率 = hidden Cov 相对 strong_fixed 下降 ≥0.05 的文档比例；配对差值（pp）+ bootstrap CI；复核告警数/覆盖例数/工时。

Runner：`benchmarks/adaptive_chunking_eval/run_heldout_paired.py`  
Artifacts：`results/public_benchmarks/heldout_paired_stage_e/{summary,per_document,tables,walkthroughs}.json`

## Manuscript structure shifts (改8)

1. **Abstract**：改写 kit 结论为 “answered 26/43→43/43；Stage C 八法中七法同达上限”；写明 Stage E held-out；公开评测边界（金标文档内检索、CLAIR 题由标题构造、ORB 4 篇）。
2. **§4.1**：RC=References Completeness，SC=Size Compliance；式 (1) 对缺失项取可用子集均值。
3. **§5**：新增 Stage E 协议表；更正 Mean/RAG 分母表述（文档等权、含未回答题）。
4. **§6**：主表 = Stage E 四条件；穿插 **AMD_2022_10K** 上传→诊断告警→人工改锁→隐藏复测；Stage D 排行榜压缩；Fig.5 从 Stage-D JSON 重生（FB：`rec_1100` 5/18，`fixed_512` 6/18）。
5. **附录**：原优势雷达/热力等迁入；保留 Stage D 全表供复现。

## What we are *not* claiming in 改8

- Stage E 主表不是 LLM-judge 答案正确率（若保留该用语需另做冻结生成器盲评）。
- 人工复核是与产品审批门一致的**模拟策略**，不是真人用户研究；工时按告警定额计入。
