#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH="" cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tool=""
repo_root="$(pwd)"
feature_dir=""
stage=""
delivery_profile=""
workflow_state=""
candidates_path=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tool) tool="$2"; shift 2 ;;
    --repo-root) repo_root="$2"; shift 2 ;;
    --feature-dir) feature_dir="$2"; shift 2 ;;
    --stage) stage="$2"; shift 2 ;;
    --delivery-profile) delivery_profile="$2"; shift 2 ;;
    --workflow-state) workflow_state="$2"; shift 2 ;;
    --candidates-path) candidates_path="$2"; shift 2 ;;
    --json) shift ;;
    *) shift ;;
  esac
done

json_escape() {
  python -c 'import json,sys; print(json.dumps(sys.stdin.read())[1:-1])'
}

emit() {
  local status="$1"
  local facts="$2"
  local blockers="$3"
  local unknowns="$4"
  local hints="$5"
  printf '{"tool":"%s","status":"%s","facts":%s,"blockers":%s,"unknowns":%s,"hints":%s}\n' \
    "$tool" "$status" "$facts" "$blockers" "$unknowns" "$hints"
}

changed_files() {
  git -C "$repo_root" status --porcelain=v1 -uall 2>/dev/null | sed 's#\\#/#g' | sed -E 's/^.. //; s/.* -> //'
}

case "$tool" in
  select-knowledge|validate-knowledge-index)
    python3 - "$tool" "$repo_root" "$stage" "$delivery_profile" "$script_dir" <<'PY'
import json
import re
import sys
from pathlib import Path

tool, repo_root, stage, delivery_profile, script_dir = sys.argv[1:]
repo = Path(repo_root)
script = Path(script_dir)

def result(status="ok", facts=None, blockers=None, unknowns=None, hints=None):
    print(json.dumps({
        "tool": tool,
        "status": status,
        "facts": facts or {},
        "blockers": blockers or [],
        "unknowns": unknowns or [],
        "hints": hints or [],
    }, ensure_ascii=False))

def knowledge_index_path():
    candidates = [
        repo / "ai" / "knowledge" / "index.yml",
        repo / "tools" / "spec-kit" / "templates" / "ai" / "knowledge" / "index.yml",
        script.parent.parent / "templates" / "ai" / "knowledge" / "index.yml",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None

def guide_root(index):
    if index.parent.name == "knowledge" and index.parent.parent.name == "ai":
        return index.parent.parent.parent
    return repo

def display_path(guide):
    guide = guide.replace("\\", "/")
    return guide if guide.startswith("ai/knowledge/") else f"ai/knowledge/{guide}"

def resolve_guide(index, guide):
    guide = guide.replace("\\", "/")
    if guide.startswith("ai/knowledge/"):
        return guide_root(index) / guide
    return index.parent / guide

def parse_entries(index):
    sections = {"workspace", "repositories", "domains", "build"}
    entries = []
    section = ""
    current = None
    for line in index.read_text(encoding="utf-8").splitlines():
        root = re.match(r"^([A-Za-z0-9_-]+):\s*$", line)
        if root:
            if current:
                entries.append(current)
                current = None
            section = root.group(1)
            continue
        entry = re.match(r"^\s{2}([A-Za-z0-9_-]+):\s*$", line)
        if section in sections and entry:
            if current:
                entries.append(current)
            current = {"category": section, "key": entry.group(1), "guide": "", "tags": []}
            continue
        if not current:
            continue
        guide = re.match(r"^\s{4}guide:\s*['\"]?(.+?)['\"]?\s*$", line)
        if guide:
            current["guide"] = guide.group(1).strip().strip('"').strip("'")
            continue
        tags = re.match(r"^\s{4}tags:\s*\[(.*?)\]\s*$", line)
        if tags:
            current["tags"] = [
                item.strip().strip('"').strip("'").lower()
                for item in tags.group(1).split(",")
                if item.strip()
            ]
    if current:
        entries.append(current)
    return entries

def max_selected(index):
    match = re.search(r"(?m)^\s*max_selected_guides:\s*(\d+)\s*$", index.read_text(encoding="utf-8"))
    return max(1, int(match.group(1))) if match else 3

def normalize(value):
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())

