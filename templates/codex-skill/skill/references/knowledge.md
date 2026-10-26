# Knowledge lifecycle

`specify pack bootstrap --id owner/project --output knowledge/project --json`
creates an authoring pack from bounded repository evidence: file map, manifest
locations and candidate run/debug commands. It labels unknown ownership, runtime
and design facts instead of guessing. Review and improve those facts before use.
Do not include credentials, private service URLs or binaries in a public pack.

`specify pack import-legacy --source ai/knowledge --id owner/imported --output knowledge/imported --json`
copies legacy references into a new authoring pack with provenance and a review
list. It does not reinterpret legacy prose as mandatory policies or migrate the
active project. Review maps, platform-specific commands and stale paths manually.

Maintain maps when boundaries change; add a pitfall only with symptom, applicable
scope, evidence, root cause, resolution and verification. Repeated lessons can
be promoted into an explicit policy or check after review. Keep candidates apart
from approved knowledge. Avoid storing transient tasks as permanent rules.

Validate with `specify pack validate <authoring-directory> --json`. Release:
`specify pack release <directory> --bump patch --reason "verified guide correction" --review-file review.json --json`.
The review file records status passed, origin human, source_ref and actual quote.
Use minor for backward-compatible capabilities, major for changed mandatory
contracts, patch for corrections. Workflow versions track their containing pack.
The release writes a changelog and a content fingerprint; installed versions
are immutable. A local release does not tag, commit, push or publish anything.

Install with `specify pack add <directory> --json`; multiple sources can be given
together for exact dependencies. Update with `specify pack update <directory>`.
Remote source form: git+https://host/owner/repo.git@<full-40-character-commit>.
Unpinned branches/tags are rejected. `pack restore` restores missing caches from
the locked sources only when their fingerprints still match.

`pack bind <pack-id> --scope "src/**"` scopes candidates. `--require <policy-id>`
marks selected policies mandatory in that binding. Layer/owner metadata identifies
personal, organization, project, component or task context; identity and declared
scope govern loading, rather than directory precedence. Conflicting mandatory
policies need an explicit human decision. Required resources are never silently
hidden by optional capability filtering.
