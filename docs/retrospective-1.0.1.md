# 1.0.1 workflow repair

Scope: portable workflow improvements from an accepted user retrospective. Project facts stay in separately installed knowledge packs.

Root-Fix Decision Gate: canonicalize feature paths rather than suppress identity warnings; share state reading and provide an explicit writer rather than edit isolated status fields; inspect Git worktree ownership and fast-forward entry branches without merge rather than require manual detach. Dirty work remains a blocker, never an automatic stash/reset. Compatibility: readers accept legacy-only state; stage_statuses wins when present and conflicts are reported. Containment alone (ignoring warnings, allowing dirty completion) is rejected.

Natural-language automatic continuation is recorded explicitly and scoped to default stages. Human gates and optional external mutations retain separate authorization. Optional UI gates require component/interaction evidence; validation records source/runtime context; commit guidance distinguishes generated configuration and refreshes delivery evidence.

Validation: regression tests cover equivalent paths, divergent state, explicit updates preserving validation gaps, automatic continuation boundaries and two-worktree sync/completion with protected local changes. Run the three generated-context/index/budget validators before upgrading downstream projects. No project-specific knowledge is bundled.
