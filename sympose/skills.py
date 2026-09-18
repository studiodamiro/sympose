"""
Modular Skill Playbook Manager for Sympose.
Parses, indexes, and formats standard SKILL.md playbooks for personas and sub-agents.
"""

import glob
import logging
import os
import re
from typing import Any

import yaml

log = logging.getLogger(__name__)


class Skill:
    """Represents a procedural skill loaded from a SKILL.md file."""

    def __init__(
        self,
        name: str,
        title: str,
        description: str,
        content: str,
        tags: list[str] | None = None,
        mcp_servers: list[str] | None = None,
        recommended_models: list[str] | None = None,
        minimum_capability_tier: str | None = None,
        filepath: str = "",
    ):
        self.name = name.lower()
        self.title = title or name.replace("_", " ").title()
        self.description = description
        self.content = content.strip()
        self.tags = tags or []
        self.mcp_servers = mcp_servers or []
        self.recommended_models = recommended_models or []
        # ADR-127/128: an optional capability floor (e.g. "standard") a
        # candidate model must clear for this skill's work. None (every
        # skill until a SKILL.md opts in) preserves today's plain
        # first-recommended-model behavior at every consumer.
        self.minimum_capability_tier = minimum_capability_tier
        self.filepath = filepath

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "tags": self.tags,
            "mcp_servers": self.mcp_servers,
            "recommended_models": self.recommended_models,
            "minimum_capability_tier": self.minimum_capability_tier,
            "filepath": self.filepath,
        }


class SkillManager:
    """Discovers, indexes, and compiles modular skill playbooks from the skills/ directory."""

    def __init__(self, skills_dir: str | None = None):
        if skills_dir:
            self.skills_dir = skills_dir
        else:
            from sympose.bootstrap import resolve_workspace_dir

            self.skills_dir = os.path.join(resolve_workspace_dir(), "skills")
        self.skills: dict[str, Skill] = {}
        self.reload_skills()

    def reload_skills(self) -> dict[str, Skill]:
        """Scans the skills directory and loads all valid SKILL.md and standalone markdown playbooks."""
        self.skills.clear()

        search_dirs = [self.skills_dir]
        builtin_dir = os.path.join(os.path.dirname(__file__), "builtin_skills")
        if os.path.exists(builtin_dir) and builtin_dir not in search_dirs:
            search_dirs.append(builtin_dir)

        found_files = set()
        for s_dir in search_dirs:
            if not os.path.exists(s_dir):
                continue
            # 1. Folder-based skills: skills/<name>/SKILL.md or skills/<name>/skill.md
            folder_pattern = os.path.join(s_dir, "*", "SKILL.md")
            folder_pattern_lower = os.path.join(s_dir, "*", "skill.md")
            for f in glob.glob(folder_pattern) + glob.glob(folder_pattern_lower):
                found_files.add(f)
            # 2. Standalone markdown files in skills/ directory (e.g. skills/debugging.md)
            for f in glob.glob(os.path.join(s_dir, "*.md")):
                found_files.add(f)

        for filepath in sorted(found_files):
            try:
                skill = self._parse_skill_file(filepath)
                if skill:
                    # User custom skills in workspace override builtins with the same name
                    self.skills[skill.name] = skill
            except Exception as e:
                log.warning("Error loading skill from %s: %s", filepath, e)

        return self.skills

    def _parse_skill_file(self, filepath: str) -> Skill | None:
        """Parses a markdown file with optional YAML frontmatter into a Skill object."""
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            raw_text = f.read()

        # Derive default skill name from folder name or file basename
        parent_dir = os.path.dirname(filepath)
        if os.path.basename(filepath).lower() in ("skill.md", "skill.markdown"):
            default_name = os.path.basename(parent_dir)
        else:
            default_name = os.path.splitext(os.path.basename(filepath))[0]

        metadata: dict[str, Any] = {}
        body = raw_text

        # Extract YAML frontmatter if present
        if raw_text.startswith("---"):
            parts = raw_text.split("---", 2)
            if len(parts) >= 3:
                try:
                    loaded_meta = yaml.safe_load(parts[1])
                    if isinstance(loaded_meta, dict):
                        metadata = loaded_meta
                    body = parts[2].strip()
                except Exception:
                    body = raw_text

        name = str(metadata.get("name") or default_name).strip().lower()
        title = str(metadata.get("title") or name.replace("_", " ").title()).strip()
        description = str(metadata.get("description") or "").strip()
        tags = metadata.get("tags") if isinstance(metadata.get("tags"), list) else []
        mcp_servers = (
            metadata.get("mcp_servers")
            if isinstance(metadata.get("mcp_servers"), list)
            else []
        )
        recommended_models = (
            metadata.get("recommended_models")
            if isinstance(metadata.get("recommended_models"), list)
            else []
        )
        raw_tier = metadata.get("minimum_capability_tier")
        minimum_capability_tier = str(raw_tier).strip() if raw_tier else None

        return Skill(
            name=name,
            title=title,
            description=description,
            content=body,
            tags=tags,
            mcp_servers=mcp_servers,
            recommended_models=recommended_models,
            minimum_capability_tier=minimum_capability_tier,
            filepath=filepath,
        )

    def get_skill(self, name: str) -> Skill | None:
        """Retrieves a skill by name (case-insensitive and tolerant of naming variations)."""
        raw = name.lower().strip()
        if raw in self.skills:
            return self.skills[raw]
        clean = re.sub(r"[_\-\s]", "", raw)
        for s_name, skill in self.skills.items():
            if re.sub(r"[_\-\s]", "", s_name) == clean:
                return skill
            if (
                clean in re.sub(r"[_\-\s]", "", skill.title.lower())
                or re.sub(r"[_\-\s]", "", s_name) in clean
            ):
                return skill

        # Dynamic hot-reload check if new skill was added at runtime
        self.reload_skills()
        if raw in self.skills:
            return self.skills[raw]
        for s_name, skill in self.skills.items():
            if re.sub(r"[_\-\s]", "", s_name) == clean:
                return skill
            if (
                clean in re.sub(r"[_\-\s]", "", skill.title.lower())
                or re.sub(r"[_\-\s]", "", s_name) in clean
            ):
                return skill
        return None

    def list_skills(self) -> list[dict[str, Any]]:
        """Returns a list of all indexed skill summaries."""
        return [skill.to_dict() for skill in self.skills.values()]

    def format_skills_for_prompt(self, skill_names: list[str]) -> str:
        """Formats the requested skills into a structured markdown prompt section."""
        if not skill_names:
            return ""

        sections = []
        for s_name in skill_names:
            skill = self.get_skill(s_name)
            if skill and skill.content:
                header = f"#### Skill Playbook: {skill.title}"
                if skill.description:
                    header += f"\n*{skill.description}*"
                sections.append(f"{header}\n\n{skill.content}")

        if not sections:
            return ""

        return "### Specialized Skill Playbooks & Heuristics:\n" + "\n\n---\n\n".join(
            sections
        )


# Singleton skill manager
skill_manager = SkillManager()
