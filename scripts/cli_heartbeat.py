"""Heartbeat / control-plane interactive surface for gddp."""

from __future__ import annotations

import socket
from pathlib import Path

from rich.text import Text

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parent



def _menu_back():
    import gddp
    return gddp._MENU_BACK


def _menu_quit():
    import gddp
    return gddp._MENU_QUIT

def resolve_runtime_root() -> Path:
    import gddp
    return gddp.resolve_runtime_root()


import gddp as _gddp_host

os = _gddp_host.os
platform = _gddp_host.platform
re = _gddp_host.re
subprocess = _gddp_host.subprocess
sys = _gddp_host.sys

from gddp_proxy import console


def _clear_screen() -> None:
    import gddp
    gddp._clear_screen()


def _menu_choice(*args, **kwargs):
    import gddp
    return gddp._menu_choice(*args, **kwargs)


def _pause(message: str = "press any key to continue") -> str:
    import gddp
    return gddp._pause(message)

_SYSTEMD_TIMER = "gddp-heartbeat.timer"

_SYSTEMD_SERVICE = "gddp-heartbeat.service"

def _launchd_status(label: str) -> dict[str, object]:
    """Return registration, enablement, and live-health as separate facts."""
    try:
        service = subprocess.run(
            ["launchctl", "print", f"gui/{os.getuid()}/{label}"],
            capture_output=True,
            text=True,
        )
    except OSError:
        service = None
    registered = service is not None and service.returncode == 0
    if not registered:
        return {
            "registered": False,
            "enabled": False,
            "healthy": False,
            "state": "missing",
            "runs": 0,
            "last_exit": None,
        }

    output = service.stdout or ""
    state_match = re.search(r"^\s*state = ([^\n]+)$", output, re.MULTILINE)
    runs_match = re.search(r"^\s*runs = (\d+)$", output, re.MULTILINE)
    exit_match = re.search(r"^\s*last exit code = (-?\d+)$", output, re.MULTILINE)
    try:
        disabled = subprocess.run(
            ["launchctl", "print-disabled", f"gui/{os.getuid()}"],
            capture_output=True,
            text=True,
        )
        marker = re.search(
            rf'"{re.escape(label)}"\s*=>\s*(enabled|disabled)',
            disabled.stdout or "",
        )
    except OSError:
        marker = None

    enabled = marker is None or marker.group(1) == "enabled"
    state = state_match.group(1).strip() if state_match else "unknown"
    runs = int(runs_match.group(1)) if runs_match else 0
    last_exit = int(exit_match.group(1)) if exit_match else None
    if label == "com.gddp.heartbeat":
        healthy = enabled and runs > 0 and last_exit == 0
    else:
        healthy = enabled and state == "running"
    return {
        "registered": True,
        "enabled": enabled,
        "healthy": healthy,
        "state": state,
        "runs": runs,
        "last_exit": last_exit,
    }

def _sh(cmd: list[str]) -> str:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return proc.stdout

def _systemd_status() -> dict[str, str]:
    """Facts about the heartbeat timer/service on a systemd host. Read-only."""
    facts: dict[str, str] = {}
    for unit in (_SYSTEMD_TIMER, _SYSTEMD_SERVICE):
        out = _sh(["systemctl", "--user", "show", unit, "-p", "ActiveState", "-p", "UnitFileState",
                   "-p", "FragmentPath", "-p", "Result", "-p", "ExecMainExitTimestamp", "-p", "NextElapseUSecRealtime"])
        for line in out.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                facts[f"{unit}.{key}"] = value.strip()
    timers = _sh(["systemctl", "--user", "list-timers", "--all", _SYSTEMD_TIMER, "--no-legend"]).strip()
    facts["timer_line"] = timers.splitlines()[0] if timers else ""
    facts["journal"] = _sh(["journalctl", "--user", "-u", _SYSTEMD_SERVICE, "-n", "6", "--no-pager", "-o", "short-iso"]).rstrip()
    return facts

