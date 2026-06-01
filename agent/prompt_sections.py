"""Typed prompt-section rendering for chat-app/persona compatibility."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

_ALLOWED_INSERTIONS = {"identity_after", "context", "ephemeral"}
_TYPE_LABELS = {
    "character_name": "Character name",
    "character_description": "Character description",
    "personality": "Personality",
    "scenario": "Scenario",
    "creator_notes": "Creator notes",
    "system_rules": "System rules",
    "response_style": "Response style",
    "world_info": "World info",
    "lorebook": "Lorebook",
    "authors_note": "Author's note",
    "post_history_instructions": "Post-history instructions",
}


def _clean_text(value: Any, *, limit: int = 24000) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    if len(text) > limit:
        return text[:limit] + "\n...[truncated prompt section]"
    return text


def _section_label(section_type: str, name: str = "") -> str:
    base = _TYPE_LABELS.get(section_type, section_type.replace("_", " ").title())
    if name:
        return f"{base}: {name}"
    return base


def normalize_prompt_sections(raw: Any) -> list[dict[str, Any]]:
    """Normalize config-defined prompt sections into sortable dictionaries."""

    if not isinstance(raw, list):
        return []
    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, Mapping):
            continue
        if item.get("enabled", True) is False:
            continue
        insertion = str(item.get("insertion") or "context").strip().lower()
        if insertion not in _ALLOWED_INSERTIONS:
            insertion = "context"
        section_type = str(item.get("type") or item.get("name") or "custom").strip().lower()
        name = str(item.get("name") or "").strip()
        content = _clean_text(item.get("content"))
        if not content:
            continue
        try:
            order = int(item.get("order", 100))
        except (TypeError, ValueError):
            order = 100
        normalized.append(
            {
                "type": section_type,
                "name": name,
                "content": content,
                "insertion": insertion,
                "order": order,
                "_index": idx,
            }
        )
    normalized.sort(key=lambda s: (s["order"], s["_index"]))
    return normalized


def render_prompt_sections(sections: Iterable[Mapping[str, Any]], insertion: str) -> str:
    """Render prompt sections for one insertion slot."""

    blocks: list[str] = []
    for section in sections or []:
        if section.get("insertion") != insertion:
            continue
        label = _section_label(str(section.get("type") or "custom"), str(section.get("name") or ""))
        content = _clean_text(section.get("content"))
        if not content:
            continue
        blocks.append(f"### {label}\n{content}")
    if not blocks:
        return ""
    return "## Typed prompt sections\n\n" + "\n\n".join(blocks)
