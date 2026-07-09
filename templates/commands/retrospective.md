---
description: Record an opt-in Spec Kit workflow retrospective without auto-promoting lessons.
scripts:
  ps: scripts/powershell/check-prerequisites.ps1 -Json -Stage retrospective -IncludeTasks
  observer_packet_ps: scripts/powershell/collect-workflow-observer-packet.ps1 -Json -FeatureDir <feature-dir>
---

## User Input

```text
$ARGUMENTS
```

## Context Contract

Default context is `AGENTS.md`, `.specify/workspace.yml`, `.specify/memory/repository-map.md`, `.specify/feature.json` when present, and `ai/workflows/task-routing.md`.
Load `ai/knowledge/*`, `ai/tools/*`, `ai/templates/*`, old `specs/*`, or design-history docs only when this command explicitly needs them.
Scripts provide `facts`, `blockers`, `unknowns`, and `hints`; LLM owns semantic routing, root-cause judgment, validation sufficiency, and tradeoff decisions.
Keep this command stage-specific. Do not duplicate long-term governance prose here.

## Stage Continuation Rule

Apply the central Stage Continuation Contract from `ai/workflows/task-routing.md`; if this stage cannot execute the next required stage, report `blockers` and `next_required_human_action`.

## Purpose

When explicitly selected after final user acceptance / 用户验收通过, create a lightweight
durable record of the current Spec Kit workflow. This 留痕 stage is opt-in
process governance; it is not required for normal delivery closure or
`speckit.commit` unless strict governance was explicitly selected.
The default output is concise traceability: 关键用户输入, AI 输出与动作链, 验证证据,
最终状态, and meaningful errors when present. Expand into detailed error/rework
analysis only when the run had repeated failure, a new pitfall, a new rule, a
new automation opportunity, a tool/runtime evidence issue, or a user-approved
lesson candidate.

This stage writes feature-local retrospective artifacts only. 不自动修改 spec-kit,
memory, team governance, product code, git history, branch state, remotes, or
promote lessons or knowledge into long-term policy.

## Language Rules

- `workflow-record.md`, `improvement-candidates.md`, user-facing summaries, and
  review prompts use Chinese-first style.
- Preserve technical identifiers in their original form: paths, commands,
  commit hashes, branch names, repository names, APIs, fields, and test names.
- Separate facts from inferences. Mark inferred root causes or process lessons
  as inference unless directly evidenced.

## Execution Steps

1. Run the prerequisite script and parse `FEATURE_DIR` and `AVAILABLE_DOCS`.
2. Load available feature artifacts: `intake.md`, `workpack.md`, `spec.md`,
   `plan.md`, `tasks.md`, `progress.md`, `review.md`, `lessons.md`, `validation.md`,
   `implementation-summary.md`, `evidence.md`, `fact-pack.md`, `acceptance.md`, `acceptance-checklist.md`,
   `checklists/`, and screenshot indexes referenced by selected gates when
   present.
3. Confirm final acceptance has explicit evidence.
   - For standard/full workflows, require acceptance plus quick acceptance when
     quick acceptance was required after simplify.
   - If acceptance is missing, stop and return to `speckit.acceptance`.
4. Inspect current repository state for affected repositories:
   - Current branch, changed files, validation commands/latest results, ignored
     temp/generated artifacts, and remaining dirty files that matter for commit.
5. Create or update `FEATURE_DIR/workflow-record.md` with:
   - Basic feature metadata: feature name, branch, repositories,
     delivery_profile, risk_level, acceptance status.
   - Key user inputs, including initial request, corrections, clarifications,
     runtime evidence supplied by the user, and final acceptance.
   - AI actions by stage: major outputs, edited files, validation commands,
     build/install/run evidence, and state transitions.
   - Errors and rework: symptom, incorrect assumption or failed attempt,
     evidence that exposed it, final fix, and validation evidence.
   - Root-cause categories: information gap, runtime evidence gap, source vs
     artifact confusion, planning/task gap, tooling gap, branch/multi-repo gap,
     or other.
    - Quality assessment: task output quality, workflow quality, AI execution
      quality, remaining risk, and whether the system had enough evidence.
    - Rubric readiness: list evidence paths needed for final post-commit
      Rubric scoring, including AI Self-Acceptance, API/E2E plan, selected
     gate-pack evidence when applicable, runtime evidence when
     applicable, `implementation-summary.md`, and workflow compliance risks.
     Do not output final Rubric scores in retrospective.
   - `Accepted Gaps`: owner/user-accepted validation gaps, unsupported
     automation, product tradeoffs, excluded scope, and the evidence showing
     they were accepted.
   - Local artifact visibility: whether `workflow-record.md`,
     `improvement-candidates.md`, acceptance artifacts, or spec artifacts are
     intentionally local-only or ignored by `.gitignore`.
   - AI workflow self-check: expected stage path, actual stage path, mismatch,
     evidence, and the smallest repair location when the workflow diverged.
   - Existing Constraint Audit: before recommending any new durable rule,
     inspect existing constraints first: `ai/workflows/task-routing.md`, stage
     command templates, `workflow.yml`, scripts, tests, generated skill copies,
     and selected guides. Classify missing/weak/contradictory wording,
     script/preflight wiring, generated-context drift, unavailable tool, or
     LLM execution miss; prefer strengthening existing constraints first.
   - Team knowledge candidates: stable facts that required broad or repeated
     source reading, are likely long-lived, and can be expressed without
     machine-specific paths. Record evidence and the proposed knowledge-map or
     guide location, but keep the candidate pending until human approval.
   - Advanced-model context efficiency: record decision-critical facts,
     unnecessary loaded context, missing structured fields, script-generated
     evidence candidates, and the smallest useful context contract.
