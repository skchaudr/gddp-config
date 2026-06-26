"""Helpers for node acceptance criteria.

Acceptance criteria are human-authored text, but graph/runtime joins need a
stable key. These helpers keep the CLI ergonomic while writing the keyed schema.
"""

from __future__ import annotations

import re
from typing import Iterable

KEBAB_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def slugify_acceptance_id(text: str, fallback: str = "criterion") -> str:
    slug = NON_ALNUM_RE.sub("-", text.strip().lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    if not slug:
        slug = fallback
    if not slug[0].isalpha():
        slug = f"{fallback}-{slug}"
    return slug[:60].rstrip("-") or fallback


def make_acceptance_item(text: str, existing_ids: Iterable[str] = ()) -> dict[str, str]:
    criterion = text.strip()
    base = slugify_acceptance_id(criterion)
    used = set(existing_ids)
    acc_id = base
    suffix = 2
    while acc_id in used:
        room = 60 - len(f"-{suffix}")
        acc_id = f"{base[:room].rstrip('-')}-{suffix}"
        suffix += 1
    return {"id": acc_id, "criterion": criterion}


def normalize_acceptance_items(items: Iterable[object]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    existing_ids: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            acc_id = str(item.get("id", "")).strip()
            criterion = str(item.get("criterion", "")).strip()
            if criterion:
                if not KEBAB_RE.match(acc_id):
                    acc_id = slugify_acceptance_id(criterion)
                if acc_id in existing_ids:
                    normalized_item = make_acceptance_item(criterion, existing_ids)
                else:
                    normalized_item = {"id": acc_id, "criterion": criterion}
                normalized.append(normalized_item)
                existing_ids.add(normalized_item["id"])
            continue
        if isinstance(item, str) and item.strip():
            normalized_item = make_acceptance_item(item, existing_ids)
            normalized.append(normalized_item)
            existing_ids.add(normalized_item["id"])
    return normalized


def acceptance_text(item: object) -> str | None:
    if isinstance(item, dict):
        criterion = item.get("criterion")
        if isinstance(criterion, str) and criterion.strip():
            return criterion.strip()
    if isinstance(item, str) and item.strip():
        return item.strip()
    return None


def acceptance_has_placeholder(items: Iterable[object]) -> bool:
    for item in items:
        if "REPLACE_ME" in str(item):
            return True
    return False