def _try_resolve_runtime_root() -> tuple[Path | None, str | None]:
    """Resolve runtime root without blowing out of the heartbeat screen."""
    try:
        return resolve_runtime_root(), None
    except RuntimeError as exc:
        return None, str(exc)

def _heartbeat_env_path(runtime_root: Path | None) -> Path:
    if runtime_root is None:
        return Path("(unset — set GDDP_RUNTIME_ROOT)") / "deploy" / "mini-heartbeat" / "env" / "gddp.env"
    return runtime_root / "deploy" / "mini-heartbeat" / "env" / "gddp.env"

def _heartbeat_kit_path(runtime_root: Path | None) -> Path:
    if runtime_root is None:
        return Path("(unset — set GDDP_RUNTIME_ROOT)") / "deploy" / "mini-heartbeat"
    return runtime_root / "deploy" / "mini-heartbeat"

def _render_heartbeat_notice(notice: str | None) -> None:
    """Paint a one-shot operator notice at the top of the status panel."""
    if not notice:
        return
    lowered = notice.lower()
    if any(token in lowered for token in ("cannot", "missing", "not found", "failed")):
        style = "yellow"
    elif "armed" in lowered or "disarmed" in lowered:
        style = "bold green"
    elif "already" in lowered or "nothing to repair" in lowered or "operational" in lowered:
        style = "dim"
    else:
        style = "yellow"
    console.print(Text(f"  {notice}", style=style))
    console.print()

def _systemd_heartbeat_actions() -> dict[str, tuple[str, str]]:
    return {
        "a": ("arm", f"start {_SYSTEMD_TIMER}"),
        "d": ("disarm", f"stop {_SYSTEMD_TIMER}"),
        "r": ("refresh", "reload status"),
        "b": ("back", ""),
    }

def _render_systemd_heartbeat_status(
    f: dict[str, str],
    env_path: Path,
    runtime_root: Path | None,
    runtime_error: str | None,
) -> tuple[bool, bool]:
    """Render systemd heartbeat facts. Returns (registered, active)."""
    registered = bool(f.get(f"{_SYSTEMD_TIMER}.FragmentPath"))
    active = f.get(f"{_SYSTEMD_TIMER}.ActiveState") == "active"
    if runtime_root is not None:
        systemd_dir = runtime_root / "deploy" / "mini-heartbeat" / "systemd"
    else:
        systemd_dir = Path("deploy/mini-heartbeat/systemd")

    if runtime_error:
        console.print(Text(f"  runtime    {runtime_error}", style="yellow"))

    if not registered:
        console.print(Text(f"  timer      absent  ({_SYSTEMD_TIMER} not installed)", style="yellow"))
        console.print(Text(f"  service    absent  ({_SYSTEMD_SERVICE} not installed)", style="yellow"))
        console.print(Text(f"  install    see {systemd_dir}/", style="dim"))
    else:
        state = Text("ARMED", style="bold green") if active else Text("off", style="dim")
        console.print(
            Text("  timer      "),
            state,
            Text(f"  enabled={f.get(f'{_SYSTEMD_TIMER}.UnitFileState', '?')}", style="dim"),
        )
        schedule = f.get("timer_line") or ""
        for unit in (_SYSTEMD_TIMER, _SYSTEMD_SERVICE):
            schedule = schedule.replace(unit, "")
        schedule = " ".join(schedule.split()) or "(never run)"
        console.print(Text(f"  next/last  {schedule}", style="dim"))
        result = f.get(f"{_SYSTEMD_SERVICE}.Result", "?")
        journal = f.get("journal") or ""
        if "Failed with result" in journal:
            result = "failed"
        console.print(
            Text("  last tick  "),
            Text(result, style="bold green" if result == "success" else "bold red"),
            Text(f"  at {f.get(f'{_SYSTEMD_SERVICE}.ExecMainExitTimestamp') or '?'}", style="dim"),
        )
        console.print(Text(f"  timer unit {f.get(f'{_SYSTEMD_TIMER}.FragmentPath')}", style="dim"))
        console.print(Text(f"  service    {f.get(f'{_SYSTEMD_SERVICE}.FragmentPath')}", style="dim"))

    env_present = runtime_root is not None and env_path.is_file()
    console.print(
        Text(
            f"  env file   {env_path}  {'(present)' if env_present else '(MISSING)'}",
            style="dim" if env_present else "bold red",
        )
    )
    console.print()
    console.print(Text("  last journal lines:", style="bold"))
    for line in (f.get("journal") or "  (empty)").splitlines():
        console.print(
            Text(f"    {line}", style="red" if "Error" in line or "Failed" in line else "dim"),
            overflow="ellipsis",
            no_wrap=True,
        )
    console.print()
    return registered, active

