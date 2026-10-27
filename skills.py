"""Skills — reusable, composable procedures the agent can load on demand.

A skill is a directory with a ``SKILL.md`` file:

    ---
    name: svg-chart
    title: SVG chart
    description: Build a vector chart with zero dependencies.
    when_to_use: The user asks for a chart, graph, plot or dashboard.
    uses: [data-wrangler]          # optional: skills this one calls
    tools: [run_terminal_command]  # optional: tools it expects
    icon: chart                    # optional: UI glyph
    ---
    ## Steps
    1. ...

Only the *catalog* (name + one-liners) is put in the system prompt; the full
body is loaded with the ``use_skill`` tool, which is how progressive disclosure
keeps the prompt small while skills stay detailed. A skill that lists ``uses``
has its dependencies loaded alongside it, so a skill can call a skill.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from config import SKILLS_DIR, SKILLS_ENABLED_BY_DEFAULT

FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [p.strip().strip("'\"") for p in inner.split(",") if p.strip()]
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    return value.strip("'\"")


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Tiny YAML subset: `key: value`, `key: [a, b]`, `key: >`-free."""
    match = FRONTMATTER.match(text)
    if not match:
        return {}, text

    meta: dict[str, Any] = {}
    for line in match.group(1).splitlines():
        line = line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, raw = line.partition(":")
        meta[key.strip()] = _parse_scalar(raw)
    return meta, match.group(2).lstrip("\n")


@dataclass
class Skill:
    name: str
    title: str
    description: str
    when_to_use: str
    body: str
    uses: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    icon: str = "spark"
    path: str = ""
    error: str | None = None

    def to_dict(self, enabled: bool = True, runs: int = 0, last_used: float | None = None) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "when_to_use": self.when_to_use,
            "uses": self.uses,
            "tools": self.tools,
            "icon": self.icon,
            "enabled": enabled,
            "runs": runs,
            "last_used": last_used,
            "error": self.error,
        }


def load_skill(path: Path) -> Skill | None:
    skill_md = path / "SKILL.md" if path.is_dir() else path
    if not skill_md.is_file():
        return None
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return Skill(
            name=path.name, title=path.name, description="", when_to_use="",
            body="", path=str(skill_md), error=f"unreadable: {exc}",
        )

    meta, body = parse_frontmatter(text)
    name = str(meta.get("name") or path.name).strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,48}", name):
        return Skill(
            name=path.name, title=path.name, description="", when_to_use="",
            body="", path=str(skill_md),
            error=f"invalid skill name {name!r} (lowercase a-z, 0-9, - and _ only)",
        )

    title = str(meta.get("title") or name.replace("-", " ").title())
    description = str(meta.get("description") or "").strip()
    if not description:
        # first non-heading line of the body as a fallback summary
        for line in body.splitlines():
            if line.strip() and not line.lstrip().startswith("#"):
                description = line.strip()
                break

    return Skill(
        name=name,
        title=title,
        description=description[:300],
        when_to_use=str(meta.get("when_to_use") or "").strip(),
        body=body.strip(),
        uses=[str(u) for u in (meta.get("uses") or []) if str(u).strip()],
        tools=[str(t) for t in (meta.get("tools") or []) if str(t).strip()],
        icon=str(meta.get("icon") or "spark"),
        path=str(skill_md),
    )


def discover_skills(directory: Path | None = None) -> dict[str, Skill]:
    """Scan the skills directory. Malformed skills are surfaced, not raised."""
    root = Path(directory or SKILLS_DIR)
    found: dict[str, Skill] = {}
    if not root.is_dir():
        return found
    for entry in sorted(root.iterdir()):
        if entry.name.startswith((".", "_")):
            continue
        skill = load_skill(entry)
        if skill and skill.name not in found:
            found[skill.name] = skill
    return found


class SkillRegistry:
    """Skills + their enabled state. Discovery is cheap, so we re-scan on read."""

    def __init__(self, directory: Path | None = None):
        self.directory = Path(directory or SKILLS_DIR)

    # ---------------------------------------------------------------- reads
    def all(self) -> dict[str, Skill]:
        return discover_skills(self.directory)

    def get(self, name: str) -> Skill | None:
        return self.all().get(name)

    def enabled(self, enabled_map: dict[str, bool] | None = None) -> list[Skill]:
        skills = self.all()
        if enabled_map is None:
            return [s for s in skills.values() if SKILLS_ENABLED_BY_DEFAULT and not s.error]
        return [
            s for s in skills.values()
            if enabled_map.get(s.name, SKILLS_ENABLED_BY_DEFAULT) and not s.error
        ]

    # -------------------------------------------------------------- prompt
    def catalog(self, enabled_map: dict[str, bool] | None = None) -> str:
        """Compact listing injected into the system prompt (name + one-liner)."""
        rows = []
        for skill in self.enabled(enabled_map):
            when = f" — {skill.when_to_use}" if skill.when_to_use else ""
            rows.append(f"- {skill.name}: {skill.description}{when}")
        return "\n".join(rows)

    def load_with_dependencies(self, name: str, max_depth: int = 2) -> tuple[str, list[str], list[str]]:
        """Return (prompt_text, loaded, missing) for a skill and the skills it uses."""
        skills = self.all()
        loaded: list[str] = []
        missing: list[str] = []
        chunks: list[str] = []

        def walk(skill_name: str, depth: int) -> None:
            if depth > max_depth or skill_name in loaded:
                return
            skill = skills.get(skill_name)
            if not skill:
                missing.append(skill_name)
                return
            loaded.append(skill_name)
            header = f"# Skill: {skill.title} (`{skill.name}`)"
            if depth > 0:
                header += " — loaded because another skill depends on it"
            chunks.append(f"{header}\n\n{skill.body}")
            for dep in skill.uses:
                walk(dep, depth + 1)

        walk(name, 0)

        if not loaded:
            return "", [], missing

        text = "\n\n---\n\n".join(chunks)
        if missing:
            text += f"\n\n---\n\nNote: referenced skill(s) not installed: {', '.join(missing)}."
        return text, loaded, missing
