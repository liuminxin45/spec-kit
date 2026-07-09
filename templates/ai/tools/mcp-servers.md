# MCP Servers

This file documents MCP servers known to Spec Kit. It does not make any MCP
server mandatory for normal feature work.

## Browser Runtime Inspection

Server id:

```text
chrome-devtools
```

Default command configured by `configure-mcp-agents.ps1`:

```text
npm exec --yes --package=chrome-devtools-mcp@latest -c "chrome-devtools-mcp --slim"
```

Connection modes:

- `browser-slim` (default): use the MCP server's slim toolset; attach to a
  browser/runtime target only when `-BrowserUrl` is supplied.
- `browser`: use the full Chrome DevTools MCP toolset; attach to a
  browser/runtime target only when `-BrowserUrl` is supplied.
- `auto`: omit `--browserUrl` and let Chrome DevTools MCP launch or discover a
  browser.
- explicit args: bypass mode-derived defaults for advanced troubleshooting.

Global Node.js requirement for MCP setup:

```text
^20.19.0 || ^22.12.0 || >=23
```

Expected target:

```text
Configured by repository-map, selected gates, or explicit user input.
```

Runtime launch:

```text
Use the command documented by the repository or selected gate pack.
```

When using a remote debugging endpoint, confirm the endpoint and choose the real
target page before collecting evidence.

Preferred target patterns:

```text
Configured by repository-map, selected gates, or explicit user input.
```

When investigating runtime UI, attach to the real target. Do not treat DevTools,
a newly launched blank page, or any unrelated target as evidence for the target
application. For embedded UI fixes, prefer the real target after source build
and runtime/deploy sync; use isolated previews only as fallback or supplemental
evidence.

For CSS-only hover states, a dispatched mouse event may not always produce a
stable hover state. Use the available inspection tool's pseudo-state support on
the target node when needed, and record that method in validation evidence.

## Agent Configuration Support

`configure-mcp-agents.ps1` configures Codex TOML
`[mcp_servers.<id>]` entries only in this team distribution.

The script configures capability access only. Runtime use is governed by
`ai/tools/mcp-usage-policy.md` and `ai/tools/mcp-permissions.md`.

## Fallback

If no browser inspection MCP server or usable runtime target is available, ask the
user for the relevant DOM/CSS/console excerpt and continue from that evidence.