def add_terms(terms, value):
    if not value:
        return
    value = str(value).lower()
    terms.add(value)
    for piece in re.split(r"[^a-z0-9]+", value):
        if piece:
            terms.add(piece)

def routing_context():
    terms = set()
    affected = []
    risk_flags = []
    capability_tags = []
    for value in [stage, delivery_profile]:
        add_terms(terms, value)
    feature_json = repo / ".specify" / "feature.json"
    if feature_json.is_file():
        try:
            data = json.loads(feature_json.read_text(encoding="utf-8"))
            affected = [str(item) for item in data.get("affected_repositories") or []]
            risk_flags = [str(item) for item in data.get("risk_flags") or []]
            capability_tags = [str(item) for item in data.get("capability_tags") or []]
            summary = str(data.get("request_summary") or "")
            for value in affected + risk_flags + capability_tags + [summary]:
                add_terms(terms, value)
        except Exception:
            pass
    return {
        "terms": sorted(terms),
        "affected_repositories": affected,
        "risk_flags": risk_flags,
        "capability_tags": capability_tags,
        "feature_json": str(feature_json),
    }

def workspace_repos():
    workspace = repo / ".specify" / "workspace.yml"
    if not workspace.is_file():
        return []
    return [
        normalize(match.group(1).strip().strip('"').strip("'"))
        for match in re.finditer(r"(?m)^\s*-\s*name:\s*(.+?)\s*$", workspace.read_text(encoding="utf-8"))
    ]

index = knowledge_index_path()
if not index:
    result("blocked", blockers=["ai/knowledge/index.yml not found"])
    raise SystemExit(0)
entries = parse_entries(index)

if tool == "select-knowledge":
    routing = routing_context()
    terms = set(routing["terms"])
    affected = {normalize(value) for value in routing["affected_repositories"]}
    ranked = []
    for entry in entries:
        if not entry["guide"]:
            continue
        score = 0
        reasons = []
        matched_tags = []
        if normalize(entry["key"]) in affected:
            score += 8
            reasons.append("affected repository")
        for tag in entry["tags"]:
            if tag in terms:
                score += 3
                matched_tags.append(tag)
        if stage == "validation" and entry["key"] == "validation-matrix":
            score += 4
            reasons.append("validation stage")
        if stage == "plan" and entry["category"] == "workspace":
            score += 1
            reasons.append("planning context")
        if "cross" in terms or "cross-repo" in terms:
            if entry["key"] == "cross-repo-routing":
                score += 4
                reasons.append("cross-repo routing")
        if matched_tags:
            reasons.append("matched tags: " + ", ".join(sorted(set(matched_tags))))
        if score > 0:
            ranked.append({
                "score": score,
                "path": display_path(entry["guide"]),
                "category": entry["category"],
                "key": entry["key"],
                "reason": "; ".join(dict.fromkeys(reasons)),
                "matched_tags": sorted(set(matched_tags)),
            })
    selected = sorted(ranked, key=lambda item: (-item["score"], item["path"]))[:max_selected(index)]
    facts = {
        "index": str(index),
        "max_selected_guides": max_selected(index),
        "terms": sorted(terms),
        "affected_repositories": routing["affected_repositories"],
        "risk_flags": routing["risk_flags"],
        "capability_tags": routing["capability_tags"],
        "selected": [
            {key: item[key] for key in ["path", "category", "key", "reason", "matched_tags"]}
            for item in selected
        ],
    }
    hints = [] if selected else ["no knowledge guide matched deterministic routing fields; keep default context only"]
    result(facts=facts, hints=hints)
