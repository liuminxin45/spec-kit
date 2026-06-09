# Frontend Plugin Runtime

## Load When

- Task touches frontend plugin source, visible UI, runtime sync, build output,
  `front-meta.json`, mock data, or host-served plugin resources.

## Source To Runtime Chain

```text
ProductUIPlugin/<plugin-id>/ source
  -> plugin frontend build
  -> built dist output
  -> direct runtime replacement in host-served frontend plugin directory
  -> real DesktopShell host CDP validation
```

## Rules

- Edit repository source first.
- Build before runtime replacement.
- Runtime files are validation/deployment artifacts, not durable fixes.
- Validate host-embedded layout in the real Electron host when parent layout,
  event routing, runtime state, or CDP evidence matters.

## Useful Evidence

- Source directory and plugin id.
- Build command and result.
- Runtime directory and removed stale count.
- Resource entries loaded by the real host target.
- DOM/computed style/box metrics for visual/layout fixes.

## Verify Before Use

Read the plugin's `package.json`, metadata files, and host location before
choosing build and sync commands.
