# 验收评分准则（Acceptance Rubric）

## 评分规则

- Hard gates: every `Essential` must be `PASS`; every relevant `Pitfall` must
  be `PASS` as "not triggered".
- 加权分只作参考，不能覆盖硬门禁失败。
- 状态值固定为：`PASS | FAIL | BLOCKED | N/A`。
- Layer weights for actual workflow scoring / 实际流程评分层级权重：
  - L1 功能与需求闭合: 0.30
  - L2 验证与证据: 0.25
  - L3 工作流阶段合规: 0.25
  - L4 交付与仓库状态: 0.10
  - L5 上下文与自动化治理: 0.10
- `workflow_score`、`ai_acceptance_score`、`ui_ux_score` 必须引用具体验证证据，
  例如测试、构建、API/E2E 计划、CDP 截图、日志、运行时事实、
  `.plugin` 包或验收记录。
- 最终 Rubric 评分只在 strict/release、rubric-score 或 complete-branch
  被显式选择时输出；plan / implement / acceptance 阶段只维护准则定义、
  证据入口和 hard gates。
- strict/release 总分低于 90、任一 hard gate 失败、任一维度低于 80 且无
  blocker 或 owner/user accepted gap 证据时，禁止 complete-branch。

## Root-Fix Decision Gate Rules

For bugfix work, missing Root-Fix Decision Gate is an Essential failure. The
rubric must verify:

- Final fix type is explicit: root fix / mitigation / containment /
  compatibility fallback.
- A fix may be called root fix only when it eliminates the failure mechanism and
  has no known same-mechanism scale-growth failure path.
- Cleanup, release, reset, retry, fallback, rate limiting, quantity limiting,
  or impact narrowing must be checked as likely mitigation unless the evidence
  proves the failure mechanism is eliminated.
- If the selected fix is mitigation, containment, or compatibility fallback,
  residual risk and follow-up root-fix route must be recorded.
- "Current project is enough" is not a root-fix reason unless future
  compatibility cost, scale boundary, and root-fix upgrade trigger are recorded.

## 评分项

| ID | 层级 | 重要性 | 权重 | 准则 | 所需证据 | 通过条件 | 来源 | 状态 |
|----|-------|------------|--------|-----------|-------------------|----------------|--------|--------|
| R-001 | L1 功能与需求闭合 | Essential | 1.0 |  |  |  |  |  |
| R-002 | L2 验证与证据 | Essential | 1.0 |  |  |  |  |  |
| R-003 | L3 工作流阶段合规 | Essential | 1.0 |  |  |  |  |  |
| R-004 | L4 交付与仓库状态 | Important | 0.7 |  |  |  |  |  |
| R-005 | L5 上下文与自动化治理 | Important | 0.7 |  |  |  |  |  |
| R-006 | L1 功能与需求闭合 | Essential | 1.0 | Bugfix Root-Fix Decision Gate 完成且最终 fix type 未被误标 | plan.md/workpack.md Root-Fix Decision Gate, implementation-summary.md | 非 root fix 明确标记残留风险和后续 root-fix 路线；root fix 消除失败机制且无同机制规模失败路径 | Root-Fix Decision Gate |  |
| P-001 | Pitfall | Pitfall | 0.9 |  |  | Not triggered |  |  |
| P-002 | Pitfall | Pitfall | 0.9 | Mitigation / containment / compatibility fallback 被描述成 root fix | Root-Fix Decision Gate, implementation-summary.md, validation.md | Not triggered | Root-Fix Decision Gate |  |

## 评审摘要

- Essential 是否全部通过:
- Pitfall 是否均未触发:
- 加权分:
- 阻塞项:
- 下一步:

## 实际流程评分审计（Actual Workflow Rubric Audit）

> Only fill when strict/release scoring, `speckit-rubric-score`, or
> `speckit-complete-branch` was explicitly selected. If a selected self-check
> amended the commit, score the final amended state without running another
> self-check.

| 维度 | 权重 | 评分 0-100 | 证据 | 主要风险 / Pitfall |
|-----------|--------|-------------|----------|---------------------|
| L1 功能与需求闭合 | 0.30 |  |  |  |
| L2 验证与证据 | 0.25 |  |  |  |
| L3 工作流阶段合规 | 0.25 |  |  |  |
| L4 交付与仓库状态 | 0.10 |  |  |  |
| L5 上下文与自动化治理 | 0.10 |  |  |  |
| Hard gates | hard gate | PASS / FAIL / BLOCKED |  | AI Self-Acceptance, selected API/E2E, `.plugin`, CDP/runtime, optional commit message, optional self-check |

- Overall Weighted Score / 总加权分:
- AI acceptance decision / AI 验收结论:
- Human acceptance readiness / 人工验收准备状态:
- Complete-branch allowed / 是否允许 complete-branch:
- 扣分原因:
- Accepted gap 证据:
