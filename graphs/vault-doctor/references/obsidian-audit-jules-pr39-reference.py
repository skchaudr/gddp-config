    def is_obsidian_running(self):
        """Check if Obsidian is currently running."""
        for proc in psutil.process_iter(['name']):
            try:
                name = proc.info['name'].lower()
                if name == 'obsidian' or name == 'obsidian.exe':
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return False

    def audit_obsidian_config(self):
        """Perform an audit of the .obsidian configuration directory."""
        obsidian_dir = self.vault_path / ".obsidian"
        warnings = []

        if not obsidian_dir.exists():
            return warnings

        # 1. Dataview Audit
        dataview_data = obsidian_dir / "plugins" / "dataview" / "data.json"
        if dataview_data.exists():
            try:
                with open(dataview_data, "r") as f:
                    data = json.load(f)
                    refresh_interval = data.get("refreshInterval", 2500) # Default if not set
                    if refresh_interval < 2000:
                        warnings.append({
                            "type": "Dataview",
                            "severity": "Warning",
                            "message": f"refreshInterval is too low ({refresh_interval}ms). May cause UI stuttering.",
                            "file": str(dataview_data.relative_to(self.vault_path))
                        })
            except Exception as e:
                 warnings.append({"type": "AuditError", "message": f"Error reading Dataview config: {e}"})

        # 2. File Recovery Audit
        app_json = obsidian_dir / "app.json"
        if app_json.exists():
            try:
                with open(app_json, "r") as f:
                    data = json.load(f)
                    # File recovery settings are often in app.json or internal.
                    # According to requirements, we check snapshot interval.
                    # Obsidian internal key might be different, but we'll follow user's instruction.
                    recovery_interval = data.get("fileRecoveryInterval", 5) # Default is 5 mins
                    if recovery_interval < 3:
                        warnings.append({
                            "type": "File Recovery",
                            "severity": "Warning",
                            "message": f"File recovery interval is too frequent ({recovery_interval} mins).",
                            "file": str(app_json.relative_to(self.vault_path))
                        })
            except Exception as e:
                warnings.append({"type": "AuditError", "message": f"Error reading app.json: {e}"})

        # 3. Massive Cache Scan
        plugins_dir = obsidian_dir / "plugins"
        if plugins_dir.exists():
            for plugin_folder in plugins_dir.iterdir():
                if plugin_folder.is_dir():
                    # data.json > 5MB
                    data_json = plugin_folder / "data.json"
                    if data_json.exists():
                        size_mb = data_json.stat().st_size / (1024 * 1024)
                        if size_mb > 5:
                            warnings.append({
                                "type": "Performance",
                                "severity": "Warning",
                                "message": f"Plugin data.json is too large ({size_mb:.2f}MB).",
                                "file": str(data_json.relative_to(self.vault_path))
                            })

                    # .db files > 20MB
                    for db_file in plugin_folder.glob("*.db"):
                        size_mb = db_file.stat().st_size / (1024 * 1024)
                        if size_mb > 20:
                            warnings.append({
                                "type": "Performance",
                                "severity": "Warning",
                                "message": f"Plugin database file is too large ({size_mb:.2f}MB).",
                                "file": str(db_file.relative_to(self.vault_path))
                            })

        # 4. CSS Snippet Validation
        appearance_json = obsidian_dir / "appearance.json"
        if appearance_json.exists():
            try:
                with open(appearance_json, "r") as f:
                    data = json.load(f)
                    enabled_snippets = data.get("enabledCssSnippets", [])
                    snippets_dir = obsidian_dir / "snippets"
                    for snippet in enabled_snippets:
                        snippet_file = snippets_dir / f"{snippet}.css"
                        if not snippet_file.exists():
                            warnings.append({
                                "type": "Orphaned Snippet",
                                "severity": "Warning",
                                "message": f"CSS snippet '{snippet}' is enabled but the file is missing.",
                                "file": "appearance.json"
                            })
            except Exception as e:
                warnings.append({"type": "AuditError", "message": f"Error reading appearance.json: {e}"})

        return warnings
