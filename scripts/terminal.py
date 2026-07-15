"""Minimal terminal input helpers — single keypress + arrow decode.

Ported verbatim from context_refinery/triage/terminal.py — battle-tested on
the vault normalization TUI. No class hierarchy, no framework. Just getch,
getline, and a shared Console.
"""

import sys
import tty
import termios

try:
    from rich.console import Console
except ImportError:
    print("This script needs `rich`. Install:  pip install rich")
    sys.exit(1)

console = Console()


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
        ch = stream.read(1)
        if ch == "\x1b":
            seq = ch + stream.read(1)
            if seq[1] == "[":
                seq += stream.read(1)
                return {
                    "A": "UP",
                    "B": "DOWN",
                    "C": "RIGHT",
                    "D": "LEFT",
                    "H": "HOME",
                    "F": "END",
                }.get(seq[2], ch)
    finally:
        try:
            termios.tcsetattr(fd, termios.TCSAFLUSH, old)
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
