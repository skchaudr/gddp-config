"""Shared fzf pickers for gddp interactive surfaces.

Contract
--------
``pick(items, *, preview_cmd=None, multi=False, ...) -> list[str] | None``

* **items** — ``(value, label)`` pairs. ``value`` is what callers get back;
  ``label`` is what the operator scans (may equal value).
* **preview_cmd** — shell fragment for ``fzf --preview``. Field tokens:
  ``{1}`` = value, ``{2}`` = label, ``{}`` = full line. fzf shell-escapes
  each placeholder (e.g. ``{1}`` → ``'aa-cli'``). Do **not** wrap
  ``{1}`` inside extra double quotes (that embeds literal quote chars
  into the path and breaks previews).
* **multi** — tab/shift-tab multi-select (``--multi``).
* **return** — selected values (order preserved). ``None`` means cancel,
  empty list input, or fzf unavailable / non-zero exit.

Callers that need a paged-menu fallback should branch on ``available()``
(or on ``None``) and keep using ``_paged_menu``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Sequence


def available() -> bool:
    """True when ``fzf`` is on PATH and stdout is a TTY (fzf needs one)."""
    if not sys.stdout.isatty() or not sys.stdin.isatty():
        return False
    return shutil.which("fzf") is not None


def pick(
    items: Sequence[tuple[str, str]],
    *,
    prompt: str = "pick> ",
    header: str = "",
    preview_cmd: str | None = None,
    preview_window: str = "down:8:wrap",
    multi: bool = False,
    height: str = "90%",
    fzf_bin: str | None = None,
) -> list[str] | None:
    """Run fzf over ``items``; return selected values or ``None``.

    Empty ``items`` → ``None``. Cancel (esc / ctrl-c / non-zero) → ``None``.
    """
    pairs = [(str(v), str(lab if lab is not None else v)) for v, lab in items]
    if not pairs:
        return None

    binary = fzf_bin or shutil.which("fzf")
    if not binary:
        return None

    # value\\tlabel — accept only field 1 so callers never parse labels.
    payload = "\n".join(f"{value}\t{label}" for value, label in pairs) + "\n"
    cmd: list[str] = [
        binary,
        "--delimiter=\t",
        "--with-nth=2..",
        "--accept-nth=1",
        "--prompt",
        prompt,
        "--height",
        height,
        "--layout=reverse",
        "--border",
        "--cycle",
        "--ansi",
        "--info=inline",
    ]
    if header:
        cmd.extend(["--header", header])
    if multi:
        cmd.append("--multi")
        cmd.extend(["--bind", "ctrl-a:select-all,ctrl-d:deselect-all"])
    if preview_cmd:
        cmd.extend([
            "--preview",
            preview_cmd,
            "--preview-window",
            preview_window,
        ])

    env = os.environ.copy()
    # Prefer a quiet color scheme; leave FZF_DEFAULT_OPTS if the user set it.
    try:
        proc = subprocess.run(
            cmd,
            input=payload,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
    except OSError:
        return None

    if proc.returncode != 0:
        # 130 = interrupt / esc in many fzf builds; 1 = no match / cancel.
        return None

    selected = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if not selected:
        return None

    # Defend against accept-nth quirks / older fzf: if we got full lines, take field 1.
    values: list[str] = []
    known = {v for v, _ in pairs}
    for line in selected:
        if "\t" in line:
            value = line.split("\t", 1)[0]
        else:
            value = line
        if value in known:
            values.append(value)
        elif line in known:
            values.append(line)
    return values or None


def fzf_pick(
    items: Sequence[tuple[str, str]],
    **kwargs,
) -> str | None:
    """Single-select convenience: first value or ``None``."""
    result = pick(items, multi=False, **kwargs)
    if not result:
        return None
    return result[0]


def fzf_multi(
    items: Sequence[tuple[str, str]],
    **kwargs,
) -> list[str] | None:
    """Multi-select convenience: list of values or ``None``."""
    return pick(items, multi=True, **kwargs)
