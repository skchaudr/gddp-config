"""Helper functions for handling the keyed acceptance criteria schema.

The node schema v1 requires acceptance criteria to be a list of mappings:
  acceptance:
    - id: stable-kebab-id
      criterion: verifiable criterion text
"""

import re

# Same regex as used in other scripts for consistency
NAME_TO_KEBAB_RE = re.compile(r"[^a-z0-9]+")
KEBAB_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


def slugify_criterion(text: str, max_length: int = 50) -> str:
    """Convert a criterion string into a stable kebab-case ID."""
    s = text.strip().lower()
    # Remove common filler words to keep IDs shorter/cleaner
    fillers = {"a", "an", "the", "and", "or", "but", "is", "if", "then", "of", "to", "for", "in", "on", "with"}
    words = [w for w in NAME_TO_KEBAB_RE.split(s) if w and w not in fillers]

    s = "-".join(words)
    if len(s) > max_length:
        # Try to break at a hyphen
        truncated = s[:max_length].rsplit("-", 1)[0]
        if truncated:
            s = truncated
        else:
            s = s[:max_length]

    s = s.strip("-")

    if not KEBAB_RE.match(s):
        # Last resort fallback
        return "criterion-" + hex(hash(text) & 0xffffffff)[2:]
    return s


def text_to_item(text: str) -> dict:
    """Convert plain text criterion to the schema-compliant dict."""
    return {
        "id": slugify_criterion(text),
        "criterion": text
    }


def ensure_list_of_items(items: list) -> list[dict]:
    """Convert a list of (possibly) mixed strings and dicts into all dicts."""
    result = []
    for item in items:
        if isinstance(item, str):
            result.append(text_to_item(item))
        elif isinstance(item, dict) and "id" in item and "criterion" in item:
            result.append(item)
        elif isinstance(item, dict) and "criterion" in item:
            # Missing ID but has criterion
            result.append(text_to_item(item["criterion"]))
    return result
