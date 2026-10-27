"""Skills — reusable, composable procedures the agent can load on demand.

A skill is a directory with a ``SKILL.md`` file:

    ---
    name: svg-chart
    title: SVG chart
    description: Build a vector chart with zero dependencies.
    when_to_use: The user asks for a chart, graph, plot or dashboard.
    uses: [data-wrangler]          # optional: skills this one calls
    triggers: [chart, plot, graph] # optional: phrases that auto-route here
    files: [csv, json]             # optional: extensions that auto-route here
    tools: [run_terminal_command]  # optional: tools it expects
    icon: chart                    # optional: UI glyph
    author: user                   # set automatically for skills you create
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
    triggers: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    icon: str = "spark"
    author: str = "builtin"
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
            "triggers": self.triggers,
            "files": self.files,
            "icon": self.icon,
            "author": self.author,
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
        triggers=[str(t).strip().lower() for t in (meta.get("triggers") or []) if str(t).strip()],
        files=[str(f).strip().lower().lstrip(".") for f in (meta.get("files") or []) if str(f).strip()],
        icon=str(meta.get("icon") or "spark"),
        author=str(meta.get("author") or "builtin"),
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


# ---------------------------------------------------------------------------
# Router — decide which skills a request needs *before* the model speaks.
#
# The model can always call `use_skill` itself, but that relies on it choosing
# to. The router is the deterministic path: mention "PDF", attach a .csv, or
# say "chart this", and the matching skill (plus the skills it uses) is loaded
# into the turn automatically.
# ---------------------------------------------------------------------------

STOPWORDS = frozenset({
    "the", "and", "for", "you", "with", "this", "that", "from", "into", "please",
    "can", "could", "would", "make", "made", "want", "need", "help", "file",
    "files", "use", "using", "use", "about", "give", "some", "any", "all",
    "и", "my", "our", "your", "have", "has", "its", "it's", "them", "then",
})


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9][a-z0-9+.-]{2,}", (text or "").lower())
    return {w for w in words if w not in STOPWORDS and len(w) >= 3}


def _phrase_in(query: str, phrase: str) -> bool:
    phrase = (phrase or "").strip().lower()
    if not phrase:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", query) is not None


class SkillRouter:
    """Scores enabled skills against a user request + any attached filenames."""

    def __init__(self, registry: "SkillRegistry | None" = None, threshold: int = 3):
        self.registry = registry or SkillRegistry()
        self.threshold = threshold

    def route(
        self,
        query: str,
        file_names: Iterable[str] = (),
        enabled_map: dict[str, bool] | None = None,
        limit: int = 2,
    ) -> list[dict[str, Any]]:
        q = (query or "").lower()
        exts = {
            Path(str(n)).suffix.lower().lstrip(".")
            for n in (file_names or ())
            if Path(str(n)).suffix
        }
        scored: list[dict[str, Any]] = []

        for skill in self.registry.enabled(enabled_map):
            score = 0
            reasons: list[str] = []

            hit_files = sorted(exts & {f.lower() for f in skill.files})
            if hit_files:
                score += 6 * len(hit_files)
                reasons.append("file ." + ", .".join(hit_files))

            for trig in skill.triggers:
                if _phrase_in(q, trig):
                    score += 3
                    reasons.append(f"“{trig}”")

            name_words = [w for w in skill.name.replace("_", "-").split("-") if len(w) > 3]
            if any(_phrase_in(q, w) for w in name_words):
                score += 2
                reasons.append("name")

            overlap = _tokens(q) & _tokens(f"{skill.description} {skill.when_to_use}")
            if overlap:
                score += min(3, len(overlap))
                reasons.append("words: " + ", ".join(sorted(overlap)[:4]))

            if score >= self.threshold:
                scored.append({"name": skill.name, "score": score, "reasons": reasons})

        scored.sort(key=lambda r: (-r["score"], r["name"]))
        if not scored:
            return []
        # Keep the runner-up only when it is genuinely close, otherwise a stray
        # keyword drags in an irrelevant skill (or a whole dependency tree).
        top = scored[0]["score"]
        kept = [scored[0]] + [r for r in scored[1:] if r["score"] >= top * 0.6]
        return kept[:limit]


# ---------------------------------------------------------------------------
# Authoring — users (and the agent itself) can create skills at runtime.
# ---------------------------------------------------------------------------

NAME_RE = re.compile(r"[a-z0-9][a-z0-9_-]{1,48}")


class SkillError(ValueError):
    """A skill could not be created, updated or removed."""


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return slug[:48]


def _render_frontmatter(meta: dict[str, Any]) -> str:
    lines = ["---"]
    for key in ("name", "title", "description", "when_to_use"):
        if meta.get(key):
            lines.append(f"{key}: {meta[key]}")
    for key in ("uses", "triggers", "files", "tools"):
        values = meta.get(key) or []
        if values:
            lines.append(f"{key}: [{', '.join(str(v) for v in values)}]")
    if meta.get("icon"):
        lines.append(f"icon: {meta['icon']}")
    if meta.get("author"):
        lines.append(f"author: {meta['author']}")
    lines.append("---")
    return "\n".join(lines)


def create_skill(
    *,
    name: str,
    description: str,
    body: str,
    title: str = "",
    when_to_use: str = "",
    uses: Iterable[str] | None = None,
    triggers: Iterable[str] | None = None,
    files: Iterable[str] | None = None,
    icon: str = "spark",
    author: str = "user",
    overwrite: bool = False,
) -> Skill:
    """Write a new ``skills/<name>/SKILL.md`` and return the parsed skill."""
    slug = _slug(name)
    if not slug or not NAME_RE.fullmatch(slug):
        raise SkillError(
            f"'{name}' is not a usable skill name — use lowercase letters, numbers, - or _."
        )
    if not (description or "").strip():
        raise SkillError("A skill needs a one-line description.")
    if not (body or "").strip():
        raise SkillError("A skill needs a body — the steps to follow.")

    directory = Path(SKILLS_DIR) / slug
    target = directory / "SKILL.md"
    if target.exists() and not overwrite:
        raise SkillError(f"A skill named '{slug}' already exists.")

    meta = {
        "name": slug,
        "title": (title or slug.replace("-", " ").title()).strip(),
        "description": description.strip().replace("\n", " "),
        "when_to_use": when_to_use.strip().replace("\n", " "),
        "uses": [u.strip() for u in (uses or []) if str(u).strip()],
        "triggers": [t.strip().lower() for t in (triggers or []) if str(t).strip()],
        "files": [f.strip().lower().lstrip(".") for f in (files or []) if str(f).strip()],
        "tools": ["run_terminal_command"],
        "icon": icon or "spark",
        "author": author,
    }
    directory.mkdir(parents=True, exist_ok=True)
    target.write_text(f"{_render_frontmatter(meta)}\n\n{body.strip()}\n", encoding="utf-8")

    skill = load_skill(directory)
    if skill is None or skill.error:
        raise SkillError(f"The skill was written but could not be parsed: {skill.error if skill else 'unknown'}")
    return skill


def update_skill(name: str, **fields: Any) -> Skill:
    """Rewrite an existing skill's frontmatter/body, keeping anything not passed."""
    skill = discover_skills().get(name)
    if not skill:
        raise SkillError(f"No skill named '{name}'.")
    return create_skill(
        name=skill.name,
        title=fields.get("title", skill.title),
        description=fields.get("description", skill.description),
        when_to_use=fields.get("when_to_use", skill.when_to_use),
        uses=fields.get("uses", skill.uses),
        triggers=fields.get("triggers", skill.triggers),
        files=fields.get("files", skill.files),
        body=fields.get("body", skill.body),
        icon=fields.get("icon", skill.icon),
        author=fields.get("author", skill.author),
        overwrite=True,
    )


def delete_skill(name: str) -> None:
    """Remove a user/agent-authored skill. Built-ins are protected."""
    skill = discover_skills().get(name)
    if not skill:
        raise SkillError(f"No skill named '{name}'.")
    if skill.author == "builtin":
        raise SkillError(f"'{name}' ships with the app — disable it instead of deleting it.")
    directory = Path(skill.path).parent
    if Path(SKILLS_DIR).resolve() not in directory.resolve().parents:
        raise SkillError("That skill lives outside the skills directory.")
    for child in sorted(directory.rglob("*"), reverse=True):
        child.unlink() if child.is_file() else child.rmdir()
    directory.rmdir()
