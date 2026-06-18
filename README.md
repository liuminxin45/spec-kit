# Spec Kit

Spec Kit 是一个面向 Codex 的 AI Coding 工作流脚手架。它的目标不是把所有
项目知识塞进默认上下文，而是提供一套小核心：初始化模板、阶段技能、验证
脚本、知识索引、知识包挂载和 AI 辅助知识包生成能力。具体项目、团队和仓库
知识应放在项目本地 `ai/knowledge/`，或打成可分发的 capability pack。

## 核心理念

- **默认上下文要小**：先读稳定入口和仓库映射，再按任务只加载需要的知识、
  gate、skill 和 feature artifacts。
- **开源核心与知识包分离**：Spec Kit 只承载通用工作流和工具框架，项目私有
  事实通过知识包挂载。
- **知识按需加载**：通过 `ai/knowledge/index.yml` 和 `select-knowledge`
  选择少量 guide，避免每次任务全量读取知识库。
- **脚本给事实，AI 做判断**：脚本输出 `facts`、`blockers`、`unknowns`、
  `hints`；语义路由、根因判断、验证充分性和取舍仍由 LLM 负责。
- **知识可生成、可挂载、可更新、可卸载、可重新打包**：项目使用过程中沉淀
  的知识可以 repack 成独立包继续分发。

## 快速开始

安装本仓库版本的 CLI：

```powershell
pwsh -NoProfile -File .\scripts\powershell\install.ps1
```

在目标项目中初始化 Spec Kit：

```powershell
specify init --here
```

初始化后，从 Codex 暴露的入口 skill 开始工作流：

```text
$speckit-specify
```

项目中会生成这些核心目录和文件：

```text
AGENTS.md
.agents/
.specify/
ai/
specs/
```

## 使用已有知识包开局

如果你已经有项目、团队或仓库知识包，可以初始化时直接挂载：

```powershell
specify init --here --knowledge-pack <pack-dir>
```

这会安装 pack，物化到 `ai/knowledge/`，写入
`.specify/knowledge/lock.yml`，并验证当前知识索引。由于知识来自已有
pack，这条路径不会生成 AI review packet；也就是 it does not generate an AI review packet because the knowledge already came from an external pack.

如果这个 pack 还应该定义目标项目的 workspace profile 和 repository map：

```powershell
specify init --here --knowledge-pack <pack-dir> --knowledge-pack-apply-profiles
```

只有当 pack 明确用于定义目标项目结构时才使用
`--knowledge-pack-apply-profiles`。不加这个参数时，Spec Kit 会保留初始化时
生成的 `.specify/workspace.yml` 和 `.specify/memory/repository-map.md`。

## 没有知识包时开局

先初始化项目：

```powershell
specify init --here
```

再生成一版低置信度的草稿知识库：

```powershell
pwsh -NoProfile -File .specify/scripts/powershell/bootstrap-knowledge.ps1 -RepoRoot . -Json
```

草稿模式会生成：

```text
.specify/knowledge-bootstrap/draft/ai/knowledge/
.specify/knowledge-bootstrap/ai-review/
```

`ai-review` 目录里包含有界源码读取计划和 claim ledger。AI 应先按这个计划
做定向源码读取，补充 source refs、未知项和分层知识，再提升置信度或导出
可复用 pack。

## 用 AI 生成项目知识包

对一个新项目或任意项目，推荐使用 AI-assisted generator，而不是直接导出
机械草稿：

```powershell
pwsh -NoProfile -File .specify/scripts/powershell/generate-knowledge-pack.ps1 -RepoRoot . -PackId <id> -IncludeProfiles -Json
```

该命令会创建 AI synthesis workspace：

```text
.specify/knowledge-pack-generation/ai-synthesis/ai/knowledge/
```

同时生成：

```text
.specify/knowledge-pack-generation/ai-pack-generator/generation-contract.json
.specify/knowledge-pack-generation/ai-pack-generator/source-read-queue.md
.specify/knowledge-pack-generation/quality/
.specify/knowledge-pack-generation/equivalence/
.specify/knowledge-pack-generation/pack/<id>/
```

脚本负责确定性事实采集、质量报告、等效性检查和 pack 机械流程；AI 负责：

- 按 source-read queue 做定向源码读取。
- 将机械库存整理成分层知识。
- 保留每条长期事实的 `source_refs`。
- 明确未知项，不靠猜测补事实。
- 删除噪声和重复内容。

质量闭环会写出：

```text
.specify/knowledge-pack-generation/quality/source-coverage-ledger.json
.specify/knowledge-pack-generation/quality/claim-verification-report.json
.specify/knowledge-pack-generation/quality/synthesis-quality-summary.md
.specify/knowledge-pack-generation/equivalence/equivalence-summary.md
```

AI 完成 synthesis 后，用 reviewed workspace 重新导出：

```powershell
pwsh -NoProfile -File .specify/scripts/powershell/generate-knowledge-pack.ps1 -RepoRoot . -PackId <id> -ReviewedKnowledgeDir .specify/knowledge-pack-generation/ai-synthesis/ai/knowledge -IncludeProfiles -Json
```

传入 `-ReviewedKnowledgeDir` 后，generator 会强制执行质量分和 pack 等效性
门禁，只有通过后才把 pack 视为可挂载。

## Capability Pack 边界

开源核心只应包含框架资产：模板、validators、selectors、workflow scripts
和通用 starter knowledge。项目事实、团队规则、领域约束、工具策略和定制
技能应该进入 workspace-local `ai/knowledge/` 或 portable capability pack。
Project-specific facts belong in workspace-local `ai/knowledge/` or portable
capability packs.

