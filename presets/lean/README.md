# CoreServicesLib Lean Preset

Lean is an explicit compact preset, not the default installed team workflow.
Default initialization installs the complete
`intake -> specify -> clarify -> plan -> tasks -> analyze -> checklist gate -> implement`
workflow. Use Lean only when the team deliberately opts into a reduced preset
for small, scoped changes.

Lean keeps the structured `specify -> plan -> tasks -> implement` pipeline, but
avoids the full ceremony of the default templates. It still requires validation
and test-case closure before handoff, and it preserves intake routing context
when `intake.md` is present.

## When To Use

Use Lean for small bug fixes, narrow plugin updates, focused SDK adjustments,
script/tooling changes, or internal migrations where the affected modules and
validation path are already clear.

Use the full templates when compatibility, device behavior, frontend state,
public APIs, or downstream migration risk needs deeper analysis.

## Commands Included

| Command | Output | Description |
|---------|--------|-------------|
| `speckit.specify` | `spec.md` | Compact capability specification |
| `speckit.plan` | `plan.md` | Boundaries, risks, and validation plan |
| `speckit.tasks` | `tasks.md` | Focused implementation tasks |
| `speckit.implement` | code + `tasks.md` | Execute scoped tasks |
| `speckit.constitution` | `constitution.md` | Maintain team principles |

## Team Rules

- Keep changes scoped.
- Preserve intake classification: migration, bugfix, new-feature, or
  needs-routing.
- For UI-related migration or new-feature, name UI design/source directories or
  record explicit N/A reasons.
- Follow existing project patterns.
- Treat compatibility boundaries as first-class.
- Preserve real runtime/device/status/permission state.
- Record validation evidence or known gaps.
- After validation passes, add or update the corresponding unit test,
  regression test, fixture, contract test, smoke case, or explicit N/A reason.
- Re-run affected tests or substitute validation after the test-case update.
- Use local Spec branches only; do not push them, create remote tracking, or
  depend on GitHub issue generation.
- Complete the Spec by merging the local Spec branch back to the configured
  base branch across affected repositories, then deleting the local branch.
- Require explicit user confirmation before any agent runs branch merge/delete
  completion commands.