else:
    text = index.read_text(encoding="utf-8")
    blockers = []
    for phrase in ["repository_map_authority", "no_full_text_search_required", "max_selected_guides"]:
        if phrase not in text:
            blockers.append(f"knowledge index missing required phrase: {phrase}")
    missing = []
    offenders = []
    oversized = []
    unknown_repos = []
    repo_names = workspace_repos()
    forbidden_patterns = [
        r"[A-Za-z]:\\Internal\\",
        r"[A-Za-z]:\\Private\\",
        r"/Users/example/",
        r"/home/example/",
        r"AppData",
        r"private-user",
    ]
    root = guide_root(index)
    for entry in entries:
        if not entry["guide"]:
            missing.append(f"{entry['category']}.{entry['key']} has no guide")
            continue
        guide = resolve_guide(index, entry["guide"])
        if not guide.is_file():
            missing.append(display_path(entry["guide"]))
            continue
        guide_text = guide.read_text(encoding="utf-8", errors="replace")
        for pattern in forbidden_patterns:
            if re.search(pattern, guide_text):
                offenders.append(
                    f"{display_path(entry['guide'])} contains machine-specific path pattern: {pattern}"
                )
        line_count = len(guide_text.splitlines())
        if line_count > 220:
            oversized.append(f"{display_path(entry['guide'])} has {line_count} lines")
        if entry["category"] == "repositories" and repo_names and normalize(entry["key"]) not in repo_names:
            unknown_repos.append(entry["key"])
    if missing:
        blockers.append("missing knowledge guides: " + ", ".join(sorted(set(missing))))
    if offenders:
        blockers.append("machine-specific knowledge paths found: " + "; ".join(sorted(set(offenders))))
    if oversized:
        blockers.append("knowledge guides exceed 220 lines: " + "; ".join(sorted(set(oversized))))
    if unknown_repos:
        blockers.append("knowledge index references repositories missing from workspace.yml: " + ", ".join(sorted(set(unknown_repos))))
    result(
        status="blocked" if blockers else "ok",
        facts={
            "index": str(index),
            "guide_count": len([entry for entry in entries if entry["guide"]]),
            "missing_guides": sorted(set(missing)),
            "absolute_path_offenders": sorted(set(offenders)),
            "oversized_guides": sorted(set(oversized)),
            "unknown_repositories": sorted(set(unknown_repos)),
            "max_selected_guides": max_selected(index),
        },
        blockers=blockers,
    )
PY
    ;;
  validate-feature-artifacts)
    python - "$tool" "$repo_root" "$feature_dir" "$stage" "$delivery_profile" "$script_dir" <<'PY'
import json
import re
import sys
from pathlib import Path

tool, repo_root, feature_dir, stage, profile, script_dir = sys.argv[1:]
repo = Path(repo_root)
feature = Path(feature_dir)
script = Path(script_dir)