一个 capability pack 可以包含：

```text
ai/knowledge/          分层项目知识
skills/                命名空间化 Codex skills，按需加载
tools/                 工具策略和 MCP/tool 使用说明
scripts/               返回 facts/blockers/unknowns/hints 的显式脚本
commands/              pack 专属命令提示
prompts/               可复用 prompt 模板
resources/             大文档、示例、图、生成地图
profiles/              workspace.yml 和 repository-map.md
evaluation/            路由 canary 和语义评估输入
capabilities/index.yml 渐进式加载注册表
```

Pack 安装或 compose 时不会自动执行 pack scripts。应用 pack 后，行为层会发布
到带命名空间的 workspace-local 路径，例如：

```text
.agents/spec-kit/skills/<pack-id>__<skill>
ai/tools/<pack-id>/
.specify/scripts/packs/<pack-id>/
```

## 知识包生命周期

常用命令：

```powershell
pwsh -NoProfile -File .specify/scripts/powershell/generate-knowledge-pack.ps1 -RepoRoot . -PackId <id> -IncludeProfiles -Json
pwsh -NoProfile -File .specify/scripts/powershell/evaluate-knowledge-pack-synthesis.ps1 -RepoRoot . -KnowledgeDir .specify/knowledge-pack-generation/ai-synthesis/ai/knowledge -MinimumScore 70 -FailBelowMinimum -Json
pwsh -NoProfile -File .specify/scripts/powershell/bootstrap-knowledge.ps1 -RepoRoot . -PackPath <pack-dir> -Force -Json
pwsh -NoProfile -File .specify/scripts/powershell/update-knowledge-pack.ps1 -RepoRoot . -PackPath <pack-dir> -Json
pwsh -NoProfile -File .specify/scripts/powershell/uninstall-knowledge-pack.ps1 -RepoRoot . -PackId <id> -Json
pwsh -NoProfile -File .specify/scripts/powershell/select-capability.ps1 -RepoRoot . -Layer skills -Json
pwsh -NoProfile -File .specify/scripts/powershell/export-knowledge-pack.ps1 -SourceKnowledgeDir ai/knowledge -PackId <id> -OutputDir <pack-dir> -Force -Json
pwsh -NoProfile -File .specify/scripts/powershell/repack-knowledge-pack.ps1 -RepoRoot . -PackId <id> -Mode full-snapshot -IncludeProfiles -Force -Json
pwsh -NoProfile -File .specify/scripts/powershell/validate-knowledge-pack.ps1 -PackRoot <pack-dir> -Json
pwsh -NoProfile -File .specify/scripts/powershell/compare-knowledge-pack-equivalence.ps1 -SourceKnowledgeDir ai/knowledge -PackRoot <pack-dir> -Json
```

生命周期语义：

- **挂载**：`bootstrap-knowledge.ps1 -PackPath` 或 `apply-knowledge-pack.ps1`
  安装 pack 并物化到 `ai/knowledge/`。
- **更新**：`update-knowledge-pack.ps1` 替换同 id 的已安装 pack，清理旧的
  命名空间发布层，然后重新 compose 当前 active pack set。
- **卸载**：`uninstall-knowledge-pack.ps1` 删除已安装 pack 和对应命名空间
  发布层，再重新 compose 剩余 pack 或恢复 base knowledge snapshot。
- **重新打包**：`repack-knowledge-pack.ps1` 可以把当前已经挂载并被用户完善
  的知识层重新打成 pack，便于继续分发。

## 初始化脚本

如果不想先全局安装 CLI，也可以从本仓库根目录使用包装脚本：

```powershell
pwsh -NoProfile -File .\scripts\powershell\init.ps1 -ProjectPath <project-dir> -SpecKitSourcePath .
```

常用选项：

- `-SkipInstall`：复用当前已经安装的 `specify`。
- `-NoForce`：不强制覆盖已管理的共享资产。
- `-EditableInstall`：以 editable 模式安装当前源码。
- `-ConfigureMcpAgent`：显式写入 Codex MCP 配置。
- `-SkipMcpAgentConfig`：即使传入 MCP 相关参数，也跳过 MCP 配置。

默认初始化不写 Codex MCP 配置；需要 Chrome DevTools MCP 时再显式开启。

## 验证

修改生成上下文、知识索引、模板、脚本或 pack 后，至少运行：

```powershell
pwsh -NoProfile -File .specify/scripts/powershell/automation-common.ps1 -Tool validate-generated-context -RepoRoot . -Json
pwsh -NoProfile -File .specify/scripts/powershell/automation-common.ps1 -Tool validate-knowledge-index -RepoRoot . -Json
pwsh -NoProfile -File .specify/scripts/powershell/automation-common.ps1 -Tool validate-context-budget -RepoRoot . -Json
```

开发 Spec Kit 本身时，可以运行自动化脚本测试：

```powershell
python -m pytest tests/test_spec_automation_scripts.py -q
```

脚本结果里的 `facts` 是硬事实，`blockers` 是必须处理的问题，`unknowns`
是仍需 AI 或人工判断的缺口，`hints` 是下一步建议。不要把脚本通过等同于
语义正确，AI 仍需要基于 source evidence 判断。

## 目录结构

```text
src/specify_cli/        CLI 源码
scripts/powershell/     初始化、验证、知识包和工作流脚本
templates/              初始化模板、命令模板、内置 skills 和 AI 资产
workflows/              bundled workflow 定义
checklist-rules/        checklist 规则包
tests/                  回归测试
TEAM-README.md          团队内部流程说明，默认不进入任务上下文
```

## 许可证

本仓库使用 MIT License。
