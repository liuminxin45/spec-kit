---
description: Record the completed Spec Kit workflow before commit without auto-promoting lessons.
scripts:
  sh: scripts/bash/check-prerequisites.sh --json --include-tasks
  ps: scripts/powershell/check-prerequisites.ps1 -Json -IncludeTasks
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

After final user acceptance and before `speckit.commit`, create a lightweight
durable record of the current Spec Kit workflow. This 留痕 stage runs after
用户验收通过 and is mandatory for standard/full Spec Kit delivery before commit.
The default output is concise traceability: 关键用户输入, AI 输出与动作链, 验证证据,
最终状态, and meaningful errors when present. Expand into detailed error/rework
analysis only when the run had repeated failure, a new pitfall, a new rule, a
new automation opportunity, a tool/runtime evidence issue, or a user-approved
lesson candidate.

This stage writes feature-local retrospective artifacts only. 不自动修改 tools/spec-kit,
memory, team governance, product code, git history, branch state, remotes, or
promote lessons into long-term policy.

## Language Rules

- `workflow-record.md`, `improvement-candidates.md`, user-facing summaries, and
  review prompts use Chinese-first style.
- Preserve technical identifiers in their original form: paths, commands,
  commit hashes, branch names, repository names, APIs, fields, and test names.
- Separate facts from inferences. Mark inferred root causes or process lessons
  as inference unless directly evidenced.

## Execution Steps

1. Run the prerequisite script and parse `FEATURE_DIR` and `AVAILABLE_DOCS`.
2. Load available feature artifacts:
   - `FEATURE_DIR/intake.md`
   - `FEATURE_DIR/spec.md`
   - `FEATURE_DIR/plan.md`
   - `FEATURE_DIR/tasks.md`
   - `FEATURE_DIR/progress.md`
   - `FEATURE_DIR/review.md`
   - `FEATURE_DIR/lessons.md`
   - `FEATURE_DIR/validation.md`
   - `FEATURE_DIR/evidence.md`
   - `FEATURE_DIR/fact-pack.md`
   - `FEATURE_DIR/acceptance.md`
   - `FEATURE_DIR/acceptance-checklist.md`
   - `FEATURE_DIR/checklists/`
3. Confirm final acceptance has explicit evidence.
   - For standard/full workflows, require acceptance plus quick acceptance when
     quick acceptance was required after simplify.
   - If acceptance is missing, stop and return to `speckit.acceptance`.
4. Inspect current repository state for affected repositories:
   - Current branch.
   - Changed files.
   - Validation commands and latest results.
   - Known untracked temp/generated artifacts that were ignored.
   - Remaining dirty files that will matter for commit.
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
   - `Accepted Gaps`: owner/user-accepted validation gaps, unsupported
     automation, product tradeoffs, excluded scope, and the evidence showing
     they were accepted.
   - Local artifact visibility: whether `workflow-record.md`,
     `improvement-candidates.md`, acceptance artifacts, or spec artifacts are
     intentionally local-only or ignored by `.gitignore`.
6. Create or update `FEATURE_DIR/improvement-candidates.md`.
   - If no reusable lesson exists, write `status: no-candidates` and do not
     invent broad advice.
   - If candidate lessons exist, each candidate must include:
   - Type: checklist, workflow, template, memory, team norm, tool automation,
     test, or other.
   - Lesson.
   - Trigger condition.
   - Recommended landing place.
   - Expected benefit.
   - Risk of over-generalization.
   - Review status: `pending`.
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
     generated facts, or rule-based gates over LLM/AI judgment whenever the
     condition can be checked mechanically. If the candidate can be encoded as
     a script, validation command, template gate, checklist item, or generated
     fact, recommend that landing place before memory or team norm. In short,
     do not outsource a deterministic check to LLM judgment.
8. Do not modify tools/spec-kit, `.specify/memory`, team governance files, or
   generated global rules from this stage. High-value lessons require human
   approval before promotion.
9. Update `review.md` when present so the human navigation page links to
   `workflow-record.md` and `improvement-candidates.md`.
10. Continue to `speckit.promote-lessons` only when there are human-approved
    improvement candidates; otherwise continue to `speckit.commit`.

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

## 8. Accepted Gaps
- 已接受缺口:
- 接受依据:
- 后续范围:

## 9. 质量判断
- 任务输出质量:
- Spec Kit 流程质量:
- AI 执行质量:
- 剩余风险:
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
- 人工审核结论: pending
- 审核人/来源:
- 批准范围:
```

Allowed review states are `pending | approved | rejected`. `retrospective`
must create new candidates as `pending`. A later `speckit.promote-lessons` stage
may promote only candidates that a human explicitly changes to `approved`.

## Quality Rules

- Do not treat this stage as acceptance. Acceptance must already be explicit.
- Do not promote lessons automatically. `pending` candidates are review input,
  not team policy.
- Do not ask humans to confirm AI-owned judgments such as test sufficiency or
  root-cause correctness. If the evidence is insufficient, mark the candidate
  as low confidence or omit it.
- Prefer zero or a few high-value candidates over broad generic advice.
- Prefer automation-first improvements when possible: deterministic checks
  should become scripts, generated facts, template gates, checklist items, or
  validation commands before they become LLM memory or broad AI instructions.
- Keep sensitive information, secrets, and private credentials out of the
  retrospective artifacts.

## Fact Layer Retrospective

- Record 是否及时启用 fact-layer. If the workflow had repeated UI fixes,
  repeated device-state fixes, unchanged rebuild/reinstall results, or a second
  same-class fix, `workflow-record.md` must state whether
  `speckit.fact-layer` produced a `fact-pack.md`, whether latest SDK/Biz logs
  were checked, and whether chrome-devtools runtime DOM / computed style / box
  metrics were collected when needed.
- Missing or late fact-layer usage should become an
  `improvement-candidates.md` item.

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
- Acceptance evidence used.
- Highest-value improvement candidates.
- Confirmation that this stage did not modify tools/spec-kit, memory, team
  governance, product code, git history, branches, or remotes.
- Required next stage: `speckit.promote-lessons` / `$speckit-promote-lessons`
  only if approved candidates exist; otherwise `speckit.commit` /
  `$speckit-commit`.
