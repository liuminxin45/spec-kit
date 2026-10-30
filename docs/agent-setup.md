# Spec Kit：给 Agent 的安装与升级指南

用户把首页安装指令交给你，即授权你在当前目标项目安装或安全升级 Spec Kit，并完成下面的验证。目标是让用户无需学习安装命令。安装后工作流面向 Codex；其他具备终端和文件能力的 Agent 也可以完成安装工作。

本指南默认使用最新正式 Release；用户明确指定 tag 时使用该正式 Release。源码与命令发生差异时，读取所选 tag 的实际源码和 `--help`，报告差异，不猜测参数。

**首次安装统一使用 2.0 `codex-skill` 模式，任务入口为 `$speckit`。**
CLI 省略 `--mode` 仍默认 legacy；安装新版 CLI 不等于项目已启用新模式。
已有项目先识别模式，再安全升级，不自动迁移、不混装两套入口。
2.0 使用与知识包操作见 [Codex Skill 模式](codex-skill-mode.md)。

## 1. 确认环境与目标

- 目标是用户当前打开的项目根目录，不是 Spec Kit 的源码目录；存在歧义时先确认目标。
- 支持环境：Windows、PowerShell 7（`pwsh`）、Python 3.11+、Git、uv。不要承诺 Linux/macOS 的完整运行兼容性。
- 检查 `pwsh --version`、`git --version`、`uv --version` 和可用 Python。用户目录中的工具可能尚未加入 PATH，先查已有安装。
- 缺少依赖时，使用该工具官方安装方式或现有包管理器，在当前用户权限内补齐；需要管理员权限或无法联网时，说明具体阻塞和最小操作。
- 记录 Git 状态、已有 `.specify`、`AGENTS.md`、`.agents` 和 `ai`。已有开发改动保留，不切分支、不清理、不 stash。
- 写入前识别模式：`.specify/config.yml` 中 `mode: codex-skill`、`.specify/packs.lock.json` 与 `.agents/skills/speckit/SKILL.md` 属于 2.0；`.specify/spec-kit.lock.yml`、`.specify/integrations/speckit.manifest.json` 或旧版 AGENTS 管理区域属于 legacy。
- 标记缺失、损坏、互相冲突或发现两套入口时先检查并报告，不猜模式、不覆盖初始化。只有普通业务文件、没有 Spec Kit 资产的项目才按首次安装处理。

## 2. 选择并安装正式版本

查询 `https://api.github.com/repos/liuminxin45/spec-kit/releases/latest`，记录 `tag_name` 和发布地址，确认不是 draft 或 prerelease。可用 GitHub CLI、HTTP 或 Agent 自带的网络工具。

用户指定 tag 时，将下面两处 `releases/latest` 替换为 `releases/tags/<指定tag>`，
并核对返回的 `tag_name` 与指定值一致，仍须排除 draft/prerelease。

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

### 首次安装：2.0 总 Skill

先检查所选版本的 `specify init --help`，确认支持 `--mode codex-skill`。
若所选正式版不支持，报告版本阻塞，不静默退回 legacy，也不把 main 冒充正式版。
在目标项目目录执行，每条命令检查退出码，失败就停止后续步骤：

```powershell
Set-Location -LiteralPath $projectPath
specify init --here --mode codex-skill --no-git --json
```

初始化添加总 Skill、短 AGENTS 管理区域、配置、锁文件和通用包，不生成旧版
`ai/` 模板、阶段 skills 或产品源码。`--no-git` 明确保留现有 Git 设置；
该模式不要求独立 Codex CLI，无需 legacy 的 `--ignore-agent-tools`。
写入前备份受影响文件，保留用户 AGENTS 区域外的规则、技能与项目知识。
不使用 `--force` 绕过冲突；非空业务目录不等于已经安装过 Spec Kit。

### 已有 2.0 项目：保留模式升级

