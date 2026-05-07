"""Skill management tools — let the agent list, view, create, and delete skills.

Skills are stored as `workspace/skills/<name>/SKILL.md` with YAML frontmatter
(name, description) and optional category subdirectories.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tools import _workspace_path

SKILLS_TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "skills_list",
        "description": "List all available skills with their names and descriptions. "
        "Skills are reusable procedures stored in workspace/skills/. "
        "Use this first to discover what skills are available.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Optional category filter to narrow results "
                    "(e.g., 'devops', 'data-science').",
                }
            },
        },
    }
}

SKILL_VIEW_TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "skill_view",
        "description": "Load a skill's full content (SKILL.md). Use this after "
        "skills_list to get the complete skill instructions. Skills are "
        "markdown files stored in workspace/skills/<name>/SKILL.md.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The skill name (directory name, e.g., 'web-research').",
                }
            },
            "required": ["name"],
        },
    }
}

SKILL_MANAGE_TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "skill_manage",
        "description": "Create, update, or delete a skill. Skills are stored as "
        "workspace/skills/<name>/SKILL.md with YAML frontmatter "
        "(name, description). Actions: create (new skill), edit (rewrite "
        "full content), delete (remove skill directory). After completing "
        "a complex task, offer to save the procedure as a skill.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "edit", "delete"],
                    "description": "create: make a new skill. edit: replace content. "
                    "delete: remove the skill and its directory.",
                },
                "name": {
                    "type": "string",
                    "description": "Skill name (lowercase, hyphens, underscores).",
                },
                "content": {
                    "type": "string",
                    "description": "Full SKILL.md content with YAML frontmatter. "
                    "Required for create and edit actions.",
                },
                "category": {
                    "type": "string",
                    "description": "Optional subdirectory for grouping "
                    "(e.g., 'devops', 'data-science').",
                },
            },
            "required": ["action", "name"],
        },
    }
}


def _get_workspace() -> Path | None:
    """Get the workspace path, or None if not configured."""
    if _workspace_path is None:
        return None
    return Path(_workspace_path)


async def _exec_skills_list(args: dict) -> str:
    """List all available skills, optionally filtered by category."""
    workspace = _get_workspace()
    if workspace is None:
        return "[error: workspace not configured]"
    return _list_skills(workspace, args.get("category") or "")


async def _exec_skill_view(args: dict) -> str:
    """View the full content of a specific skill."""
    workspace = _get_workspace()
    if workspace is None:
        return "[error: workspace not configured]"
    name = (args.get("name") or "").strip()
    if not name:
        return "[error: 'name' is required]"
    return _view_skill(workspace, name)


async def _exec_skill_manage(args: dict) -> str:
    """Create, edit, or delete a skill."""
    workspace = _get_workspace()
    if workspace is None:
        return "[error: workspace not configured]"
    return _manage_skill(workspace, args)


def _list_skills(workspace: Path, category_filter: str) -> str:
    """List skills in the workspace skills directory."""
    skills_dir = workspace / "skills"
    if not skills_dir.is_dir():
        return "[info] No skills directory found."

    category_filter = category_filter.strip().lower()

    result_lines: list[str] = []

    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_dir():
            continue

        if _is_category_dir(entry):
            if category_filter and entry.name.lower() != category_filter:
                continue
            for sub in sorted(entry.iterdir()):
                if not sub.is_dir():
                    continue
                name, description = _load_skill_meta(sub)
                if name:
                    result_lines.append(
                        f"- **{entry.name}/{name}**: {description}"
                    )
        else:
            name, description = _load_skill_meta(entry)
            if name:
                result_lines.append(f"- **{name}**: {description}")

    if not result_lines:
        msg = "[info] No skills found"
        if category_filter:
            msg += f" in category '{category_filter}'"
        return msg + "."

    header = f"## Available Skills ({len(result_lines)})"
    return "\n".join([header] + result_lines)


def _view_skill(workspace: Path, name: str) -> str:
    """View a specific skill by name."""
    skills_dir = workspace / "skills"
    if not skills_dir.is_dir():
        return "[error: No skills directory found]"

    # Direct match: workspace/skills/<name>/SKILL.md
    direct = skills_dir / name / "SKILL.md"
    if direct.exists():
        try:
            content = direct.read_text()
            if not content.strip():
                return f"[info] Skill '{name}' is empty."
            return content
        except (OSError, UnicodeDecodeError) as e:
            return f"[error reading skill: {e}]"

    # Search in category subdirs: workspace/skills/<category>/<name>/SKILL.md
    for cat_dir in skills_dir.iterdir():
        if not cat_dir.is_dir():
            continue
        candidate = cat_dir / name / "SKILL.md"
        if candidate.exists():
            try:
                content = candidate.read_text()
                if not content.strip():
                    return f"[info] Skill '{name}' is empty."
                return content
            except (OSError, UnicodeDecodeError) as e:
                return f"[error reading skill: {e}]"

    return f"[error: Skill '{name}' not found. Use skills_list to see available skills.]"


def _manage_skill(workspace: Path, args: dict) -> str:
    """Create, edit, or delete a skill."""
    action = (args.get("action") or "").strip()
    name = (args.get("name") or "").strip()

    if not name:
        return "[error: 'name' is required]"
    if not re.match(r"^[a-zA-Z0-9_-]+$", name):
        return "[error: name must contain only letters, numbers, hyphens, and underscores]"

    category = (args.get("category") or "").strip()
    skills_dir = workspace / "skills"

    if category:
        skill_dir = skills_dir / category / name
    else:
        skill_dir = skills_dir / name

    if action == "create":
        content = args.get("content")
        if not content:
            return "[error: 'content' is required for create]"
        try:
            skill_dir.mkdir(parents=True, exist_ok=True)
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                return f"[error: Skill '{name}' already exists. Use edit to update it.]"
            skill_file.write_text(content)
            return f"[ok] Skill '{name}' created at {skill_file}."
        except OSError as e:
            return f"[error creating skill: {e}]"

    elif action == "edit":
        content = args.get("content")
        if not content:
            return "[error: 'content' is required for edit]"
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            return f"[error: Skill '{name}' not found. Use create to make a new one.]"
        try:
            skill_file.write_text(content)
            return f"[ok] Skill '{name}' updated."
        except OSError as e:
            return f"[error updating skill: {e}]"

    elif action == "delete":
        if not skill_dir.exists():
            # Check category subdirectories too
            for cat_dir in skills_dir.iterdir():
                if not cat_dir.is_dir():
                    continue
                candidate = cat_dir / name
                if candidate.exists():
                    skill_dir = candidate
                    break
            else:
                return f"[error: Skill '{name}' not found.]"
        import shutil

        try:
            shutil.rmtree(skill_dir)
            return f"[ok] Skill '{name}' deleted."
        except OSError as e:
            return f"[error deleting skill: {e}]"

    return f"[error: Unknown action '{action}'. Use create, edit, or delete.]"


def _load_skill_meta(skill_dir: Path) -> tuple[str, str]:
    """Extract skill name and description from a skill directory."""
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.exists():
        return ("", "")
    try:
        content = skill_file.read_text()
    except (OSError, UnicodeDecodeError):
        return ("", "")
    return _parse_skill_metadata(skill_dir.name, content)


def _is_category_dir(path: Path) -> bool:
    """Check if a directory under skills/ contains subdirectories (not a skill itself)."""
    if not path.is_dir():
        return False
    if (path / "SKILL.md").exists():
        return False
    for child in path.iterdir():
        if child.is_dir():
            return True
    return False


def _parse_skill_metadata(dir_name: str, content: str) -> tuple[str, str]:
    """Extract skill name and description from SKILL.md content."""
    lines = content.splitlines()

    if lines and lines[0].strip() == "---":
        fm_name = ""
        fm_description = ""
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                if fm_description:
                    return fm_name or dir_name, fm_description
                return _parse_legacy_description(dir_name, lines[i + 1 :])
            stripped = line.strip()
            if stripped.startswith("name:"):
                fm_name = stripped[5:].strip().strip("\"'")
            elif stripped.startswith("description:"):
                fm_description = stripped[12:].strip().strip("\"'")

    return _parse_legacy_description(dir_name, lines)


def _parse_legacy_description(
    dir_name: str, lines: list[str]
) -> tuple[str, str]:
    """Extract description as the first non-empty, non-heading line."""
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return dir_name, stripped
    return dir_name, ""
