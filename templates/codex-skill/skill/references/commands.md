# Task command contract

All paths below are relative to the project. Use `--project-dir <path>` when
outside it. Commands accept `--json`; blocked checks exit nonzero. Write JSON
inputs as UTF-8 files using normal file tools, preserving actual newlines.

```text
specify task start --request-file request.txt --source-ref "user:<message-id>" --json
specify context --select speckit/workflows::coding-lite --json
specify task record <id> --event-file event.json --json
specify task check <id> --phase contract --json
specify task run <id> --command-file command.json --json
specify task inspect <id> --json
specify task finish <id> --json
```

Each event file has `{"type":"<event>","payload":{...}}`. Event shapes:

- `clarification.recorded`: `{"status":"not-needed","reason":"scope and observable outcome are clear"}`;
  or status pending/answered, with questions:
  `[{"id":"Q1","question":"...","answer":"...","answer_origin":"human","source_ref":"user:...","requires_human":true}]`.
  Origins are human, host-auto, agent-assumption, unknown. Explicitly nonblocking
  assumptions use requires_human false and retain their origin.
- `workflow.selected`: `{"id":"speckit/workflows::coding-lite","reason":"bounded internal defect"}`.
- `contract.recorded`:
  `{"requirements":[{"id":"R1","criterion":"observable outcome","evidence_kinds":["test"]}],"files":["src","tests"],"inputs":[],"flags":{"changes_code":true}}`.
  Declare all source and diagnostic inputs that determine the result. A "." scope
  hashes the project except runtime/build/dependency directories. For diagnosis
  use evidence_status "observed" to allow a failed probe to establish the cause.
  Default evidence_status "passed" requires passing evidence.
- `resources.selected`: `{"ids":["owner/project::map"],"reason":"affected subsystem"}`.
- `ai.reviewed`:
  `{"status":"passed","summary":"verified outcome","criteria":[{"id":"R1","result":"passed","reason":"observed result matches criterion","evidence":["ev-..."]}]}`.
  A failed or blocked review may retain findings without passing gates.
- `knowledge.recorded`: `{"status":"none","reason":"no durable new project fact"}`;
  candidate/maintained also needs a path; deferred needs a reason.
- `human.recorded`: `{"status":"passed","origin":"human","quote":"actual user words","source_ref":"user:..."}`.
  rejected and explicitly allowed accepted-with-gaps are distinct states.
- `request.amended`: text, reason and source_ref. Keeps historical events but
  invalidates workflow, clarification, contract and acceptance for the new revision.
- `task.cancelled`: reason. Start a follow-up task for new work.

Command file for actual execution:

```json
{"argv":["python","-m","pytest","-q"],"cwd":".","kind":"test","requirements":["R1"],"timeout_seconds":120}
```

There is no shell interpolation. Use a registered check with
`{"check_resource":"owner/project::check","requirements":["R1"]}`; the runner
loads its immutable descriptor instead of accepting a replacement command.
Use action_resource instead of check_resource to execute a declared action;
its receipt is diagnostic evidence. Selecting a Skill resource returns its
SKILL.md body and installed path; resolve supporting files relative to that
path. Pack skills are not automatically registered as separate native skills.
structured true requires the whole stdout to be a JSON object with a positive
status. A negative JSON status blocks even when the process exits zero.

`events.jsonl` is the canonical append-only journal. task.json and report.md are
projections; inspect rebuilds state from events. Hash chaining detects accidental
corruption, not a hostile writer able to rewrite the entire local repository.