def _interactive_heartbeat_systemd():
    """Linux: show timer + service facts and arm/disarm through systemctl."""
    runtime_root, runtime_error = _try_resolve_runtime_root()
    env_path = _heartbeat_env_path(runtime_root)
    actions = _systemd_heartbeat_actions()
    notice: str | None = None

    while True:
        _clear_screen()
        import gddp
        f = gddp._systemd_status()
        console.print(
            Text("heartbeat", style="bold").append(
                f"  ·  {socket.gethostname()} (systemd)", style="dim"
            )
        )
        console.print()
        _render_heartbeat_notice(notice)
        notice = None
        registered, active = _render_systemd_heartbeat_status(
            f, env_path, runtime_root, runtime_error
        )

        try:
            choice = _menu_choice(actions, default="b")
        except (EOFError, KeyboardInterrupt):
            return _menu_back()
        if choice == "b":
            return _menu_back()
        if choice == "r":
            continue

        if choice == "a":
            if not registered:
                notice = (
                    f"cannot arm: {_SYSTEMD_TIMER} is not installed "
                    f"(see deploy/mini-heartbeat/systemd/)"
                )
                continue
            if active:
                notice = f"already armed: {_SYSTEMD_TIMER} is active"
                continue
            cmd = ["systemctl", "--user", "start", _SYSTEMD_TIMER]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if proc.returncode == 0:
                notice = f"armed: {_SYSTEMD_TIMER}"
            else:
                detail = (proc.stderr or proc.stdout or "").strip()
                console.print(
                    Text(f"  arm failed (exit {proc.returncode}): {detail}", style="bold red")
                )
                _pause()
            continue

        if choice == "d":
            if not registered:
                notice = f"cannot disarm: {_SYSTEMD_TIMER} is not installed"
                continue
            if not active:
                notice = f"already disarmed: {_SYSTEMD_TIMER} is inactive"
                continue
            cmd = ["systemctl", "--user", "stop", _SYSTEMD_TIMER]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if proc.returncode == 0:
                notice = f"disarmed: {_SYSTEMD_TIMER}"
            else:
                detail = (proc.stderr or proc.stdout or "").strip()
                console.print(
                    Text(f"  disarm failed (exit {proc.returncode}): {detail}", style="bold red")
                )
                _pause()
            continue

def _launchd_heartbeat_actions() -> dict[str, tuple[str, str]]:
    return {
        "a": ("arm", "load intake + heartbeat (arm.sh)"),
        "d": ("disarm", "unload control plane (disarm.sh)"),
        "r": ("repair", "reload degraded labels (arm.sh)"),
        "f": ("refresh", "reload status"),
        "b": ("back", ""),
    }