def manifest_path():
    candidates = [
        repo / ".specify" / "templates" / "layer-manifest.yml",
        repo / "tools" / "spec-kit" / "templates" / "layer-manifest.yml",
        repo / "templates" / "layer-manifest.yml",
        script.parent.parent / "templates" / "layer-manifest.yml",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None

def yaml_list(path, section, key):
    if not path or not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    in_key = False
    items = []
    for line in lines:
        if re.match(r"^\S.*:\s*$", line):
            in_section = line.rstrip().rstrip(":").strip() == section
            in_key = False
            continue
        if not in_section:
            continue
        match_key = re.match(r"^\s{2}([^:#]+):\s*$", line)
        if match_key:
            in_key = match_key.group(1).strip().strip('"') == key
            continue
        match_item = re.match(r"^\s{4}-\s+(.+?)\s*$", line)
        if in_key and match_item:
            items.append(match_item.group(1).strip().strip('"').strip("'"))
        elif in_key and re.match(r"^\s{0,2}\S", line):
            in_key = False
    return items

manifest = manifest_path()
def feature_routing():
    routing = {
        "profile": profile,
        "risk_level": "",
        "risk_flags": [],
        "feature_json": str(repo / ".specify" / "feature.json"),
    }
    feature_json = Path(routing["feature_json"])
    if not feature_json.is_file():
        return routing, [".specify/feature.json not found; using explicit DeliveryProfile only"], []
    try:
        data = json.loads(feature_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return routing, [], [".specify/feature.json is not valid JSON"]
    if (not routing["profile"] or routing["profile"] == "auto") and data.get("delivery_profile"):
        routing["profile"] = str(data.get("delivery_profile"))
    if data.get("risk_level"):
        routing["risk_level"] = str(data.get("risk_level"))
    flags = data.get("risk_flags") or []
    if isinstance(flags, list):
        routing["risk_flags"] = [str(flag) for flag in flags]
    return routing, [], []

def unique(items):
    output = []
    for item in items:
        if item and item not in output:
            output.append(item)
    return output

def stage_gate_required(routing):
    if stage != "implement":
        return []
    high_risk_flags = {
        "ui-parity",
        "host-embedded-ui",
        "cross-repo-validation",
        "public-api",
        "real-device",
    }
    has_high_risk_flag = any(flag in high_risk_flags for flag in routing["risk_flags"])
    if routing["profile"] == "full-sdd":
        return ["tasks.md", "analysis.md", "checklists/implementation-readiness.md"]
    if routing["risk_level"] in {"high", "blocked"} or has_high_risk_flag:
        return ["analysis.md", "checklists/implementation-readiness.md"]
    return []

stage_key = stage or "default"
profile_stage_key = f"{profile}-{stage}" if profile and stage else ""
required = []
for key in [profile_stage_key, stage_key]:
    if key:
        required = yaml_list(manifest, "artifact_sets", key)
        if required:
            break
required_source = "layer-manifest.yml" if required else "fallback"
if not required:
    if stage == "commit":
        required = [
            "spec.md",
            "plan.md",
            "validation.md",
            "acceptance.md",
            "workflow-state.json",
            "workflow-record.md",
            "improvement-candidates.md",
        ]
    elif stage == "implement":
        required = ["spec.md", "plan.md"]
    elif stage == "retrospective":
        required = ["acceptance.md", "workflow-record.md", "improvement-candidates.md"]
    else:
        required = ["spec.md"]
routing, routing_unknowns, routing_blockers = feature_routing()
stage_gate = stage_gate_required(routing)
required = unique(required + stage_gate)

blockers = list(routing_blockers)
missing = [name for name in required if not (feature / name).is_file()]
if missing:
    blockers.append("missing required artifacts: " + ", ".join(missing))

missing_sections = []
if manifest and feature.exists():
    for name in required:
        path = feature / name
        if not path.is_file():
            continue
        required_sections = yaml_list(manifest, "artifact_sections", name)
        if not required_sections:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        current_missing = [section for section in required_sections if section not in text]
        if current_missing:
            missing_sections.append({"file": name, "missing": current_missing})
            blockers.append(f"{name} missing required sections: " + ", ".join(current_missing))

todos = []
if feature.exists():
    for path in feature.glob("*.md"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"\b(TBD|TODO)\b", text, re.IGNORECASE):
            todos.append(path.name)
if todos:
    blockers.append("unfinished placeholders in: " + ", ".join(todos))

retrospective_gate = {
    "checked": False,
    "gate_status": "not_checked",
    "status": "",
    "workflow_record": "",
    "improvement_candidates": "",
}
if stage == "commit":
    retrospective_gate["checked"] = True
    retrospective_gate["gate_status"] = "ok"
    workflow_state_path = feature / "workflow-state.json"
    if not workflow_state_path.is_file():
        retrospective_gate["gate_status"] = "blocked"
        blockers.append("workflow-state.json missing; commit requires completed retrospective state")
    else:
        try:
            workflow_state = json.loads(workflow_state_path.read_text(encoding="utf-8"))
            retro = workflow_state.get("retrospective")
            if not isinstance(retro, dict):
                retrospective_gate["gate_status"] = "blocked"
                blockers.append("workflow-state.json missing retrospective state")
            else:
                retrospective_gate["status"] = str(retro.get("status", ""))
                retrospective_gate["workflow_record"] = str(retro.get("workflow_record", ""))
                retrospective_gate["improvement_candidates"] = str(retro.get("improvement_candidates", ""))
                if retrospective_gate["status"] != "completed":
                    retrospective_gate["gate_status"] = "blocked"
                    blockers.append("retrospective.status must be completed before commit")
                if not retrospective_gate["workflow_record"].strip():
                    retrospective_gate["gate_status"] = "blocked"
                    blockers.append("retrospective.workflow_record must reference workflow-record.md before commit")
                if not retrospective_gate["improvement_candidates"].strip():
                    retrospective_gate["gate_status"] = "blocked"
                    blockers.append("retrospective.improvement_candidates must reference improvement-candidates.md before commit")
        except json.JSONDecodeError:
            retrospective_gate["gate_status"] = "blocked"
            blockers.append("workflow-state.json is not valid JSON")

result = {
    "tool": tool,
    "status": "blocked" if blockers else "ok",
    "facts": {
        "feature_dir": feature_dir,
        "stage": stage,
        "delivery_profile": profile,
        "effective_delivery_profile": routing["profile"],
        "risk_level": routing["risk_level"],
        "risk_flags": routing["risk_flags"],
        "stage_gate_required": stage_gate,
        "feature_json": routing["feature_json"],
        "required": required,
        "required_source": required_source,
        "layer_manifest": str(manifest) if manifest else "",
        "missing_sections": missing_sections,
        "retrospective_gate": retrospective_gate,
    },
    "blockers": blockers,
    "unknowns": routing_unknowns,
    "hints": [],
}
print(json.dumps(result, ensure_ascii=False))
PY
    ;;
  validate-generated-context)
    python - "$tool" "$repo_root" <<'PY'
import json
import sys
from pathlib import Path

tool, repo_root = sys.argv[1:]
repo = Path(repo_root)
checks = [
    {
        "path": "AGENTS.md",
        "phrases": ["Project Path Categories", "source-to-runtime copy", "best-effort self-validation", "direct runtime replacement", "DesktopShell CDP validation", "ensure-desktop-shell-cdp-host", "stale/current-feature hint", "read the current plan only", "select-knowledge", "validate-knowledge-index"],
    },
    {
        "path": ".specify/memory/repository-map.md",
        "phrases": ["Project Path Categories", "<workspace-root>/ProductUIPlugin/<plugin-id>/", "CDP target inventory", "Do not write machine-specific absolute paths here"],
    },
    {
        "path": ".specify/templates/layer-manifest.yml",
        "phrases": ["stage_gates:", "read_strategies:", "Knowledge", "validate-knowledge-index", "checklists/implementation-readiness.md"],
    },
    {
        "path": "ai/workflows/task-routing.md",
        "phrases": ["tasks -> analyze -> checklist", "validate-generated-context", "validate-knowledge-index", "select-knowledge", "artifact_sections", "Stage Continuation", "inspect-desktop-shell-cdp-target", "ensure-desktop-shell-cdp-host", "do not apply stale feature risk flags"],
    },
    {
        "path": "ai/rules/ai-coding-rules.md",
        "phrases": ["Generated Context Drift", "analysis.md", "validate-generated-context", "validate-knowledge-index", "Stage Continuation Contract", "Host Frontend Delivery Chain", "ensure-desktop-shell-cdp-host", "Retrospective/留痕 is mandatory before commit"],
    },
    {
        "path": "tools/spec-kit/workflows/speckit/workflow.yml",
        "phrases": ["id: retrospective", "id: commit", "Require workflow-record.md and improvement-candidates.md before commit", "automatic_stage_continuation", "inspect-desktop-shell-cdp-target", "ensure-desktop-shell-cdp-host", "validate-knowledge-index", "current-feature state only"],
    },
    {
        "path": "tools/spec-kit/TEAM-README.md",
        "phrases": ["retrospective/留痕 -> commit", "commit 前强制 retrospective", "source edit -> frontend build -> direct runtime replacement -> real host CDP verification", "select-knowledge", "full-text/BM25 search"],
    },
]

blockers = []
context_file = "AGENTS.md"
canonical_context_file = "AGENTS.md"
init_options = repo / ".specify/init-options.json"
if init_options.exists():
    try:
        init_data = json.loads(init_options.read_text(encoding="utf-8"))
        stored_context_file = init_data.get("context_file")
        if isinstance(stored_context_file, str) and stored_context_file.strip():
            context_file = stored_context_file.strip()
        stored_canonical = init_data.get("canonical_context_file")
        if isinstance(stored_canonical, str) and stored_canonical.strip():
            canonical_context_file = stored_canonical.strip()
    except Exception:
        blockers.append("failed to parse .specify/init-options.json")
if context_file == "CLAUDE.md" and canonical_context_file == context_file:
    canonical_context_file = "AGENTS.md"
context_checks = []
if context_file == "CLAUDE.md":
    context_checks.append({
        "path": context_file,
        "phrases": ["@AGENTS.md", ".claude/skills", "/speckit-specify", "/speckit-plan", "/speckit-tasks", "/speckit-implement"],
    })
checks[0]["path"] = canonical_context_file
for candidate_skills_dir in [".agents/skills", ".claude/skills"]:
    if not (repo / candidate_skills_dir).exists():
        continue
    checks.extend([
        {
            "path": f"{candidate_skills_dir}/speckit-commit/SKILL.md",
            "phrases": ["validate-feature-artifacts", "Stage commit", "workflow-record.md", "improvement-candidates.md", "retrospective.status"],
        },
        {
            "path": f"{candidate_skills_dir}/speckit-implement/SKILL.md",
            "phrases": ["ensure-desktop-shell-cdp-host", "CDP host recovery ladder", "manual acceptance"],
        },
        {
            "path": f"{candidate_skills_dir}/speckit-retrospective/SKILL.md",
            "phrases": ["Existing Constraint Audit", "AI workflow self-check", "Team knowledge candidates", "retrospective.status"],
        },
        {
            "path": f"{candidate_skills_dir}/speckit-tasks/SKILL.md",
            "phrases": ["Run mandatory", "speckit.retrospective", "after quick acceptance and before", "optional test-hardening, retrospective/留痕"],
        },
    ])
checks = context_checks + checks
workflow_path = repo / "tools/spec-kit/workflows/speckit/workflow.yml"
if not workflow_path.is_file() and (repo / ".specify/workflows/speckit/workflow.yml").is_file():
    for check in checks:
        if check["path"] == "tools/spec-kit/workflows/speckit/workflow.yml":
            check["path"] = ".specify/workflows/speckit/workflow.yml"
for check in checks:
    if check["path"] == "tools/spec-kit/TEAM-README.md":
        check["optional"] = True
details = []
for check in checks:
    path = repo / check["path"]
    if not path.is_file():
        details.append({"path": check["path"], "exists": False, "missing_phrases": check["phrases"]})
        if not check.get("optional"):
            blockers.append(f"generated context missing: {check['path']}")
        continue
    text = path.read_text(encoding="utf-8", errors="replace")
    missing = [phrase for phrase in check["phrases"] if phrase not in text]
    details.append({"path": check["path"], "exists": True, "missing_phrases": missing})
    if missing:
        blockers.append(f"{check['path']} missing required generated-context phrases: {', '.join(missing)}")

print(json.dumps({
    "tool": tool,
    "status": "blocked" if blockers else "ok",
    "facts": {"repo_root": repo_root, "checked": details},
    "blockers": blockers,
    "unknowns": [],
    "hints": [],
}, ensure_ascii=False))
PY
    ;;
  inspect-commit-scope|inspect-source-artifact-consistency|suggest-validation|validate-fact-layer-gate|parse-promotion-candidates)
    python - "$tool" "$repo_root" "$workflow_state" "$candidates_path" "$feature_dir" <<'PY'
