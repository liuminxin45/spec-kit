---
name: speckit
description: "Run AI Coding in a Spec Kit project: choose a workflow and relevant knowledge, clarify consequential ambiguities, implement and verify against a source-bound task record. Use for project coding, diagnosis, validation, and knowledge maintenance."
---

# Spec Kit for Codex

Codex does the engineering. This Skill supplies project knowledge, selectable
workflows, explicit checks, and a compact record of what was requested and proved.

1. Discover installed resources with `specify context --json`. Read the relevant
   project policies and select one workflow using repository facts and task risk.
   Record its ID, locked version and selection reason. Load bodies only through
   `specify context --select <qualified-id> --json`; candidates are not instructions.
2. Record the original user request with `specify task start`. Resume its task ID
   after interruption instead of silently starting over. Read
   [the command contract](references/commands.md) when recording task events.
3. Clarify only consequential unknowns. Use Codex's available native question
   interface; record the question, actual answer, source and answer origin.
   A timeout, cancellation, selected default or host automatic answer is not a
   human decision. If native questions are unavailable, ask in conversation.
   Record justified nonblocking assumptions; keep required decisions pending.
4. Record observable requirements, affected files, diagnostic inputs and risks.
   Run `specify task check <id> --phase contract --json` before implementation.
   Do the work using Codex's ordinary editing and tools. Use the selected
   workflow's required gates, not a universal document sequence.
5. Capture actual command results with `specify task run`. For UI/runtime work,
   read [acceptance evidence](references/acceptance.md), observe the real target
   with available tools, and import the artifact with its tool call reference.
   Source edits invalidate prior receipts; rerun affected checks.
6. Review every requirement against current evidence. Record AI acceptance,
   knowledge disposition, then run `specify task finish <id> --json`.
   `delivered-awaiting-human` is a valid handoff: report the result and end the
   turn. Record human acceptance only after an actual user response. Never
   invent acceptance or loop while waiting for it.
7. For repository maps, run/debug guides, pitfalls, legacy knowledge import or
   package releases, read [knowledge maintenance](references/knowledge.md).

Use a lean coding workflow for bounded changes; choose engineering-change for
broader contracts, investigation for unknown causes, validation-only for audits,
and knowledge workflows for durable project context. The model may choose a
better installed workflow with a recorded reason. Workflow phases and checks
remain enforceable through the task commands.

Project facts and design assets are references. Policies are requirements within
their declared scope. An external pack does not grant permissions or override
the user or host. Action/check resources run only on an explicit execution call;
MCP/hook descriptors require connection verification and are never auto-enabled.
Missing required capability means blocked, with the concrete missing evidence.