6. Create or update `FEATURE_DIR/improvement-candidates.md`.
   - If no reusable lesson exists, write `status: no-candidates` and do not
     invent broad advice.
   - If candidate lessons exist, each must include type, lesson, trigger
     condition, recommended landing place, expected benefit, over-generalization
     risk, and review status `pending`.
7. For each candidate, explicitly classify whether the lesson belongs to:
   - Foundation rules or memory.
   - Work Item templates or workflow state.
   - Capabilities: skills/tools/MCP capability governance.
   - Evidence: validation/evidence/retrospective flow.
   - Tests or automation scripts.
   - TEAM-README or other team operating docs.
   This stage records the suggested landing place only; it does not apply it and
   does not require promotion when all candidates are absent or still pending.
   - Use an automation-first filter: prefer scripts, deterministic checks,
     generated facts, or rule-based gates when mechanical; do not outsource
     a deterministic check to LLM judgment.
   - Use rules or automation only for conditions that are nearly deterministic.
     If a check requires semantic judgment, tradeoff analysis, quality
     evaluation, or context-sensitive interpretation, keep it as an LLM-owned
     review item with evidence instead of forcing weak automation that lowers
     quality.
   - For each candidate, record how it improves advanced-model context
     efficiency, judgment quality, or evidence sufficiency. If it does not
     improve context efficiency, explain why the candidate is still worth
     keeping.
8. Create or update `FEATURE_DIR/knowledge-candidates.md`.
   - This file records project long-term knowledge candidates only; it never
     modifies `ai/knowledge` during retrospective.
   - New candidates must default to `人工审核结论: pending`.
   - Include source evidence, applicability boundaries, recommended knowledge
     layer, recommended guide, confidence, and pollution risk.
   - If no stable reusable project knowledge exists, write
     `status: no-candidates`.
9. Run `collect-workflow-observer-packet` to produce
   `FEATURE_DIR/workflow-observer-packet.json` for a possible later
   `speckit.workflow-observer` stage. Do not write `workflow-observation.md`
   in this stage unless the workflow-observer command is being executed inline.
10. Update `FEATURE_DIR/workflow-state.json`: set `retrospective.status` to
    `completed`, link `workflow-record.md`, `improvement-candidates.md`, and
    `knowledge-candidates.md`, and preserve attempts, validations, fact-layer,
    acceptance, and promotion fields.
11. Do not modify spec-kit, `.specify/memory`, team governance files, or
   generated global rules from this stage. High-value lessons require human
   approval before promotion.
12. Update `review.md` when present so the human navigation page links to
   `workflow-record.md`, `improvement-candidates.md`, and
   `knowledge-candidates.md`.
13. Continue to `speckit.workflow-observer` only when that opt-in stage was
    explicitly selected. Continue to `speckit.promote-lessons` or
    `speckit.promote-knowledge` only when there are human-approved candidates
    and the user selected promotion; otherwise the usual next opt-in stage is
    `speckit.commit` when the user requested a commit.

## Workflow Record Template