安装并核对目标 CLI 版本后，先预览，再执行不带 `--force` 的升级：

```powershell
specify upgrade --project-dir $projectPath --dry-run --json
specify upgrade --project-dir $projectPath --json
```

逐条检查退出码和 JSON 状态，预览有阻塞时不执行写入。该分支使用已安装 CLI
的总 Skill 与内置包，不接受 legacy 的 `--source`，也不运行
`specify integration upgrade codex`。保留自定义受管文件并报告冲突，
不删除用户知识、任务历史或现有技能。

已有 legacy 项目转到[兼容与迁移](#6-legacy-兼容与迁移)，不运行上面的初始化命令。

## 4. 验证 2.0 安装结果

核对 `.specify/config.yml` 的 `mode: codex-skill`、`.specify/packs.lock.json`、
`.agents/skills/speckit/SKILL.md` 与 `AGENTS.md` 管理区域。从目标目录执行：

```powershell
Set-Location -LiteralPath $projectPath
specify pack doctor --json
specify context --json
```

每条命令同时检查退出码与 JSON。首次安装应均为 `status: ok`；doctor 的
`mode` 应为 `codex-skill`，`runtime_version` 与所选 CLI 版本一致；context
应返回内置 workflow/knowledge 候选。`warning`、`blocked`、定制文件或未完成
事务必须列出并处理，不能仅凭退出码 0 宣称通过。重新确认没有混入旧入口。
不要用 legacy 的 integration/self check 或旧上下文校验脚本代替这些检查。

安装完成不代表项目产品测试或运行验收通过。不自动提交、推送、创建任务或发布
项目；不自动挂载项目知识包。需要项目知识时按用户选择参照
[2.0 使用说明](codex-skill-mode.md)。

## 5. 向用户交付

用用户的语言简洁报告：版本与 tag、目标路径、实际模式、初始化或升级、
检查结果、保留的定制及剩余阻塞。检查未通过时继续处理可修复问题，无法处理的
给出具体原因。建议重新打开目标项目中的 Codex 对话以加载技能。

2.0 `codex-skill` 项目给出可复制的第一条任务：

```text
$speckit 修复登录失败时提示不明确的问题，先核实原因，完成后给出验证结果。
```

保留 legacy 的项目只给出下节对应入口，并明确尚未迁移到 2.0 新模式。
用户不需要先阅读完整手册，按实际模式加载对应章节。

## 6. legacy 兼容与迁移

本节仅供已有 legacy 项目维护或用户明确要求兼容模式时使用，不作为新用户安装路径。
CLI 默认值仍为 legacy；两套入口不是别名，不能混装，也不要为清理旧入口而删除
活动项目的 AGENTS、skills、配置、知识或历史状态。

### 原模式安全升级

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

### legacy 验证

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

验证通过后，重新打开 Codex 对话，legacy 项目继续使用：

```text
$speckit-specify 修复登录失败时提示不明确的问题，先核实原因，完成后给出验证结果。
```

仅当用户明确要求新建 legacy 项目时，在完成第 1、2 节检查后执行：

```powershell
Set-Location -LiteralPath $projectPath
specify init --here --mode legacy --no-git --ignore-agent-tools
```

逐条检查退出码，按本节 legacy 检查验收。写入前备份，非空目录完成冲突检查后
才可应答确认，不使用 `--force` 覆盖用户内容。

### 计划迁移到单一入口

在旧项目目录先做只读预览：

```powershell
Set-Location -LiteralPath $projectPath
specify pack migration-plan --json
```

该命令只输出计划，不执行迁移。先在隔离目录试装新模式、导入并核验旧知识，
再由用户明确决定如何迁移项目规则和处理旧 AGENTS/skills。切换完成后只保留
与新模式匹配的入口；当前版本不自动改写活动 legacy 项目。
详见 [2.0 模式与知识导入](codex-skill-mode.md) 和
[legacy 使用手册](agent-guide.md)。
