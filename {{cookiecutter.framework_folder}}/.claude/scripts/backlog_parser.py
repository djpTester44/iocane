"""Backlog parsing utilities.

YAML-based backlog I/O with Pydantic validation.
Plan parsing has moved to plan_parser.py (Phase 2).

Used by hooks, scripts, auto_checkpoint.py, and auto_architect.py.
"""

import re
from pathlib import Path

import yaml
from schemas import Annotation, Backlog, BacklogItem

# ---------------------------------------------------------------------------
# Backlog I/O (YAML)
# ---------------------------------------------------------------------------


def load_backlog(path: str) -> Backlog:
    """Load and validate plans/backlog.yaml."""
    text = Path(path).read_text(encoding="utf-8")
    if not text.strip():
        return Backlog()
    raw = yaml.safe_load(text)
    if raw is None:
        return Backlog()
    return Backlog.model_validate(raw)


def save_backlog(path: str, backlog: Backlog) -> None:
    """Serialize backlog to YAML and write to disk."""
    data = backlog.model_dump(mode="json", exclude_none=True)
    # Clean up empty lists to keep YAML readable
    for item in data.get("items", []):
        for key in ("files", "blocked_by", "annotations"):
            if key in item and not item[key]:
                del item[key]
    output = yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)
    Path(path).write_text(output, encoding="utf-8")


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def find_item(backlog: Backlog, bl_id: str) -> BacklogItem | None:
    """Find a backlog item by BL-ID."""
    for item in backlog.items:
        if item.id == bl_id:
            return item
    return None


def find_max_id(backlog: Backlog) -> int:
    """Find the highest numeric BL-ID. Returns 0 if no items."""
    max_id = 0
    for item in backlog.items:
        match = re.match(r"BL-(\d{3})", item.id)
        if match:
            max_id = max(max_id, int(match.group(1)))
    return max_id


def open_items(backlog: Backlog) -> list[BacklogItem]:
    """Return all items with status == open."""
    return [item for item in backlog.items if item.status.value == "open"]


def items_by_tag(backlog: Backlog, *tags: str) -> list[BacklogItem]:
    """Return items matching any of the given tag strings."""
    tag_set = set(tags)
    return [item for item in backlog.items if item.tag.value in tag_set]


def items_with_routing(backlog: Backlog, command: str) -> list[BacklogItem]:
    """Return items whose routing prompt annotation contains the given command string."""
    return [
        item for item in backlog.items
        if (prompt := item.get_routing_prompt()) and command in prompt
    ]


# ---------------------------------------------------------------------------
# Mutations (return new Backlog)
# ---------------------------------------------------------------------------


def add_item(backlog: Backlog, item: BacklogItem) -> Backlog:
    """Return a new Backlog with the item appended."""
    return Backlog(items=[*backlog.items, item])


def update_item(backlog: Backlog, bl_id: str, **changes: object) -> Backlog:
    """Return a new Backlog with the specified item updated.

    Uses model_copy(update=...) on the frozen BacklogItem.
    """
    new_items: list[BacklogItem] = []
    for item in backlog.items:
        if item.id == bl_id:
            new_items.append(item.model_copy(update=changes))
        else:
            new_items.append(item)
    return Backlog(items=new_items)


def add_annotation(backlog: Backlog, bl_id: str, annotation: Annotation) -> Backlog:
    """Return a new Backlog with an annotation appended to the specified item."""
    new_items: list[BacklogItem] = []
    for item in backlog.items:
        if item.id == bl_id:
            new_items.append(
                item.model_copy(update={"annotations": [*item.annotations, annotation]})
            )
        else:
            new_items.append(item)
    return Backlog(items=new_items)


def mark_resolved(backlog: Backlog, bl_id: str) -> Backlog:
    """Return a new Backlog with the specified item marked resolved."""
    return update_item(backlog, bl_id, status="resolved")



def extract_bl_ids_from_text(text: str) -> list[str]:
    """Find all BL-NNN references in text."""
    return re.findall(r"BL-\d{3}", text)
