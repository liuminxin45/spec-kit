# Spec Kit：给 Agent 的安装与升级指南

用户把首页安装指令交给你，即授权你在当前目标项目安装或安全升级 Spec Kit，并完成下面的验证。目标是让用户无需学习安装命令。安装后工作流面向 Codex；其他具备终端和文件能力的 Agent 也可以完成安装工作。

本指南使用最新正式 Release。源码与命令发生差异时，读取所选 tag 的实际源码和 `--help`，报告差异，不猜测参数。

## 1. 确认环境与目标

- 目标是用户当前打开的项目根目录，不是 Spec Kit 的源码目录；存在歧义时先确认目标。
- 支持环境：Windows、PowerShell 7（`pwsh`）、Python 3.11+、Git、uv。不要承诺 Linux/macOS 的完整运行兼容性。
- 检查 `pwsh --version`、`git --version`、`uv --version` 和可用 Python。用户目录中的工具可能尚未加入 PATH，先查已有安装。
- 缺少依赖时，使用该工具官方安装方式或现有包管理器，在当前用户权限内补齐；需要管理员权限或无法联网时，说明具体阻塞和最小操作。
- 记录 Git 状态、已有 `.specify`、`AGENTS.md`、`.agents` 和 `ai`。已有开发改动保留，不切分支、不清理、不 stash。
- `.specify/spec-kit.lock.yml` 或 `.specify/integrations/speckit.manifest.json` 存在时按升级处理。只有一个损坏或不完整的 `.specify` 目录时先检查，不能直接覆盖初始化。

## 2. 选择并安装正式版本

查询 `https://api.github.com/repos/liuminxin45/spec-kit/releases/latest`，记录 `tag_name` 和发布地址，确认不是 draft 或 prerelease。可用 GitHub CLI、HTTP 或 Agent 自带的网络工具。

如果无法查询 Release，不静默改用 main。先用可用的网络方式重试；仍不可用则报告阻塞，或按用户明确指定的 tag 安装。

在目标项目之外创建独立的临时源码目录，把选定 tag 克隆进去。以下为 PowerShell 示例，`$tag` 必须来自刚查询的 Release：

```powershell
$projectPath = (Get-Location).Path
$release = Invoke-RestMethod https://api.github.com/repos/liuminxin45/spec-kit/releases/latest
$tag = [string]$release.tag_name
if (-not $tag -or $release.draft -or $release.prerelease) { throw 'No stable release found' }
$sourcePath = Join-Path ([IO.Path]::GetTempPath()) ('spec-kit-' + [guid]::NewGuid().ToString('N'))
git clone --depth 1 --branch $tag https://github.com/liuminxin45/spec-kit.git $sourcePath
if ($LASTEXITCODE -ne 0) { throw 'Source checkout failed' }
pwsh -NoProfile -File "$sourcePath/scripts/powershell/install.ps1" -SkipProjectUpgrade
if ($LASTEXITCODE -ne 0) { throw 'CLI installation failed' }
specify --version
if ($LASTEXITCODE -ne 0) { throw 'CLI verification failed' }
```

`-SkipProjectUpgrade` 避免临时源码的父目录被误判为项目。后续使用明确的 `$projectPath` 处理目标项目。安装前核对同名 `specify` CLI 是否来自其他项目；若更换会影响其他用途，应先告知用户冲突并取得选择。

核对 `specify --version` 与所选 tag 的版本。不要把命令存在等同于版本正确。CLI 和模板随包安装，不需要另外下载官方 github/spec-kit 的同名 CLI。

## 3. 初始化或安全升级

### 首次安装

先检查所选版本的 `specify init --help`。在目标项目目录执行：

```powershell
Set-Location -LiteralPath $projectPath
specify init --here --no-git --ignore-agent-tools
```

- `--no-git` 保留现有 Git 设置，也避免为用户自动创建仓库。
- `--ignore-agent-tools` 兼容使用 Codex 桌面应用、没有独立 Codex CLI 的情况；不改变 Codex-only 集成。
- 在写入前备份可能受影响的已有文件。非空目录确认可以在完成冲突检查后由 Agent 应答；不为跳过提示而使用 `--force`。
- 保留用户的 `AGENTS.md` 内容、已有技能与项目知识。初始化会添加 Spec Kit 管理区域和资源；发生无法安全合并的冲突时说明具体文件，不覆盖自定义内容。

### 已有项目

先预览，再执行不带 `--force` 的升级：

```powershell
specify upgrade --project-dir $projectPath --source $sourcePath --dry-run --json
specify integration upgrade codex --project-dir $projectPath --dry-run --json
```

检查计划状态、阻塞、`preserved-customized` 与缺失项。预检通过后执行：

```powershell
specify upgrade --project-dir $projectPath --source $sourcePath
specify integration upgrade codex --project-dir $projectPath
```

每条命令检查退出码；失败就停止依赖步骤。保留 `.specify/workspace.yml`、repository map、项目知识、自定义受管文件和历史工作流快照。覆盖自定义受管文件需要用户对具体冲突的明确授权。不要执行尚未实现的 `specify self upgrade`。

## 4. 验证安装结果

检查生成的 `AGENTS.md` 管理区域、`.agents/skills/speckit-specify/SKILL.md`、`.agents/spec-kit/skills/`、`.specify/` 与 `ai/`。

从目标项目运行以下检查。每条命令检查退出码及 JSON 状态，不只看最后一行输出：

```powershell
pwsh -NoProfile -File "$projectPath/.specify/scripts/powershell/validate-generated-context.ps1" -RepoRoot $projectPath -Json
pwsh -NoProfile -File "$projectPath/.specify/scripts/powershell/validate-knowledge-index.ps1" -RepoRoot $projectPath -Json
pwsh -NoProfile -File "$projectPath/.specify/scripts/powershell/validate-context-budget.ps1" -RepoRoot $projectPath -Json
Set-Location -LiteralPath $projectPath
specify integration status --json
specify self check --project-dir $projectPath --json
```

前三项应为 `status: ok`。最后核对 CLI、项目资产和 Codex integration 版本一致且为本次选择的版本，无 outdated 或 missing 项。`self check` 的 `customized` 可以表示保留了用户定制，应列出差异及影响，不能改写成完全一致。版本查询等网络故障应单独披露，不冒充安装校验通过。

安装完成不代表项目产品测试或运行验收通过。不自动提交、推送、创建任务或发布项目；不自动挂载项目知识包。需要知识包时按用户选择参照 [Agent 使用手册](agent-guide.md) 和 [本地安装指南](local-install-and-knowledge-mount.md)。

## 5. 向用户交付

用用户的语言简洁报告：安装版本与 tag、目标路径、初始化或升级、检查结果、保留的定制及剩余阻塞。检查未通过时继续处理可修复问题，无法处理的给出具体原因。

建议重新打开目标项目中的 Codex 对话以加载新技能，然后给出可复制的第一条任务：

```text
$speckit-specify 描述你要实现的功能或修复的问题，完成后给出验证结果。
```

用户不需要先阅读完整手册。仅在下一项工作需要时加载 [Agent 使用手册](agent-guide.md) 中对应章节。
