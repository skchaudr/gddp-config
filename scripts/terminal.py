"""Minimal terminal input helpers — single keypress + arrow decode.

Ported verbatim from context_refinery/triage/terminal.py — battle-tested on
the vault normalization TUI. No class hierarchy, no framework. Just getch,
getline, and a shared Console.
"""

import os
import select
import sys
import termios
import tty

try:
    from rich.console import Console
except ImportError:
    print("This script needs `rich`. Install:  pip install rich")
    sys.exit(1)

console = Console()

# Arrow bytes can be split by terminal multiplexers. Keep bare Escape responsive
# while allowing a realistic gap between bytes in the same control sequence.
# tmux escape-time is 100ms on this host; stay above that plus a small slop.
ESCAPE_SEQUENCE_TIMEOUT_SECONDS = 0.25

_ARROW_FINALS = {
    "A": "UP",
    "B": "DOWN",
    "C": "RIGHT",
    "D": "LEFT",
    "H": "HOME",
    "F": "END",
}
_TILDE_KEYS = {
    "1": "HOME",
    "4": "END",
    "3": "DELETE",
    "5": "PAGE_UP",
    "6": "PAGE_DOWN",
}


def _map_csi(params: str, final: str) -> str:
    """Map a complete CSI sequence. Unknown / focus / mouse → '' (not Escape)."""
    if final in _ARROW_FINALS:
        return _ARROW_FINALS[final]
    if final == "~":
        kind = params.split(";")[0] if params else ""
        return _TILDE_KEYS.get(kind, "")
    return ""


def _decode_escape_sequence(first: str, read_available) -> str:
    """Decode arrows, including modified CSI (``ESC[1;3A``).

    Bare Escape (no follower within the timeout) stays ``\\x1b``.
    Incomplete or unknown CSI/SS3 returns ``''`` so callers do not treat a
    failed arrow as back/quit, and leftover bytes are not leftover.
    """
    if first != "\x1b":
        return first
    second = read_available()
    if second is None:
        return "\x1b"
    if second == "O":
        final = read_available()
        if final is None:
            return ""
        return _ARROW_FINALS.get(final, "")
    if second != "[":
        # ESC + other (alt-key, noise). Do not treat as back.
        return ""

    params: list[str] = []
    while True:
        ch = read_available()
        if ch is None:
            return ""
        if len(ch) != 1:
            return ""
        code = ord(ch)
        # CSI final byte: @ through ~ (0x40–0x7E)
        if 0x40 <= code <= 0x7E:
            return _map_csi("".join(params), ch)
        params.append(ch)


def clear_lines(n: int) -> None:
    """Move cursor up n lines and clear from there to end of screen.

    Used to redraw menus in place instead of stacking duplicate frames.
    """
    if n <= 0:
        return
    sys.stdout.write(f"\033[{n}A\033[J")
    sys.stdout.flush()


def getch() -> str:
    """Read one keypress without Enter. Arrow keys decoded to UP/DOWN/LEFT/RIGHT.

    Ctrl-C (\\x03) is passed through so the caller decides whether to abort.

    Falls back to /dev/tty when stdin isn't a TTY (e.g. piped input).
    """
    tty_in = None
    if sys.stdin.isatty():
        stream = sys.stdin
    else:
        try:
            tty_in = open("/dev/tty", encoding="utf-8")
            stream = tty_in
        except OSError:
            stream = sys.stdin

    if not stream.isatty():
        console.print("[red]This script needs an interactive terminal.[/red]")
        sys.exit(1)

    fd = stream.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        ch = os.read(fd, 1).decode("utf-8", errors="replace")
        if ch == "\x1b":
            def read_available() -> str | None:
                readable, _, _ = select.select(
                    [fd], [], [], ESCAPE_SEQUENCE_TIMEOUT_SECONDS
                )
                if not readable:
                    return None
                return os.read(fd, 1).decode("utf-8", errors="replace")

            return _decode_escape_sequence(ch, read_available)
    finally:
        try:
            # TCSAFLUSH drops queued keystrokes, including an arrow sequence tail.
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        except termios.error:
            pass
        if tty_in is not None:
            tty_in.close()
    return ch


def getline(prompt: str) -> str:
    """Read one line of normal text input with a colored prompt.

    Uses cbreak mode restored after each read so getch and getline can interleave.
    """
    console.print(f"[bold]{prompt}[/bold] ", end="")
    tty_in = None
    try:
        if sys.stdin.isatty():
            stream = sys.stdin
        else:
            try:
                tty_in = open("/dev/tty", encoding="utf-8")
                stream = tty_in
            except OSError:
                stream = sys.stdin
        return stream.readline().rstrip("\n")
    except (EOFError, OSError):
        return ""
    finally:
        if tty_in is not None:
            tty_in.close()
