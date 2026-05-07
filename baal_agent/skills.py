"""Skill management tools — let the agent list, view, create, and delete skills.

Skills are stored as `workspace/skills/<name>/SKILL.md` with YAML frontmatter
(name, description) and optional category subdirectories.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

SKILLS_TOOL_DEF = {
    "function": {
        "name": "skills_list",
        "description": "List all available skills with their names and descriptions. "
        "Skills are reusable procedures stored in workspace/skills/.",
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
    "function": {
        "name": "skill_view",
        "description": "Load a skill's full content. Skills are markdown files with "
        "YAML frontmatter stored in workspace/skills/<name>/SKILL.md. "
        "Returns the full file content. Use after skills_list to get details.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The skill directory name (e.g., 'web-research').",
                }
            },
            "required": ["name"],
        },
    }
}

SKILL_MANAGE_TOOL_DEF = {
    "function": {
        "name": "skill_manage",
        "description": "Create, update, or delete a skill. Skills are stored as "
        "workspace/skills/<name>/SKILL.md with YAML frontmatter. "
        "Actions: create (new skill), edit (rewrite full content), "
        "delete (remove skill directory). When a complex task succeeds, "
        "offer to save the procedure as a skill.",
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
                    "description": "Skill directory name (lowercase, hyphens).",
                },
                "content": {
                    "type": "string",
                    "description": "Full SKILL.md content with YAML frontmatter. "
                    "Required for create and edit.",
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


def _exec_skills_list(
    args: dict[str, Any],
    workspace: Path,
    **_,
) -> str:
    """List skills, optionally filtered by category."""
    skills_dir = workspace / "skills"
    if not skills_dir.is_dir():
        return "No skills directory found."

    category_filter = (args.get("category") or "").strip().lower()

    lines: list[str] = []
    result_lines: list[str] = []

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue

        # Skip category dirs themselves — look inside them
        post_category: list[Path]
        if _is_category_dir(skill_dir):
            if category_filter and skill_dir.name.lower() != category_filter:
                continue
            post_category = sorted(skill_dir.iterdir())
        else:
            post_category = [skill_dir]

        for sub in post_category:
            if not sub.is_dir():
                continue
            skill_file = sub / "SKILL.md"
            if not skill_file.exists():
                continue
            try:
                content = skill_file.read_text()
            except (OSError, UnicodeDecodeError):
                continue
            name, description = _parse_skill_metadata(sub.name, content)
            cat_prefix = f"{skill_dir.name}/" if _is_category_dir(skill_dir) else ""
            result_lines.append(f"- **{cat_prefix}{name}**: {description}")

    if not result_lines:
        msg = f"No skills found"
        if category_filter:
            msg += f" in category '{category_filter}'"
        return msg + "."

    header = f"## Available Skills ({len(result_lines)})"
    lines.append(header)
    lines.extend(result_lines)
    return "\n".join(lines)


def _exec_skill_view(
    args: dict[str, Any],
    workspace: Path,
    **_,
) -> str:
    """Load a specific skill's content."""
    name = (args.get("name") or "").strip()
    if not name:
        return "Error: 'name' is required."

    # Search in workspace/skills/<name>/ or workspace/skills/<category>/<name>/
    skills_dir = workspace / "skills"
    if not skills_dir.is_dir():
        return "No skills directory found."

    # Direct match first
    direct = skills_dir / name / "SKILL.md"
    if direct.exists():
        try:
            return direct.read_text()
        except (OSError, UnicodeDecodeError) as e:
            return f"Error reading skill: {e}"

    # Search in category subdirectories
    for cat_dir in skills_dir.iterdir():
        if not cat_dir.is_dir():
            continue
        candidate = cat_dir / name / "SKILL.md"
        if candidate.exists():
            try:
                return candidate.read_text()
            except (OSError, UnicodeDecodeError) as e:
                return f"Error reading skill: {e}"

    return f"Skill '{name}' not found. Use skills_list to see available skills."


def _exec_skill_manage(
    args: dict[str, Any],
    workspace: Path,
    **_,
) -> str:
    """Create, edit, or delete a skill."""
    action = (args.get("action") or "").strip()
    name = (args.get("name") or "").strip()

    if not name:
        return "Error: 'name' is required."
    if not re.match(r"^[a-zA-Z0-9_-]+$", name):
        return "Error: name must contain only letters, numbers, hyphens, and underscores."

    category = (args.get("category") or "").strip()

    # Determine skill path
    skills_dir = workspace / "skills"
    if category:
        skill_dir = skills_dir / category / name
    else:
        skill_dir = skills_dir / name

    if action == "create":
        if not args.get("content"):
            return "Error: 'content' is required for create."
        try:
            skill_dir.mkdir(parents=True, exist_ok=True)
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text(args["content"])
            return f"Skill '{name}' created successfully at {skill_file}."
        except OSError as e:
            return f"Error creating skill: {e}"

    elif action == "edit":
        if not args.get("content"):
            return "Error: 'content' is required for edit."
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            return f"Skill '{name}' not found. Use action='create' to make a new one."
        try:
            skill_file.write_text(args["content"])
            return f"Skill '{name}' updated successfully."
        except OSError as e:
            return f"Error updating skill: {e}"

    elif action == "delete":
        if not skill_dir.exists():
            return f"Skill '{name}' not found."
        import shutil

        try:
            shutil.rmtree(skill_dir)
            return f"Skill '{name}' deleted successfully."
        except OSError as e:
            return f"Error deleting skill: {e}"

    return f"Unknown action: {action}. Use 'create', 'edit', or 'delete'."


def _is_category_dir(path: Path) -> bool:
    """Check if a directory under skills/ contains subdirectories (not a skill itself)."""
    if not path.is_dir():
        return False
    # If it has subdirectories and no SKILL.md, it's a category dir
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