import json, os, sys
from pathlib import Path
tool, repo, workflow_state, candidates_path, feature_dir = sys.argv[1:]
result = {"tool": tool, "status": "ok", "facts": {"repo_root": repo}, "blockers": [], "unknowns": [], "hints": []}
if tool == "suggest-validation":
    hints = []
    package_path = Path(repo) / "package.json"
    if package_path.exists():
        try:
            package = json.loads(package_path.read_text(encoding="utf-8"))
            scripts = package.get("scripts") or {}
            if "test" in scripts:
                hints.append({"command": "npm test", "confidence": "exact", "source": "package.json scripts.test"})
            if "build" in scripts:
                hints.append({"command": "npm run build", "confidence": "exact", "source": "package.json scripts.build"})
            if "lint" in scripts:
                hints.append({"command": "npm run lint", "confidence": "exact", "source": "package.json scripts.lint"})
        except Exception:
            result["unknowns"].append("package.json could not be parsed")
    if (Path(repo) / "pytest.ini").exists() or (Path(repo) / "conftest.py").exists() or (Path(repo) / "pyproject.toml").exists():
        hints.append({"command": "pytest", "confidence": "likely", "source": "pytest marker"})
    if (Path(repo) / "CMakeLists.txt").exists():
        hints.append({"command": "cmake --build <build-dir>", "confidence": "likely", "source": "CMakeLists.txt"})
    result["hints"] = hints
    result["facts"]["candidate_count"] = len(hints)
    result["facts"]["validation_artifacts"] = ["validation.md", "acceptance.md"]
    result["facts"]["optional_evidence_artifacts"] = ["evidence.md", "fact-pack.md"]
    result["facts"]["validation_template"] = "ai/templates/validation-template.md"
    result["facts"]["evidence_template"] = "ai/templates/evidence-template.md"
    result["facts"]["evidence_required"] = "complex_or_runtime_or_tool_heavy"
    if feature_dir:
        result["facts"]["feature_dir"] = feature_dir
        result["facts"]["validation_path"] = str(Path(feature_dir) / "validation.md")
        result["facts"]["acceptance_path"] = str(Path(feature_dir) / "acceptance.md")
        result["facts"]["evidence_path"] = str(Path(feature_dir) / "evidence.md")
    if not hints:
        result["unknowns"].append("no validation command candidates discovered from package.json, pytest, or CMake markers")
if tool == "validate-fact-layer-gate" and not os.path.exists(workflow_state):
    result["status"] = "blocked"
    result["blockers"].append("missing workflow-state.json; LLM must create structured state before this gate")
if tool == "parse-promotion-candidates":
    counts = {"approved": 0, "pending": 0, "rejected": 0}
    if os.path.exists(candidates_path):
        text = open(candidates_path, encoding="utf-8").read()
        for key in counts:
            counts[key] = text.count(f"人工审核结论: {key}")
        result["facts"]["counts"] = counts
    else:
        result["status"] = "blocked"
        result["blockers"].append("missing improvement-candidates.md")
        result["facts"]["counts"] = counts
print(json.dumps(result, ensure_ascii=False))
PY
    ;;
  *)
    emit "ok" "{\"repo_root\":\"$repo_root\"}" "[]" "[]" "[\"hard facts collected only; LLM owns semantic routing, risk, and sufficiency decisions\"]"
    ;;
esac
