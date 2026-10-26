# Spec Kit

**让 Codex 把需求做成有验证依据的交付。**

Spec-driven AI coding for Codex — from intent to verified delivery.

[English](README.en.md) · [一句话安装](#一句话安装) · [使用文档](docs/README.md) · [最新版本](https://github.com/liuminxin45/spec-kit/releases/latest)

[![Release](https://img.shields.io/github/v/release/liuminxin45/spec-kit)](https://github.com/liuminxin45/spec-kit/releases/latest)
[![Stars](https://img.shields.io/github/stars/liuminxin45/spec-kit?style=flat)](https://github.com/liuminxin45/spec-kit/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

写出代码只是开发的一部分。Spec Kit 为 Codex 加上需求澄清、按风险选择的工作流、可复用的项目知识和交付前验证，让你更容易判断：**做对了吗，可以交付了吗？**

## 为什么用它

- **小改动轻装上阵**：简单修复用精简计划，复杂变更再展开规格、任务和验证门禁。
- **项目知识按需加载**：把仓库结构、约束和经验整理成独立知识包，减少反复解释。
- **验收有据可查**：让 AI 提供测试、构建、日志或界面检查的证据，标明未验证的部分。
- **你掌握交付决定**：AI 先自检，再由你验收；提交、集成和推送按明确授权执行。

```text
描述需求 → 选择合适的流程 → 实现 → 收集验证证据 → 人工验收
```

适合想把 AI 编程从“改完了”推进到“可验收”的个人开发者和团队。

## 一句话安装

在**目标项目目录**打开你的 Agent，复制下面这一句：

```text
请读取 https://raw.githubusercontent.com/liuminxin45/spec-kit/main/docs/agent-setup.md，按指南在当前项目安装或安全升级 Spec Kit，完成自检并告诉我如何开始。
```

具备终端和文件访问能力的 Agent 可以按指南完成安装；安装后的工作流面向 **Codex**。当前支持的使用环境是 **Windows + PowerShell 7**，需要 Python 3.11+、Git 和 uv；指南会先检查环境，并保留已有项目配置。

## 装好后怎么用

在 Codex 中调用入口 skill，并说清你要做的事：

```text
$speckit-specify 修复登录失败时提示不明确的问题，先核实原因，完成后给出验证结果。
```

也可以用于新功能、重构、迁移或只做验证。AI 会根据风险选择流程，你不用先学会整套命令。

## 能验证到什么程度

测试、构建、日志和运行时检查可以成为交付依据。Electron、Chromium、WebView 等可连接 CDP 的界面还可检查 DOM、网络、样式和截图。原生界面、真实设备和外部服务需要相应证据；缺证据时应明确标记阻塞或未验证。

## 深入使用

| 想做什么 | 文档 |
| --- | --- |
| 让 Agent 安装、升级并自检 | [AI 安装指南](docs/agent-setup.md) |
| 查命令、流程、知识包与排障 | [Agent 使用手册](docs/agent-guide.md) |
| 分发本地安装包和知识包 | [本地安装与知识包挂载](docs/local-install-and-knowledge-mount.md) |
| 查更多资料或参与改进 | [文档目录](docs/README.md) |

如果它对你有用，欢迎点一个 **Star**，让更多开发者发现它。遇到问题或有改进想法，欢迎[提交 Issue](https://github.com/liuminxin45/spec-kit/issues) 或 PR；反馈时附上版本、预期行为和复现步骤会很有帮助。

## 来源与许可

本项目基于 [github/spec-kit](https://github.com/github/spec-kit) 扩展，面向 Codex 的工程交付场景独立演进。**本仓库不是 GitHub 官方项目。** 遵循 [MIT License](LICENSE)。
