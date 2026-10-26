# Acceptance evidence

Use real capabilities available in the current host. A tool descriptor in a pack
does not install a tool or establish that MCP, CDP, a browser extension or computer
use is connected. Discover the host tool and prove the actual target.

For commands, use task run; importing a hand-written test/build/check receipt is
rejected. The runner records argv, cwd, time, exit code, bounded timeout, stdout
and stderr. A command can itself be a weak test: judge whether it proves the
criterion. The runner is not a sandbox.

For screenshots, runtime observations and interaction traces, save the artifact
inside the project and import with evidence.added:

```json
{"type":"evidence.added","payload":{"kind":"screenshot","path":"evidence/after.png","origin":"tool-observed","tool_ref":"actual-tool-call-id","target":{"identity":"http://localhost:3000/settings","build":"current commit/build"},"requirements":["R1"],"result":"passed","description":"Observed required page state at the stated viewport"}}
```

Allowed origins: tool-observed, human-supplied, agent-authored. Authored notes do
not satisfy UI/runtime observation gates. A reference is recorded provenance,
not a cryptographic host attestation. A selected MCP/hook resource also needs a
current tool-observed artifact with
capability_id set to its qualified resource ID, target.identity and tool_ref
before it counts as a verified connection. Descriptors alone never qualify.
Keep claims within the observed scope: a browser capture does not prove a native
device or installer worked. For UI
behavior also map interaction evidence to its criterion; a screenshot alone
proves appearance only. Sensitive logs require review before sharing; common
tokens and secrets are redacted by the runner, not arbitrary private data.

Every AI review covers all current requirements exactly once with explanation
and evidence IDs. Changed source, changed diagnostic input, amended requirements,
modified artifact or changed package binding invalidates prior proof.
Human acceptance remains separate from AI acceptance and command success.
