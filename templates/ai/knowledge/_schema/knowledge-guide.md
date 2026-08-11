# Knowledge Guide Schema

Each guide should begin with lightweight metadata:

```yaml
---
authority: generated | reviewed | authoritative
confidence: low | medium | high
knowledge_kind: policy | implementation-fact | procedure
source_refs:
  - path-or-command-used-as-evidence
last_verified: YYYY-MM-DD or null
verified_revisions: {"repository-name":"full-git-revision"}
conformance_checks: [{"repository":"repository-name","path":"relative/path","command":"path-exists | file-contains | git-tracked","pattern":"optional literal","expected":"true | false | present | absent"}]
supersedes: []
superseded_by: []
revalidation_triggers: ["repository revision change", "path or command change"]
---
```

Authority means:

- `generated`: AI/bootstrap draft. Useful for routing, never final proof.
- `reviewed`: human or maintainer reviewed. Usable as project guidance.
- `authoritative`: backed by source, policy, or owner-approved documentation.

Selectors may load generated guides, but the agent must ground risky decisions in
source evidence or reviewed/authoritative guides.

`implementation-fact` entries become `needs-revalidation` when a recorded
repository revision changes and are excluded by default. `policy` remains
selectable when conformance fails, but must be labeled as policy not implemented
by current source. `procedure` is selectable only while its relative paths and
allowlisted read-only checks pass. Use JSON-compatible inline values for the
five lifecycle fields so the PowerShell validator can parse them without a YAML
runtime. Reviewed/high-confidence promotion requires passing conformance.