def _render_launchd_heartbeat_status(
    kit: Path,
    statuses: dict[str, dict[str, object]],
    env_path: Path,
    runtime_root: Path | None,
    runtime_error: str | None,
) -> tuple[bool, bool]:
    """Render launchd control-plane status. Returns (operational, any_enabled)."""
    if runtime_error:
        console.print(Text(f"  runtime    {runtime_error}", style="yellow"))
    kit_present = runtime_root is not None and kit.is_dir()
    console.print(
        Text(
            f"  kit      {kit}  {'(present)' if kit_present else '(MISSING)'}",
            style="dim" if kit_present else "bold red",
        )
    )
    env_present = runtime_root is not None and env_path.is_file()
    console.print(
        Text(
            f"  env file {env_path}  {'(present)' if env_present else '(MISSING)'}",
            style="dim" if env_present else "bold red",
        )
    )
    console.print(
        Text("  logs     ~/Library/Logs/gddp-heartbeat.log · gddp-heartbeat.err.log", style="dim")
    )
    for name in ("gddp-heartbeat.err.log", "gddp-heartbeat.log"):
        log_path = Path.home() / "Library" / "Logs" / name
        if log_path.is_file():
            try:
                tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-4:]
            except OSError:
                tail = []
            if tail:
                console.print(Text("  log tail:", style="bold"))
                for line in tail:
                    console.print(Text(f"    {line}", style="dim"), overflow="ellipsis", no_wrap=True)
            break
    console.print()
    for label, status in statuses.items():
        if status["healthy"]:
            state = Text("HEALTHY", style="bold green")
        elif status["enabled"]:
            state = Text("DEGRADED", style="bold red")
        else:
            state = Text("off", style="dim")
        detail = (
            f"registered={status['registered']} enabled={status['enabled']} "
            f"state={status['state']} runs={status['runs']} "
            f"last_exit={status['last_exit']}"
        )
        console.print(f"  {label}  ", state, f"  {detail}")

    operational = all(status["healthy"] for status in statuses.values())
    any_enabled = any(status["enabled"] for status in statuses.values())
    console.print()
    return operational, any_enabled

def _run_launchd_heartbeat_script(kit: Path, script: str) -> str | None:
    """Run a launchd kit script. Returns a sticky notice when the script is missing."""
    script_path = kit / "bin" / script
    if not kit.is_dir():
        return f"heartbeat kit missing: {kit} (set GDDP_RUNTIME_ROOT)"
    if not script_path.is_file():
        return f"cannot run {script}: missing {script_path} (set GDDP_RUNTIME_ROOT)"
    env = dict(os.environ)
    if script == "arm.sh":
        env["MINI_HEARTBEAT_ARM"] = "1"
    subprocess.run(["bash", str(script_path)], env=env, check=False)
    return None

def _interactive_heartbeat_launchd():
    """macOS: show launchd health and arm/disarm/repair through the mini-heartbeat kit."""
    runtime_root, runtime_error = _try_resolve_runtime_root()
    kit = _heartbeat_kit_path(runtime_root)
    env_path = _heartbeat_env_path(runtime_root)
    labels = ("com.gddp.intake", "com.gddp.heartbeat")
    actions = _launchd_heartbeat_actions()
    notice: str | None = None

    while True:
        _clear_screen()
        console.print(
            Text("heartbeat", style="bold").append(
                f"  ·  {socket.gethostname()} (launchd)", style="dim"
            )
        )
        console.print()
        _render_heartbeat_notice(notice)
        notice = None
        import gddp
        statuses = {label: gddp._launchd_status(label) for label in labels}
        operational, any_enabled = _render_launchd_heartbeat_status(
            kit, statuses, env_path, runtime_root, runtime_error
        )

        try:
            choice = _menu_choice(actions, default="b")
        except (EOFError, KeyboardInterrupt):
            return _menu_back()
        if choice == "b":
            return _menu_back()
        if choice == "f":
            continue

        if choice == "a":
            if operational:
                notice = "already operational — disarm if you want to stop"
                continue
            script_notice = _run_launchd_heartbeat_script(kit, "arm.sh")
            if script_notice:
                notice = script_notice
            continue

        if choice == "d":
            if not any_enabled and not operational:
                notice = "cannot disarm: control plane is not enabled"
                continue
            script_notice = _run_launchd_heartbeat_script(kit, "disarm.sh")
            if script_notice:
                notice = script_notice
            continue

        if choice == "r":
            if operational:
                notice = "nothing to repair: control plane is healthy"
                continue
            script_notice = _run_launchd_heartbeat_script(kit, "arm.sh")
            if script_notice:
                notice = script_notice
            continue

def interactive_heartbeat():
    """Show actual control-plane health and offer repair/arm or disarm."""
    if platform.system() == "Linux":
        return _interactive_heartbeat_systemd()
    return _interactive_heartbeat_launchd()
