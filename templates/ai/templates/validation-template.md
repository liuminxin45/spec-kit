# Validation

This is the default L5 validation summary for a feature. It records what was
checked and what the result means. It pairs with `acceptance.md`; validation-only
work also writes into this file instead of creating a separate report.

## 1. Scope

- Feature:
- Repositories:
- Delivery profile:
- Risk level:
- Validation owner:

## 2. Validation Matrix

| Target | Command / Manual Check | Expected Result | Actual Result | Evidence |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |

## 3. Result Interpretation

- Passed checks:
- Failed checks:
- Not run:
- Known gaps:
- LLM judgment:

## 4. Routing Impact

- Continue current workflow:
- Return to implement:
- Return to plan/tasks:
- Escalate to fact-layer:
- Human/user acceptance required:

## 5. Evidence Links

- `acceptance.md`:
- `evidence.md` (optional for complex/runtime/tool-heavy evidence):
- `fact-pack.md` (optional fact-layer evidence):
- Logs:
- Screenshots:
- Screenshot directory:
- Test output:

## 6. Validation Context Contract

- Decision-critical facts used:
- Evidence sources actually loaded:
- Context intentionally not loaded:
- Missing facts:
- Sufficiency judgment:
- Reason this is enough for AI acceptance:

## 7. Selected Gate / Runtime Evidence

- Applies:
- Source edit evidence:
- Build command/result:
- Runtime/deployment verification evidence:
- Runtime directory:
- Removed stale runtime files:
- Runtime target id/title/url:
- Key-path screenshots:
- Loaded resource evidence:
- Final package/release evidence when selected gates require it:

## 8. Integration / Generated-Artifact Evidence

- Applies:
- Source edit evidence:
- Build/export command/result:
- Runtime replacement evidence:
- Runtime directory:
- Generated artifact hash/parity evidence:
- Protocol/export validation:
- Restart/reload evidence:
- Runtime/external-system behavior evidence:
- Final package/release evidence:

## 9. AI Acceptance Result

- AI acceptance status: `PASS | BLOCKED | FAIL`
- AI Self-Acceptance skill run:
- Acceptance rubric source:
- Essential result:
- Pitfall result:
- UI baseline source/status:
- Original symptom reproduced before fix:
- Original symptom absent after fix:
- Runtime/browser/external-system validation loop completed:
- Remaining blocker, if any:
- Human acceptance may start:

## 10. Final Rubric Score (strict/release only)

Do not fill this section for normal lean delivery. Use it only when the user
selected strict/release scoring, `speckit.rubric-score`, or branch completion.
The final Rubric may also be written to `rubric-score.md`; if so, link it here.

| Dimension | Weight | Score / Status | Evidence | Deduction Notes |
| --- | --- | --- | --- | --- |
| L1 功能与需求闭合 | 0.30 |  |  |  |
| L2 验证与证据 | 0.25 |  |  |  |
| L3 工作流阶段合规 | 0.25 |  |  |  |
| L4 交付与仓库状态 | 0.10 |  |  |  |
| L5 上下文与自动化治理 | 0.10 |  |  |  |

- Overall Weighted Score:
- Hard-gate result:
- Complete-branch allowed: `yes | no`
- Main deduction reason:
- Accepted gap evidence, if any:

## Rules

- No validation claim is complete without a concrete evidence reference in this
  file, `acceptance.md`, `evidence.md`, `fact-pack.md`, logs, screenshots,
  command output, or another cited artifact.
- This file may summarize sufficiency, but only the LLM can judge sufficiency.
- Keep raw command output and tool facts in `evidence.md` when they are lengthy.
- For selected gate-pack validation, record the selected gate id, target
  identity, commands run, evidence paths, and unresolved gaps before asking for
  human acceptance. Record final package/release evidence when selected gates or
  strict delivery require it.
- For runtime/browser validation, record the selected target id/title/url when
  available. Mark unrelated targets as `wrong-target / insufficient`. Save
  key-path screenshots when they decide acceptance and report the screenshot
  directory to the human when validation ends.
- If AI changed code, human acceptance may start only after this file records
  AI acceptance `PASS` or a true external blocker. Fixable runtime target,
  sync, process, generated-artifact, or deployment gaps must return to
  implementation.
- For integration/protocol changes, validate required generated bundle messages
  and fields before using frontend/UI behavior as final evidence.
- AI self-acceptance records criteria coverage only. Final Rubric score output
  is strict/release opt-in and is not required for normal lean delivery.