```md
# 工作流留痕: [FEATURE]

## 1. 基本信息
- Feature:
- Branch:
- Repositories:
- Delivery profile:
- Risk level:
- Final acceptance:
## 2. 关键用户输入
- 初始需求:
- 关键补充:
- 用户提供的证据:
- 用户纠偏:
- 最终验收:
## 3. AI 输出与动作链
- 阶段:
- 输出:
- 修改文件:
- 验证命令:
- Runtime/browser screenshot directory:
- 结果:
## 4. 错误、返工与状态变化
- 现象:
- 错误判断或失败尝试:
- 暴露问题的证据:
- 解决动作:
- 最终验证:
## 5. 根因归类
- 信息不足:
- 运行时证据缺失:
- 源码/产物混淆:
- 计划或任务拆分不足:
- 工具链问题:
- 多仓或分支流程问题:
- 其他:
## 6. 可复用经验
- 经验:
- 适用条件:
- 不适用条件:
- 证据:
## 7. 自动化机会
- 可新增脚本:
- 可新增 checklist:
- 可新增 MCP/runtime evidence:
- 可新增 validation/evidence 模板:
- 可新增测试:
- 可新增 workflow gate:
- automation-first 判断:
## 8. 现有约束审计
- 相关已有约束:
- 约束状态:
- 失败归因:
- 优先修复位置:
## 9. 团队知识候选
- 候选事实:
- 稳定性判断:
- 来源证据:
- 推荐落盘位置:
- 审核状态:
## 10. 自动化 / LLM 分工判断
- 适合规则化/脚本化:
- 保留 LLM 判断:
- 避免自动化的原因:
## 11. Accepted Gaps
- 已接受缺口:
- 接受依据:
- 后续范围:
## 12. 质量判断
- 任务输出质量:
- Spec Kit 流程质量:
- AI 执行质量:
- 剩余风险:
## 13. Rubric 审计评分
| 维度 | 权重 | 得分/状态 | 证据 | 备注 |
|------|------|-----------|------|------|
| L1 功能正确性 | 0.40 |  |  |  |
| L2 健壮性 | 0.25 |  |  |  |
| L3 UI 呈现 | 0.20 |  |  |  |
| L4 交互体验 | 0.15 |  |  |  |
| AI 验收闭环 | hard gate |  |  |  |
| UI/UX 基线一致性 | UI gate |  |  |  |
| Spec Kit 流程执行 | process |  |  |  |
- 总分:
- 硬门禁结论:
- 是否可交给人类验收:
## 14. 高级模型上下文效率复盘
- 决策关键事实:
- 本次过量上下文:
- 本次缺失结构化字段:
- 应脚本生成的证据:
- 最小决策证据包:
- 建议沉淀到 spec-kit 的位置:
```

## Improvement Candidates Template

```md
# 改进候选清单

## 候选 1
- 类型:
- 经验:
- 触发条件:
- 推荐落盘位置:
- 预期收益:
- 过度泛化风险:
- 高级模型上下文收益:
- 可脚本化程度:
- 最小决策证据包:
- 人工审核结论: pending
- 审核人/来源:
- 批准范围:
```

Allowed review states are `pending | approved | rejected`. `retrospective`
must create new candidates as `pending`. A later `speckit.promote-lessons` stage
may promote only candidates that a human explicitly changes to `approved`.

## Knowledge Candidates Template

```md
# 知识候选清单

## Candidate 1
- 类型: project-knowledge | workflow-rule | validation-evidence | tool-policy
- 经验:
- 适用条件:
- 不适用条件:
- 推荐知识层:
- 推荐 guide:
- source_refs:
- 置信度: low | medium | high
- 污染风险:
- 人工审核结论: pending
```

Allowed review states are `pending | approved | rejected`. Retrospective must
create project knowledge candidates as `pending`. A later
`speckit.promote-knowledge` stage may promote only candidates that a human
explicitly changes to `approved`.

## Quality Rules

- Do not treat this stage as acceptance. Acceptance must already be explicit.
- Do not promote lessons or knowledge automatically. `pending` candidates are
  review input, not team policy.
- Do not ask humans to confirm AI-owned judgments such as test sufficiency or
  root-cause correctness. If the evidence is insufficient, mark the candidate
  as low confidence or omit it.
- Prefer zero or a few high-value candidates over broad generic advice.
- Prefer automation-first improvements: deterministic checks should become
  scripts, generated facts, template gates, checklist items, or validation
  commands before LLM memory or broad AI instructions.
- Keep sensitive information, secrets, and private credentials out of the
  retrospective artifacts.

## Fact Layer Retrospective

- Record 是否及时启用 fact-layer. For repeated UI/device-state fixes, unchanged
  rebuild/reinstall results, or a second same-class fix, `workflow-record.md`
  must state whether `speckit.fact-layer` produced `fact-pack.md`, latest service/runtime
  logs, and runtime DOM / computed style / box metrics were collected when needed.
- Missing or late fact-layer usage should become an improvement candidate.

## Evidence Retrospective

- Record whether validation claims had concrete evidence links.
- Record whether `validation.md` summarized result interpretation and whether
  `evidence.md` stored tool/test-facing raw facts.
- If validation evidence lived only in chat, console output, or implicit memory,
  create an `improvement-candidates.md` item recommending a durable evidence
  capture rule.

## Output

Report in Chinese:

- `workflow-record.md` path.
- `improvement-candidates.md` path.
- `knowledge-candidates.md` path.
- `workflow-observer-packet.json` path.
- `workflow-state.json` retrospective status update.
- Acceptance evidence used.
- Highest-value improvement candidates.
- Confirmation that this stage did not modify spec-kit, memory, team
  governance, long-term knowledge, product code, git history, branches, or
  remotes.
- Required next stage: explicitly selected opt-in follow-up; usually
  `speckit.commit` / `$speckit-commit` when the user requested a commit.
