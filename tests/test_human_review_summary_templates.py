from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def read_template(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_page_templates_keep_ai_sections_and_add_human_review_summary():
    expected_sections = {
        "templates/spec-template.md": [
            "## 能力概览",
            "## 能力场景 *(必填)*",
            "## 功能需求 *(必填)*",
            "## 验证预期",
        ],
        "templates/plan-template.md": [
            "## 概览",
            "## 技术上下文",
            "## 宪章检查",
            "## 验证计划",
        ],
        "templates/tasks-template.md": [
            "## 格式: `[ID] [P?] [Scenario?] Description`",
            "## Phase 1: 上下文与边界",
            "## Phase N: 横切事项与交付",
            "## 依赖说明",
        ],
        "templates/checklist-template.md": [
            "## 生成策略",
            "## 需求质量",
            "## 工程边界",
            "## 验证",
        ],
    }

    for path, existing_sections in expected_sections.items():
        text = read_template(path)

        assert "## 人类审核摘要" in text
        assert "不得替代或删减后续 AI/流程读取区" in text
        assert "必需人工决策" in text
        for section in existing_sections:
            assert section in text


def test_command_templates_require_a_non_destructive_human_review_summary():
    command_paths = [
        "templates/commands/specify.md",
        "templates/commands/plan.md",
        "templates/commands/tasks.md",
        "templates/commands/checklist.md",
    ]

    for path in command_paths:
        text = read_template(path)

        assert "人类审核摘要" in text
        assert "不得替代或删减" in text
        assert "AI" in text


def test_human_review_summaries_separate_navigation_from_required_decisions():
    for path in [
        "templates/spec-template.md",
        "templates/intake-template.md",
        "templates/plan-template.md",
        "templates/tasks-template.md",
    ]:
        text = read_template(path)
        assert "必需人工决策" in text

    for path in [
        "templates/commands/specify.md",
        "templates/commands/plan.md",
        "templates/commands/tasks.md",
        "templates/commands/analyze.md",
        "templates/commands/checklist.md",
    ]:
        text = read_template(path)
        assert "Do not ask" in text or "Do not ask humans" in text
        assert "root cause correctness" in text
        assert "test sufficiency" in text
