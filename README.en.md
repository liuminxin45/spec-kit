# Spec Kit

**Give Codex a path from intent to verified delivery.**

[简体中文](README.md) · [Quick start](#quick-start) · [Documentation](docs/README.md) · [Latest release](https://github.com/liuminxin45/spec-kit/releases/latest)

[![Release](https://img.shields.io/github/v/release/liuminxin45/spec-kit)](https://github.com/liuminxin45/spec-kit/releases/latest)
[![Stars](https://img.shields.io/github/stars/liuminxin45/spec-kit?style=flat)](https://github.com/liuminxin45/spec-kit/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Getting AI to write code is one step. Spec Kit helps Codex clarify requirements, choose a workflow that fits the risk, load relevant project knowledge, and collect evidence before asking you to accept the result.

## Why use it?

- **Keep small changes small.** Use a compact plan for a simple fix; expand into specifications, tasks, and validation gates when the change needs them.
- **Reuse project knowledge.** Package repository facts and constraints separately, then load them when relevant.
- **Review the evidence.** Ask for test, build, log, or UI inspection results, with unverified areas called out.
- **Keep control of delivery.** AI checks its work before your acceptance. Commits, integration, and pushes follow explicit authorization.

```text
Describe the change → Choose a workflow → Implement → Collect evidence → Human acceptance
```

For developers and teams who want AI changes they can assess and accept.

## One Skill, composable project knowledge

New projects should use the version 2.0 **Codex + `$speckit` + packs** mode.
Load project maps, debugging guides, design assets, requirements and workflows
when needed; keep requests, clarification and actual acceptance evidence together.
After installing version 2.0, use
`specify init --here --mode codex-skill` explicitly: omitting `--mode` still selects legacy.
The setup instruction below selects 2.0 for first-time setup and preserves existing project modes.
See the [new mode guide](docs/codex-skill-mode.md).

## Quick start

Open an agent in your **target project directory** and paste this sentence:

```text
Read https://raw.githubusercontent.com/liuminxin45/spec-kit/main/docs/agent-setup.md and follow it to install or safely upgrade Spec Kit in this project, explicitly use --mode codex-skill for first-time setup, preserve the mode of existing projects, run mode-specific checks, and show the matching task entry.
```

An agent with terminal and file access can perform setup. The installed workflow targets **Codex**. The supported environment is **Windows with PowerShell 7**, Python 3.11+, Git, and uv. The guide checks prerequisites and preserves existing project configuration. Detailed operating docs are currently in Chinese; your agent can follow them in your language.

## After setup

After 2.0 setup and checks, invoke the main Skill in Codex:

```text
$speckit Fix the unclear error message after a failed login. Verify the cause first and report the validation results.
```

Use it for features, fixes, refactoring, migrations, or validation alone. Codex selects the workflow based on scope and risk. Existing legacy projects retain their entry; see [compatibility and migration](docs/agent-setup.md#6-legacy-兼容与迁移).

## What can it verify?

Tests, builds, logs, and runtime inspection can support acceptance. CDP-accessible interfaces such as Electron, Chromium, and WebView can also expose DOM, network, styles, and screenshots. Native interfaces, physical devices, and external services need appropriate evidence; missing evidence must be reported.

## Go deeper

| Task | Guide |
| --- | --- |
| Install, upgrade, and check a project | [Agent setup](docs/agent-setup.md) |
| Look up 2.0 commands, workflows, packs, and acceptance | [2.0 guide](docs/codex-skill-mode.md) |
| Maintain an existing legacy project | [Compatibility and migration](docs/agent-setup.md#6-legacy-兼容与迁移) |
| Explore documentation and contribute | [Documentation index](docs/README.md) |

If this helps your work, **Star the repository** to help others find it. [Issues](https://github.com/liuminxin45/spec-kit/issues) and pull requests are welcome; include your version, expected behavior, and reproduction steps when reporting a problem.

## Credits and license

Built on [github/spec-kit](https://github.com/github/spec-kit) and independently developed for Codex delivery workflows. This repository is not an official GitHub project. [MIT License](LICENSE).