import os
import time
import psutil
from pathlib import Path
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.progress import BarColumn, Progress, TextColumn

class LiveDashboard:
    def __init__(self, vault_path):
        self.vault_path = Path(vault_path)
        self.error_log_path = self.vault_path / ".vaultdoctor" / "errors.log"
        self.console = Console()
        self.obsidian_procs = {} # Persistent process objects for accurate CPU

    def get_obsidian_metrics(self):
        total_cpu = 0
        total_memory = 0

        # Update our list of active Obsidian processes
        current_pids = set()
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                name = proc.info['name'].lower()
                if name == 'obsidian' or name == 'obsidian.exe':
                    pid = proc.info['pid']
                    current_pids.add(pid)
                    if pid not in self.obsidian_procs:
                        # Initial call to cpu_percent(None) starts the timer for this process
                        p = psutil.Process(pid)
                        p.cpu_percent(None)
                        self.obsidian_procs[pid] = p
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Remove dead processes
        for pid in list(self.obsidian_procs.keys()):
            if pid not in current_pids:
                del self.obsidian_procs[pid]

        # Aggregate metrics
        for pid, proc in self.obsidian_procs.items():
            try:
                total_cpu += proc.cpu_percent(None)
                total_memory += proc.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        return total_cpu, total_memory, len(self.obsidian_procs)

    def get_last_errors(self, n=10):
        if not self.error_log_path.exists():
            return ["[yellow]No errors.log found in .vaultdoctor/[/yellow]"]

        try:
            # Efficiently read last n lines
            with open(self.error_log_path, "rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                buffer_size = 1024
                data = b""
                pos = size

                while pos > 0 and data.count(b"\n") <= n:
                    step = min(pos, buffer_size)
                    pos -= step
                    f.seek(pos)
                    data = f.read(step) + data

                lines = data.decode("utf-8", errors="ignore").splitlines()
                last_lines = lines[-n:]
                formatted_errors = []
                for line in last_lines:
                    line = line.strip()
                    if "[CONSOLE ERROR]" in line:
                        formatted_errors.append(f"[red]{line}[/red]")
                    elif "[WINDOW ERROR]" in line:
                        formatted_errors.append(f"[bold red]{line}[/bold red]")
                    else:
                        formatted_errors.append(line)
                return formatted_errors
        except Exception as e:
            return [f"[red]Error reading logs: {e}[/red]"]

    def make_layout(self):
        layout = Layout()
        layout.split(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=10),
        )
        return layout

    def run(self):
        layout = self.make_layout()

        cpu_progress = Progress(
            TextColumn("[bold blue]CPU Usage"),
            BarColumn(bar_width=None),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        )
        cpu_task = cpu_progress.add_task("CPU", total=100)

        with Live(layout, refresh_per_second=2, screen=True):
            while True:
                cpu, mem, count = self.get_obsidian_metrics()
                mem_mb = mem / (1024 * 1024)

                # Header
                layout["header"].update(Panel(
                    f"[bold blue]Vault Doctor Live Dashboard[/bold blue] | "
                    f"Obsidian Processes: [green]{count}[/green] | "
                    f"Total CPU: [magenta]{cpu:.1f}%[/magenta] | "
                    f"Total Memory: [magenta]{mem_mb:.1f} MB[/magenta]",
                    style="white on blue"
                ))

                # Main - Metrics visualization
                metrics_table = Table.grid(expand=True)
                metrics_table.add_column()

                # Update persistent progress object
                cpu_progress.update(cpu_task, completed=min(cpu, 100))

                metrics_table.add_row(Panel(cpu_progress, title="Overall Performance"))
                layout["main"].update(metrics_table)

                # Footer - Errors
                errors = self.get_last_errors()
                error_panel = Panel(
                    "\n".join(errors),
                    title="[bold red]Recent Errors (.vaultdoctor/errors.log)[/bold red]",
                    border_style="red"
                )
                layout["footer"].update(error_panel)

                time.sleep(0.5)

if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    dash = LiveDashboard(path)
    dash.run()
