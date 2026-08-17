# Spec Kit 与知识包本地安装指南（AI 使用）

本产物用于在不访问 Spec Kit 源码仓库的情况下安装 `specify-cli`，并可把调用方显式
选择的知识包挂载到目标工作区。Spec Kit 不内置任何项目名称、仓库名称、pack id 或
产品事实。安装不会执行知识 promotion，不会提交或推送代码，也不会执行知识包中的脚本。

## 产物结构

```text
<bundle>/
├── Install-Local.ps1
├── INSTALL-AI.md
├── bundle-manifest.json
├── SHA256SUMS.json
├── spec-kit/specify_cli-<version>-py3-none-any.whl
├── knowledge-packs/<pack-id>/
└── knowledge-pack-archives/<pack-id>-<version>.zip
```

ZIP 仅用于传输。挂载前应解压整个 bundle；`specify` 当前接收知识包目录，不直接接收
知识包 ZIP。

## 前置条件与完整性检查

- Windows PowerShell 7（`pwsh`）。
- Python 3.11 或更高版本。
- `uv`。Spec Kit wheel 位于本地；它的 Python 依赖由 `uv` 从本机缓存或配置的软件源
  解析。完全离线环境还需要事先准备依赖 wheelhouse/缓存。

`Install-Local.ps1` 会在安装 wheel 前自动校验 bundle 内所有 SHA-256。也可以在执行前手工复核：

```powershell
$root = (Resolve-Path <bundle-root>).Path
$failures = foreach ($item in (Get-Content "$root\SHA256SUMS.json" -Raw | ConvertFrom-Json)) {
  $actual = (Get-FileHash -LiteralPath (Join-Path $root $item.path) -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actual -ne $item.sha256) { $item.path }
}
if ($failures) { throw "Bundle checksum mismatch: $($failures -join ', ')" }
```

## AI 执行约束

1. 先读取 `bundle-manifest.json` 和 `SHA256SUMS.json`，确认版本、pack id 和哈希。
2. 已存在 Spec Kit 的项目默认走安全升级，不覆盖用户改过的 managed assets。
3. 只有用户明确授权时才使用 `-ForceManagedAssetRefresh`。
4. bundle 中的 pack 必须按 manifest 的 `default_compose_order` 一次性 compose，不能连续
   `apply-pack` 后假设此前 pack 仍处于 active 状态。
5. pack 的用途、依赖、迁移关系和目标仓库只能从其 manifest、guide 和 conformance
   元数据读取，不能由 Spec Kit 或 AI 猜测。
6. 安装和挂载不等于 promotion。不得自动运行 `promote-candidates`。
7. Spec Kit 基础设施任务路由知识时使用 `IgnoreActiveFeature`，避免被目标工作区的活动
   feature 污染。

## 适用边界

Spec Kit wheel 可安装到新项目或现有项目。知识包可能包含与特定仓库 revision 绑定的
`implementation-fact`，因此只能挂载到能够解析其 repository 名称并通过 conformance
检查的工作区。

在不含对应仓库的项目中，可用 `-SkipKnowledgePacks` 仅安装 Spec Kit。若强行挂载，
`validate-knowledge-index` 因无法完成 conformance 而返回 blocked 是预期安全行为，AI
不得把它绕过或改写成成功。

## 一键安装并挂载

PowerShell：

```powershell
pwsh -NoProfile -File .\Install-Local.ps1 `
  -ProjectPath <target-project-root> `
  -Json
```

行为：

- 用本地 wheel 安装/重装 `specify-cli`。
- 新项目执行 `specify init`；已初始化项目先 dry-run，再执行安全 `specify upgrade`。
- 对已有项目的每个已安装 integration 先 dry-run，再执行 `specify integration upgrade`。
- 安装 bundle 中显式包含的知识包并严格按 `default_compose_order` 统一 compose。
- 运行 generated context、knowledge index 和 context budget 三项验证。
- 最后运行带受管文件哈希核验的 `specify self check`；版本过期或文件缺失时安装失败，
  用户定制文件会以 `warning` 而不是虚假的 `ok` 返回。

仅安装 Spec Kit，不挂载知识包：

```powershell
pwsh -NoProfile -File .\Install-Local.ps1 `
  -ProjectPath <target-project-root> `
  -SkipKnowledgePacks
```

明确授权覆盖已定制 managed assets 时：

```powershell
pwsh -NoProfile -File .\Install-Local.ps1 `
  -ProjectPath <target-project-root> `
  -ForceManagedAssetRefresh
```

## 手动安装 Spec Kit

```powershell
uv tool install .\spec-kit\specify_cli-<version>-py3-none-any.whl --force --reinstall
specify --version
```

新项目初始化：

```powershell
Set-Location <target-project-root>
specify init --here --force --no-git --ignore-agent-tools
```

已有项目先预览再升级：

```powershell
specify upgrade --project-dir <target-project-root> --dry-run --json
specify upgrade --project-dir <target-project-root>
specify integration upgrade codex --project-dir <target-project-root> --dry-run --json
specify integration upgrade codex --project-dir <target-project-root>
specify self check --project-dir <target-project-root> --json
```

## 手动挂载多个知识包

不要逐个调用高级 `apply-pack` 后结束；应先全部安装，再统一 compose：

```powershell
$project = Resolve-Path <target-project-root>
$bundle = Resolve-Path <bundle-root>
$manifest = Get-Content "$bundle\bundle-manifest.json" -Raw | ConvertFrom-Json
$ids = @($manifest.default_compose_order)

foreach ($pack in @($manifest.knowledge_packs)) {
  & "$project\.specify\scripts\powershell\install-knowledge-pack.ps1" `
    -RepoRoot $project `
    -PackPath (Join-Path $bundle $pack.directory) `
    -Force -Json
}

& "$project\.specify\scripts\powershell\compose-knowledge-packs.ps1" `
  -RepoRoot $project -PackId $ids -Json
```

挂载记录位于：

```text
.specify/knowledge/records/
.specify/knowledge/lock.yml
.specify/capabilities/lock.yml
```

## 安装后验证

```powershell
& <target-project-root>\.specify\scripts\powershell\validate-generated-context.ps1 `
  -RepoRoot <target-project-root> -Json
& <target-project-root>\.specify\scripts\powershell\validate-knowledge-index.ps1 `
  -RepoRoot <target-project-root> -Json
& <target-project-root>\.specify\scripts\powershell\validate-context-budget.ps1 `
  -RepoRoot <target-project-root> -Json
```

三项必须返回 `status: ok`。路由检查时同时检查 `selected` 和负向
`expected_excluded`；不能只比较来源包是否相同。

## 更新与卸载知识包

用新目录更新某个已安装 pack：

```powershell
specify knowledge update-pack <new-pack-dir> --project-dir <target-project-root> --json
```

卸载：

```powershell
specify knowledge uninstall-pack <pack-id> --project-dir <target-project-root> --json
```

更新或卸载后重新执行三项验证。知识 promotion 仍需独立人工批准。
